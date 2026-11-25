// --------------------------------------------------------------------------------------
// Copyright (c) 2026, Nucleic Development Team.
//
// Distributed under the terms of the Modified BSD License.
//
// The full license is in the file LICENSE, distributed with this software.
// --------------------------------------------------------------------------------------
use pyo3::exceptions::PyTypeError;
use pyo3::prelude::*;
use pyo3::sync::PyOnceLock;
use pyo3::types::{PyDict, PyTuple};

static WEAK_METHOD_CACHE: PyOnceLock<Py<PyAny>> = PyOnceLock::new();

/// A callable weak reference to a bound Python method.
#[pyclass(subclass, weakref, module = "enaml.weakmethod")]
pub struct WeakMethod {
    owner_ref: Py<PyAny>,
    function: Py<PyAny>,
}

fn make_owner_ref(py: Python<'_>, owner: &Bound<'_, PyAny>) -> PyResult<Py<PyAny>> {
    let weakref = py.import("weakref")?;
    match weakref.getattr("ref")?.call1((owner,)) {
        Ok(reference) => Ok(reference.unbind()),
        Err(err) if err.is_instance_of::<PyTypeError>(py) => Ok(owner.clone().unbind()),
        Err(err) => Err(err),
    }
}

#[pymethods]
impl WeakMethod {
    #[new]
    #[pyo3(signature = (*args, **kwargs))]
    pub fn new(
        py: Python<'_>,
        args: &Bound<'_, PyTuple>,
        kwargs: Option<&Bound<'_, PyDict>>,
    ) -> PyResult<Py<WeakMethod>> {
        if kwargs.is_some_and(|values| !values.is_empty()) {
            let count = kwargs.map_or(0, |values| values.len());
            return Err(PyTypeError::new_err(format!(
                "WeakMethod() takes no keyword arguments ({count} given)"
            )));
        }
        if args.len() != 1 {
            return Err(PyTypeError::new_err(format!(
                "WeakMethod() takes 1 argument ({} given)",
                args.len()
            )));
        }

        let method = args.get_item(0)?;
        let owner = method
            .getattr("__self__")
            .map_err(|_| PyTypeError::new_err("WeakMethod() argument must be a MethodType"))?;
        if owner.is_none() {
            return Err(PyTypeError::new_err(
                "WeakMethod() argument must be a MethodType",
            ));
        }

        let function = method
            .getattr("__func__")
            .map_err(|_| PyTypeError::new_err("WeakMethod() argument must be a MethodType"))?;

        let cache = WEAK_METHOD_CACHE.get_or_try_init(py, || {
            let weakref = py.import("weakref")?;
            let dictionary = weakref.getattr("WeakKeyDictionary")?.call0()?;
            Ok::<Py<PyAny>, PyErr>(dictionary.unbind())
        })?;

        let methods = cache
            .bind(py)
            .call_method1("get", (owner.clone(), py.None()))?;
        if !methods.is_none() {
            let methods = methods.cast::<PyDict>()?;
            let existing = methods.call_method1("get", (function.clone(), py.None()))?;
            if !existing.is_none() {
                return Ok(existing.extract::<Py<WeakMethod>>()?);
            }
        }

        let weak_method = Py::new(
            py,
            WeakMethod {
                owner_ref: make_owner_ref(py, &owner)?,
                function: function.clone().unbind(),
            },
        )?;

        let methods = if methods.is_none() {
            let methods = PyDict::new(py);
            cache
                .bind(py)
                .call_method1("__setitem__", (owner, &methods))?;
            methods
        } else {
            methods.cast::<PyDict>()?.clone()
        };
        methods.set_item(function, weak_method.clone_ref(py))?;

        Ok(weak_method)
    }

    #[pyo3(name = "__call__", signature = (*args, **kwargs))]
    pub fn call(
        &self,
        py: Python<'_>,
        args: &Bound<'_, PyTuple>,
        kwargs: Option<&Bound<'_, PyDict>>,
    ) -> PyResult<Py<PyAny>> {
        let owner = self.owner_ref.bind(py).call0()?;
        if owner.is_none() {
            return Ok(py.None());
        }

        let mut values = Vec::with_capacity(args.len() + 1);
        values.push(owner);
        for arg in args.iter() {
            values.push(arg);
        }
        let call_args = PyTuple::new(py, values)?;
        let result = self.function.bind(py).call(&call_args, kwargs)?;
        Ok(result.unbind())
    }

    pub fn __bool__(&self) -> bool {
        true
    }

    pub fn __repr__(&self) -> String {
        format!("<enaml.weakmethod.WeakMethod object at {:p}>", self)
    }
}
