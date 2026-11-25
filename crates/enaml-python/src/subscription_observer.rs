// --------------------------------------------------------------------------------------
// Copyright (c) 2013-2026, Nucleic Development Team.
//
// Distributed under the terms of the Modified BSD License.
//
// The full license is in the file LICENSE, distributed with this software.
// --------------------------------------------------------------------------------------
use pyo3::exceptions::PyTypeError;
use pyo3::prelude::*;
use pyo3::types::{PyAnyMethods, PyDict, PyString, PyTuple};

/// Small callable wrapper used when the observed owner cannot be weak-referenced.
#[pyclass(module = "enaml._rust")]
pub struct SubscriptionCallableRef {
    value: Py<PyAny>,
}

#[pymethods]
impl SubscriptionCallableRef {
    #[new]
    pub fn new(value: Py<PyAny>) -> Self {
        Self { value }
    }

    #[pyo3(name = "__call__", signature = (*_args, **_kwargs))]
    pub fn __call__(
        &self,
        py: Python<'_>,
        _args: &Bound<'_, PyTuple>,
        _kwargs: Option<&Bound<'_, PyDict>>,
    ) -> PyResult<Py<PyAny>> {
        Ok(self.value.clone_ref(py))
    }
}

/// Subscription observer for reactive updates.
///
/// Observes object subscriptions and triggers reactive updates when subscribed
/// attributes change. Stores a reference to the observed object (via weakref if
/// possible, otherwise via a callable adapter) and the attribute name.
#[pyclass(subclass, weakref, dict, module = "enaml.core.subscription_observer")]
pub struct SubscriptionObserver {}

fn make_ref(py: Python<'_>, owner: &Bound<'_, PyAny>) -> PyResult<Py<PyAny>> {
    let weakref_module = py.import("weakref")?;
    let ref_fn = weakref_module.getattr("ref")?;

    match ref_fn.call1((owner,)) {
        Ok(weak_ref) => Ok(weak_ref.unbind()),
        Err(err) if err.is_instance_of::<PyTypeError>(py) => {
            let wrapper = Py::new(py, SubscriptionCallableRef::new(owner.clone().unbind()))?;
            Ok(wrapper.into_any())
        }
        Err(err) => Err(err),
    }
}

#[pymethods]
impl SubscriptionObserver {
    #[new]
    pub fn new(
        py: Python<'_>,
        owner: &Bound<'_, PyAny>,
        attribute: &Bound<'_, PyAny>,
    ) -> PyResult<Py<SubscriptionObserver>> {
        if !attribute.is_instance_of::<PyString>() {
            return Err(PyTypeError::new_err("attribute must be a string"));
        }

        if owner.is_none() {
            return Err(PyTypeError::new_err("owner must not be None"));
        }

        let observer = Py::new(py, SubscriptionObserver {})?;
        let bound = observer.bind(py);
        bound.setattr("_ref_obj", make_ref(py, owner)?)?;
        bound.setattr("_attribute", attribute.clone())?;
        Ok(observer)
    }

    /// Return the attribute name.
    #[getter]
    pub fn name(slf: &Bound<'_, Self>) -> PyResult<Py<PyAny>> {
        Ok(slf.getattr("_attribute")?.unbind())
    }

    /// Return the callable ref object used to resolve the owner.
    #[getter]
    pub fn get_ref(slf: &Bound<'_, Self>) -> PyResult<Py<PyAny>> {
        Ok(slf.getattr("_ref_obj")?.unbind())
    }

    /// Set the ref property - can only be set to None.
    #[setter]
    pub fn set_ref(
        slf: &Bound<'_, Self>,
        py: Python<'_>,
        value: &Bound<'_, PyAny>,
    ) -> PyResult<()> {
        if value.is_none() {
            slf.setattr("_ref_obj", py.None())?;
            Ok(())
        } else {
            Err(PyTypeError::new_err("ref can only be set to None"))
        }
    }

    /// Return True when the owner is still available.
    pub fn __bool__(slf: &Bound<'_, Self>) -> bool {
        let Ok(ref_obj) = slf.getattr("_ref_obj") else {
            return false;
        };
        if ref_obj.is_none() {
            return false;
        }

        ref_obj.call0().is_ok_and(|owner| !owner.is_none())
    }

    /// Call the subscription observer callback.
    #[pyo3(name = "__call__", signature = (*_args, **_kwargs))]
    pub fn __call__(
        slf: &Bound<'_, Self>,
        py: Python<'_>,
        _args: &Bound<'_, PyTuple>,
        _kwargs: Option<&Bound<'_, PyDict>>,
    ) -> PyResult<Py<PyAny>> {
        let ref_obj = slf.getattr("_ref_obj")?;
        let owner = ref_obj.call0()?;
        if owner.is_none() {
            return Ok(py.None());
        }

        match owner.getattr("_d_engine") {
            Ok(engine) => {
                let attr_bound = slf.getattr("_attribute")?;
                Ok(engine
                    .call_method("update", (owner, attr_bound), None)?
                    .unbind())
            }
            Err(_) => Ok(py.None()),
        }
    }

    /// Return string representation.
    pub fn __repr__(slf: &Bound<'_, Self>) -> PyResult<String> {
        Ok(format!(
            "<enaml.core.subscription_observer.SubscriptionObserver object at {:p}>",
            slf.as_ptr()
        ))
    }
}
