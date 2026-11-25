// --------------------------------------------------------------------------------------
// Copyright (c) 2026, Nucleic Development Team.
//
// Distributed under the terms of the Modified BSD License.
//
// The license is in the LICENSE file in the project root.
// --------------------------------------------------------------------------------------
use pyo3::exceptions::PyAttributeError;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList, PyTuple};

const SLOTS_ATTR: &str = "__enaml_signaling_slots";

/// A descriptor for weak, bound signal connections.
#[pyclass(subclass, weakref, module = "enaml.signaling")]
pub struct Signal {}

impl Signal {
    fn disconnect_owner(_py: Python<'_>, owner: &Bound<'_, PyAny>) -> PyResult<()> {
        match owner.getattr(SLOTS_ATTR) {
            Ok(slots) => {
                if slots.cast::<PyDict>().is_ok() {
                    owner.delattr(SLOTS_ATTR)?;
                }
            }
            Err(_) => {}
        }
        Ok(())
    }

    fn slots_for_owner<'py>(
        py: Python<'py>,
        owner: &Bound<'py, PyAny>,
        signal: &Bound<'py, PyAny>,
        create: bool,
    ) -> PyResult<Option<Bound<'py, PyList>>> {
        let slots_attr = match owner.getattr(SLOTS_ATTR) {
            Ok(value) => value,
            Err(_) if create => {
                let slots = PyDict::new(py);
                owner.setattr(SLOTS_ATTR, slots)?;
                owner.getattr(SLOTS_ATTR)?
            }
            Err(_) => return Ok(None),
        };
        let slots = match slots_attr.cast::<PyDict>() {
            Ok(value) => value,
            Err(_) => return Ok(None),
        };
        if let Some(existing) = slots.get_item(signal)? {
            return Ok(Some(existing.cast::<PyList>()?.clone()));
        }
        if !create {
            return Ok(None);
        }
        let list = PyList::empty(py);
        slots.set_item(signal, &list)?;
        Ok(Some(list))
    }

    fn slot_for(py: Python<'_>, slot: &Bound<'_, PyAny>) -> PyResult<Py<PyAny>> {
        if slot.hasattr("__self__")? && !slot.getattr("__self__")?.is_none() {
            let weakref = py.import("weakref")?;
            let weak_method = weakref.getattr("WeakMethod")?;
            return Ok(weak_method.call1((slot,))?.unbind());
        }
        let weakref = py.import("weakref")?;
        match weakref.getattr("ref")?.call1((slot,)) {
            Ok(reference) => Ok(reference.unbind()),
            Err(_) => Ok(slot.clone().unbind()),
        }
    }

    fn resolve_slot(_py: Python<'_>, slot: &Bound<'_, PyAny>) -> PyResult<Py<PyAny>> {
        if slot.hasattr("__call__")? {
            if let Ok(value) = slot.call0() {
                return Ok(value.unbind());
            }
        }
        Ok(slot.clone().unbind())
    }

    fn same_slot(
        py: Python<'_>,
        left: &Bound<'_, PyAny>,
        right: &Bound<'_, PyAny>,
    ) -> PyResult<bool> {
        let left_resolved = Self::resolve_slot(py, left)?;
        let right_resolved = Self::resolve_slot(py, right)?;
        let left_owner = match left_resolved.bind(py).getattr("__self__") {
            Ok(value) if !value.is_none() => Some(value),
            _ => None,
        };
        let right_owner = match right_resolved.bind(py).getattr("__self__") {
            Ok(value) if !value.is_none() => Some(value),
            _ => None,
        };
        if left_owner.is_some() || right_owner.is_some() {
            if let (Some(left_owner), Some(right_owner)) = (left_owner, right_owner) {
                let left_func = left_resolved.bind(py).getattr("__func__");
                let right_func = right_resolved.bind(py).getattr("__func__");
                if let (Ok(left_func), Ok(right_func)) = (left_func, right_func) {
                    return Ok(left_owner.as_ptr() == right_owner.as_ptr()
                        && left_func.as_ptr() == right_func.as_ptr());
                }
            }
            return Ok(false);
        }
        Ok(left_resolved.bind(py).as_ptr() == right_resolved.bind(py).as_ptr())
    }
}

#[pymethods]
impl Signal {
    #[new]
    pub fn new() -> PyResult<Self> {
        Ok(Self {})
    }

    pub fn __get__<'py>(
        slf: PyRef<'py, Self>,
        obj: Option<Py<PyAny>>,
        _owner: Option<Py<PyAny>>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let py = slf.py();
        if obj.is_none() {
            return Ok(slf.into_pyobject(py)?.into_any());
        }
        let owner = obj.unwrap();
        let weakref = py.import("weakref")?;
        let objref = match weakref.getattr("ref")?.call1((owner.bind(py),)) {
            Ok(reference) => reference.unbind(),
            Err(_) => owner,
        };
        let signal = slf.into_pyobject(py)?.into_any().unbind();
        let bound = Py::new(py, BoundSignal::new(signal, objref)?)?;
        Ok(bound.into_bound(py).into_any())
    }

    pub fn __set__(
        &self,
        _obj: &Bound<'_, PyAny>,
        _value: &Bound<'_, PyAny>,
    ) -> PyResult<()> {
        Err(PyAttributeError::new_err("can't set read only Signal"))
    }

    pub fn __delete__(&self, _py: Python<'_>, obj: &Bound<'_, PyAny>) -> PyResult<()> {
        match obj.getattr(SLOTS_ATTR) {
            Ok(value) => {
                if let Ok(slots) = value.cast::<PyDict>() {
                    slots.clear();
                }
            }
            Err(_) => {}
        }
        Ok(())
    }

    #[staticmethod]
    pub fn disconnect_all(py: Python<'_>, obj: &Bound<'_, PyAny>) -> PyResult<()> {
        Self::disconnect_owner(py, obj)
    }
}

