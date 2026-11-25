// --------------------------------------------------------------------------------------
// Copyright (c) 2013-2026, Nucleic Development Team.
//
// Distributed under the terms of the Modified BSD License.
//
// The full license is in the file LICENSE, distributed with this software.
// --------------------------------------------------------------------------------------
use core::ffi::c_int;
use pyo3::ffi;
use pyo3::intern;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyFunction, PyMapping, PyTuple};

/// Call a function with optional locals mapping.
///
/// This allows Enaml to generate bytecode with LOAD_GLOBAL replaced with LOAD_NAME
/// and use a custom locals mapping to implement dynamic scoping.
#[pyfunction]
#[pyo3(signature = (func, func_args, func_kwargs, func_locals = None))]
pub fn call_func(
    py: Python<'_>,
    func: &Bound<'_, PyFunction>,
    func_args: &Bound<'_, PyTuple>,
    func_kwargs: &Bound<'_, PyDict>,
    func_locals: Option<&Bound<'_, PyMapping>>,
) -> PyResult<Py<PyAny>> {
    let code = func.getattr(intern!(py, "__code__"))?;
    let globals = func.getattr(intern!(py, "__globals__"))?;
    let defaults = func.getattr(intern!(py, "__defaults__"))?;
    let closure = func.getattr(intern!(py, "__closure__"))?;

    let mut kw_values = Vec::new();
    for (key, value) in func_kwargs.iter() {
        kw_values.push(key.as_ptr());
        kw_values.push(value.as_ptr());
    }

    let defaults_values = if defaults.is_none() {
        None
    } else {
        let tuple = defaults.cast::<PyTuple>()?;
        Some(tuple.iter().map(|item| item.as_ptr()).collect::<Vec<_>>())
    };
    let defaults_ptr = match defaults_values.as_ref() {
        Some(values) => values.as_ptr(),
        None => std::ptr::null_mut(),
    };
    let default_count = defaults_values.as_ref().map_or(0, |values| values.len()) as c_int;

    let fast_args = unsafe { ffi::PySequence_Fast(func_args.as_ptr(), c"".as_ptr()) };
    if fast_args.is_null() {
        return Err(PyErr::fetch(py));
    }
    let args_ptr = unsafe { ffi::PySequence_Fast_ITEMS(fast_args) };

    let locals_ptr = func_locals.map_or(std::ptr::null_mut(), |locals| locals.as_ptr());

    let closure_ptr = if closure.is_none() {
        std::ptr::null_mut()
    } else {
        closure.as_ptr()
    };
    let kwdefaults_ptr = std::ptr::null_mut();
    let kwds_ptr = if kw_values.is_empty() {
        std::ptr::null_mut()
    } else {
        kw_values.as_ptr()
    };

    let result = unsafe {
        ffi::PyEval_EvalCodeEx(
            code.as_ptr(),
            globals.as_ptr(),
            locals_ptr,
            args_ptr,
            func_args.len() as c_int,
            kwds_ptr,
            (kw_values.len() / 2) as c_int,
            defaults_ptr,
            default_count,
            kwdefaults_ptr,
            closure_ptr,
        )
    };

    unsafe {
        ffi::Py_DecRef(fast_args);
    }
    if result.is_null() {
        return Err(PyErr::fetch(py));
    }
    Ok(unsafe { Bound::from_owned_ptr(py, result).unbind() })
}
