// --------------------------------------------------------------------------------------
// Copyright (c) 2026, Nucleic Development Team.
//
// Distributed under the terms of the Modified BSD License.
//
// The full license is in the file LICENSE, distributed with this software.
// --------------------------------------------------------------------------------------
use pyo3::exceptions::PyTypeError;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyTuple};

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
    pub fn new(py: Python<'_>, method: &Bound<'_, PyAny>) -> PyResult<Self> {
        let owner = method.getattr("__self__").or_else(|_| {
            method
                .getattr("im_self")
                .map_err(|_| PyTypeError::new_err("WeakMethod() argument must be a bound method"))
        })?;
        if owner.is_none() {
            return Err(PyTypeError::new_err(
                "WeakMethod() argument must be a bound method",
            ));
        }

        let function = method.getattr("__func__").or_else(|_| {
            method
                .getattr("im_func")
                .map_err(|_| PyTypeError::new_err("WeakMethod() argument must be a bound method"))
        })?;

        Ok(Self {
            owner_ref: make_owner_ref(py, &owner)?,
            function: function.unbind(),
        })
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

    pub fn __bool__(&self, py: Python<'_>) -> bool {
        self.owner_ref
            .bind(py)
            .call0()
            .is_ok_and(|owner| !owner.is_none())
    }

    pub fn __repr__(&self, py: Python<'_>) -> String {
        match self.owner_ref.bind(py).call0() {
            Ok(owner) if !owner.is_none() => {
                let owner_repr = owner
                    .repr()
                    .map(|value| value.to_string())
                    .unwrap_or_else(|_| "<error>".to_string());
                let function_repr = self
                    .function
                    .bind(py)
                    .repr()
                    .map(|value| value.to_string())
                    .unwrap_or_else(|_| "<error>".to_string());
                format!(
                    "WeakMethod(owner={}, function={})",
                    owner_repr, function_repr
                )
            }
            _ => "WeakMethod(<dead>)".to_string(),
        }
    }
}