/// A bound signal associated with a single owner instance.
#[pyclass(subclass, weakref, module = "enaml.signaling")]
pub struct BoundSignal {
    signal: Py<PyAny>,
    objref: Py<PyAny>,
}

impl BoundSignal {
    fn owner<'py>(&self, py: Python<'py>) -> PyResult<Py<PyAny>> {
        let objref = self.objref.bind(py);
        let owner = if objref.hasattr("__call__")? {
            match objref.call0() {
                Ok(value) => value.unbind(),
                Err(_) => py.None(),
            }
        } else {
            objref.clone().unbind()
        };
        if owner.is_none(py) {
            return Ok(py.None());
        }
        if let Ok(method_owner) = owner.bind(py).getattr("__self__") {
            if !method_owner.is_none() {
                return Ok(method_owner.unbind());
            }
        }
        Ok(owner)
    }
}

#[pymethods]
impl BoundSignal {
    #[new]
    pub fn new(signal: Py<PyAny>, objref: Py<PyAny>) -> PyResult<Self> {
        Ok(Self { signal, objref })
    }

    pub fn _owner(&self, py: Python<'_>) -> Py<PyAny> {
        self.owner(py).unwrap_or_else(|_| py.None())
    }

    pub fn connect(&self, py: Python<'_>, slot: &Bound<'_, PyAny>) -> PyResult<()> {
        let owner = self.owner(py)?;
        if owner.is_none(py) {
            return Ok(());
        }
        let signal = self.signal.bind(py);
        let Some(slots) =
            Signal::slots_for_owner(py, &owner.bind(py), signal, true)?
        else {
            return Ok(());
        };
        let slot_ref = Signal::slot_for(py, slot)?;
        for existing in slots.iter() {
            if Signal::same_slot(py, &existing, slot)? {
                return Ok(());
            }
        }
        slots.append(slot_ref.bind(py))?;
        Ok(())
    }

    pub fn disconnect(&self, py: Python<'_>, slot: &Bound<'_, PyAny>) -> PyResult<()> {
        let owner = self.owner(py)?;
        if owner.is_none(py) {
            return Ok(());
        }
        let signal = self.signal.bind(py);
        let Some(slots) =
            Signal::slots_for_owner(py, &owner.bind(py), signal, false)?
        else {
            return Ok(());
        };
        let mut index = 0;
        while index < slots.len() {
            let existing = slots.get_item(index)?;
            if Signal::same_slot(py, &existing, slot)? {
                slots.del_item(index)?;
                break;
            }
            index += 1;
        }
        Ok(())
    }

    #[pyo3(signature = (*args, **kwargs))]
    pub fn emit(
        &self,
        py: Python<'_>,
        args: &Bound<'_, PyTuple>,
        kwargs: Option<&Bound<'_, PyDict>>,
    ) -> PyResult<Py<PyAny>> {
        let owner = self.owner(py)?;
        if owner.is_none(py) {
            return Ok(py.None());
        }
        let signal = self.signal.bind(py);
        let Some(slots) =
            Signal::slots_for_owner(py, &owner.bind(py), signal, false)?
        else {
            return Ok(py.None());
        };
        let mut last = py.None();
        for slot_ref in slots.iter() {
            let slot = Signal::resolve_slot(py, &slot_ref)?;
            if !slot.is_none(py) {
                last = slot.bind(py).call(args, kwargs)?.unbind();
            }
        }
        Ok(last)
    }

    #[pyo3(name = "__call__", signature = (*args, **kwargs))]
    pub fn call(
        &self,
        py: Python<'_>,
        args: &Bound<'_, PyTuple>,
        kwargs: Option<&Bound<'_, PyDict>>,
    ) -> PyResult<Py<PyAny>> {
        self.emit(py, args, kwargs)
    }

    pub fn __eq__(&self, py: Python<'_>, other: &Bound<'_, PyAny>) -> PyResult<bool> {
        let Ok(other) = other.cast::<BoundSignal>() else {
            return Ok(false);
        };
        let other = other.borrow();
        let owner = self.owner(py)?;
        let other_owner = other.owner(py)?;
        Ok(owner.bind(py).as_ptr() == other_owner.bind(py).as_ptr()
            && self.signal.bind(py).as_ptr() == other.signal.bind(py).as_ptr())
    }

    pub fn __repr__(&self, py: Python<'_>) -> String {
        let owner = self.owner(py).unwrap_or_else(|_| py.None());
        if owner.is_none(py) {
            "BoundSignal(<dead>)".to_string()
        } else {
            format!(
                "BoundSignal(signal={}, owner={})",
                self.signal
                    .bind(py)
                    .repr()
                    .map_or_else(|_| "<error>".to_string(), |v| v.to_string()),
                owner
                    .bind(py)
                    .repr()
                    .map_or_else(|_| "<error>".to_string(), |v| v.to_string())
            )
        }
    }
}
