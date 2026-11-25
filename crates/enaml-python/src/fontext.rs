// --------------------------------------------------------------------------------------
// Copyright (c) 2013-2026, Nucleic Development Team.
//
// Distributed under the terms of the Modified BSD License.
//
// The full license is in the file LICENSE, distributed with this software.
// --------------------------------------------------------------------------------------
use pyo3::prelude::*;

type FontReduceArgs = (String, i32, i32, i32, i32, i32);

// --------------------------------------------------------------------------------------
// FontStyle - represents text style (normal, italic, oblique)
#[pyclass(module = "fontext")]
pub struct FontStyle {}

#[pymethods]
#[allow(non_upper_case_globals)]
impl FontStyle {
    #[classattr]
    const Normal: i32 = 0;
    #[classattr]
    const Italic: i32 = 1;
    #[classattr]
    const Oblique: i32 = 2;
}

// --------------------------------------------------------------------------------------
// FontStretch - represents font width variations
#[pyclass(module = "fontext")]
pub struct FontStretch {}

#[pymethods]
#[allow(non_upper_case_globals)]
impl FontStretch {
    #[classattr]
    const UltraCondensed: i32 = 0;
    #[classattr]
    const ExtraCondensed: i32 = 1;
    #[classattr]
    const Condensed: i32 = 2;
    #[classattr]
    const SemiCondensed: i32 = 3;
    #[classattr]
    const Unstretched: i32 = 4;
    #[classattr]
    const SemiExpanded: i32 = 5;
    #[classattr]
    const Expanded: i32 = 6;
    #[classattr]
    const ExtraExpanded: i32 = 7;
    #[classattr]
    const UltraExpanded: i32 = 8;
}

// --------------------------------------------------------------------------------------
// FontCaps - represents font capitalization variants
#[pyclass(module = "fontext")]
pub struct FontCaps {}

#[pymethods]
#[allow(non_upper_case_globals)]
impl FontCaps {
    #[classattr]
    const MixedCase: i32 = 0;
    #[classattr]
    const AllUppercase: i32 = 1;
    #[classattr]
    const AllLowercase: i32 = 2;
    #[classattr]
    const SmallCaps: i32 = 3;
    #[classattr]
    const Capitalize: i32 = 4;
}

/// Font descriptor for Enaml UI elements
#[pyclass(immutable_type, module = "enaml.fontext")]
pub struct Font {
    #[pyo3(get, set)]
    _tkdata: Option<Py<PyAny>>,

    #[pyo3(get)]
    family: String,

    #[pyo3(get)]
    pointsize: i32,

    #[pyo3(get)]
    weight: i32,
    style: i32,
    caps: i32,
    stretch: i32,
}

#[pymethods]
impl Font {
    #[new]
    #[pyo3(signature = (family = String::new(), pointsize = -1, weight = -1, style = 0, caps = 0, stretch = 4))]
    pub fn new(
        family: String,
        pointsize: i32,
        weight: i32,
        style: i32,
        caps: i32,
        stretch: i32,
    ) -> Self {
        let pointsize = pointsize.max(-1);
        let weight = weight.clamp(-1, 99);
        let style = if (0..=2).contains(&style) { style } else { 0 };
        let caps = if (0..=4).contains(&caps) { caps } else { 0 };
        let stretch = if (0..=8).contains(&stretch) {
            stretch
        } else {
            4
        };
        Font {
            _tkdata: None,
            family,
            pointsize,
            weight,
            style,
            caps,
            stretch,
        }
    }

    #[getter]
    fn style(&self) -> i32 {
        self.style
    }

    #[getter]
    fn caps(&self) -> i32 {
        self.caps
    }

    #[getter]
    fn stretch(&self) -> i32 {
        self.stretch
    }

    pub fn __repr__(&self) -> String {
        format!(
            "Font(family=\"{}\", pointsize={}, weight={}, style={}, caps={}stretch={}",
            self.family,
            self.pointsize,
            self.weight,
            match self.style {
                0 => "Normal",
                1 => "Italic",
                2 => "Oblique",
                _ => "Normal",
            },
            match self.caps {
                0 => "MixedCase",
                1 => "AllUppercase",
                2 => "AllLowercase",
                3 => "SmallCaps",
                4 => "Capitalize",
                _ => "MixedCase",
            },
            match self.stretch {
                0 => "UltraCondensed)",
                1 => "ExtraCondensed)",
                2 => "Condensed)",
                3 => "SemiCondensed)",
                4 => "Unstretched)",
                5 => "SemiExpanded)",
                6 => "Expanded)",
                7 => "ExtraExpanded)",
                8 => "UltraExpanded)",
                _ => "Unstretched)",
            }
        )
    }

    fn __reduce__(&self, py: Python<'_>) -> PyResult<(Py<PyAny>, FontReduceArgs)> {
        // Return (_reconstruct_font, (family, pointsize, weight, style, caps, stretch))
        let fonts_module = py.import("enaml.fonts")?;
        let reconstruct = fonts_module.getattr("_reconstruct_font")?;
        let args = (
            self.family.clone(),
            self.pointsize,
            self.weight,
            self.style,
            self.caps,
            self.stretch,
        );
        Ok((reconstruct.into(), args))
    }
}
