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
#[pyclass(immutable_type, module = "fontext")]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum FontStyle {
    Normal = 0,
    Italic = 1,
    Oblique = 2,
}

// --------------------------------------------------------------------------------------
// FontStretch - represents font width variations
#[pyclass(immutable_type, module = "fontext")]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum FontStretch {
    UltraCondensed = 0,
    ExtraCondensed = 1,
    Condensed = 2,
    SemiCondensed = 3,
    Unstretched = 4,
    SemiExpanded = 5,
    Expanded = 6,
    ExtraExpanded = 7,
    UltraExpanded = 8,
}

// --------------------------------------------------------------------------------------
// FontCaps - represents font capitalization variants
#[pyclass(immutable_type, module = "fontext")]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum FontCaps {
    MixedCase = 0,
    AllUppercase = 1,
    AllLowercase = 2,
    SmallCaps = 3,
    Capitalize = 4,
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
