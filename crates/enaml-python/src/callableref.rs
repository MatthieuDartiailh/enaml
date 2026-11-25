// --------------------------------------------------------------------------------------
// Copyright (c) 2026, Nucleic Development Team.
//
// Distributed under the terms of the Modified BSD License.
//
// The license is in the LICENSE file in the project root.
// --------------------------------------------------------------------------------------
use pyo3::exceptions::PyTypeError;
use pyo3::prelude::*;
use pyo3::types::{PyBool, PyDict, PyTuple};
use pyo3::basic::CompareOp;

/// A weak callable reference with an optional weak callback.
#[pyclass(subclass, weakref, module = "enaml.callableref")]
pub struct CallableRef {
    value_ref: Py<PyAny>,
    callback_ref: Option<Py<PyAny>>,
}

fn make_ref(py: Python<'_>, value: &Bound<'_, PyAny>) -> PyResult<Py<PyAny>> {
    let weakref = py.import("weakref")?;
    match weakref.getattr("ref")?.call1((value,)) {
        Ok(reference) => Ok(reference.unbind()),
        Err(err) if err.is_instance_of::<PyTypeError>(py) => Ok(value.clone().unbind()),
        Err(err) => Err(err),
    }
}

impl CallableRef {
    fn resolve(&self, py: Python<'_>) -> Py<PyAny> {
        self.value_ref
            .bind(py)
            .call0()
            .map(|value| value.unbind())
            .unwrap_or_else(|_| py.None())
    }
}

#[pymethods]
impl CallableRef {
    #[new]
    pub fn new(
        py: Python<'_>,
        value: &Bound<'_, PyAny>,
        callback: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<Self> {
        let callback_ref = match callback {
            Some(callback) => Some(make_ref(py, callback)?),
            None => None,
        };
        Ok(Self {
            value_ref: make_ref(py, value)?,
            callback_ref,
        })
    }

    #[getter]
    #[pyo3(name = "ref")]
    pub fn get_ref(&self, py: Python<'_>) -> Py<PyAny> {
        self.value_ref.clone_ref(py)
    }

    #[pyo3(name = "__call__", signature = (*args, **kwargs))]
    pub fn call(
        &self,
        py: Python<'_>,
        args: &Bound<'_, PyTuple>,
        kwargs: Option<&Bound<'_, PyDict>>,
    ) -> PyResult<Py<PyAny>> {
        let value = self.resolve(py);
        if value.is_none(py) {
            if let Some(callback_ref) = &self.callback_ref {
                let callback = callback_ref.bind(py).call0()?;
                if !callback.is_none() {
                    callback.call0()?;
                }
            }
            return Ok(py.None());
        }
        let result = value.bind(py).call(args, kwargs)?;
        Ok(result.unbind())
    }

    pub fn __bool__(&self, py: Python<'_>) -> bool {
        let value = self.resolve(py);
        !value.is_none(py)
    }

    pub fn __repr__(&self, py: Python<'_>) -> String {
        let value = self.resolve(py);
        if value.is_none(py) {
            "<dead CallableRef>".to_string()
        } else {
            format!(
                "CallableRef({})",
                value
                    .bind(py)
                    .repr()
                    .map_or_else(|_| "<error>".to_string(), |v| v.to_string())
            )
        }
    }

    pub fn __richcmp__(
        &self,
        py: Python<'_>,
        other: &Bound<'_, PyAny>,
        op: CompareOp,
    ) -> PyResult<Py<PyAny>> {
        match op {
            CompareOp::Eq | CompareOp::Ne => {
                let value = self.resolve(py);
                let other_value = if let Ok(other_ref) = other.cast::<CallableRef>() {
                    other_ref.borrow().resolve(py)
                } else if other.hasattr("__call__").unwrap_or(false) {
                    match other.call0() {
                        Ok(value) => value.unbind(),
                        Err(_) => py.None(),
                    }
                } else {
                    py.None()
                };
                let equal = !value.is_none(py)
                    && !other_value.is_none(py)
                    && value.bind(py).as_ptr() == other_value.bind(py).as_ptr();
                let result = match op {
                    CompareOp::Eq => equal,
                    CompareOp::Ne => !equal,
                    _ => unreachable!(),
                };
                Ok(PyBool::new(py, result).to_owned().into_any().unbind())
            }
            _ => Ok(py.NotImplemented()),
        }
    }
}
