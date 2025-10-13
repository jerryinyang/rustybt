#!/usr/bin/env python
"""
Minimal setup.py for building Cython and Rust extensions.

This file is kept separate from package metadata (now in pyproject.toml) to handle
extension building which is not yet fully supported in pure pyproject.toml.

Architecture:
- Package metadata, dependencies, scripts: pyproject.toml
- Extension building (Cython, Rust): This file
- Package discovery: Explicit configuration in pyproject.toml
"""

from pathlib import Path

import numpy
from Cython.Build import cythonize
from setuptools import Extension
from setuptools_rust import Binding, RustExtension

ROOT_DIR = Path(__file__).parent.resolve()


def window_specialization(typename):
    """Make an extension for an AdjustedArrayWindow specialization."""
    return Extension(
        name=f"rustybt.lib._{typename}window",
        sources=[f"rustybt/lib/_{typename}window.pyx"],
        depends=["rustybt/lib/_windowtemplate.pxi"],
        define_macros=[("NPY_NO_DEPRECATED_API", "NPY_1_7_API_VERSION")],
    )


# Cython compiler options
ext_options = {
    "compiler_directives": {
        "profile": True,
        "language_level": "3",
        "embedsignature": True,
    },
    "annotate": True,
}

# Define all Cython extensions
ext_modules = [
    # Assets
    Extension(
        name="rustybt.assets._assets",
        sources=["rustybt/assets/_assets.pyx"],
        define_macros=[("NPY_NO_DEPRECATED_API", "NPY_1_7_API_VERSION")],
    ),
    Extension(
        name="rustybt.assets.continuous_futures",
        sources=["rustybt/assets/continuous_futures.pyx"],
        define_macros=[("NPY_NO_DEPRECATED_API", "NPY_1_7_API_VERSION")],
    ),
    # Lib
    Extension(
        name="rustybt.lib.adjustment",
        sources=["rustybt/lib/adjustment.pyx"],
        define_macros=[("NPY_NO_DEPRECATED_API", "NPY_1_7_API_VERSION")],
    ),
    Extension(
        name="rustybt.lib._factorize",
        sources=["rustybt/lib/_factorize.pyx"],
        define_macros=[("NPY_NO_DEPRECATED_API", "NPY_1_7_API_VERSION")],
    ),
    window_specialization("float64"),
    window_specialization("int64"),
    window_specialization("uint8"),
    window_specialization("label"),
    Extension(
        name="rustybt.lib.rank",
        sources=["rustybt/lib/rank.pyx"],
        define_macros=[("NPY_NO_DEPRECATED_API", "NPY_1_7_API_VERSION")],
    ),
    # Data
    Extension(
        name="rustybt.data._equities",
        sources=["rustybt/data/_equities.pyx"],
        define_macros=[("NPY_NO_DEPRECATED_API", "NPY_1_7_API_VERSION")],
    ),
    Extension(
        name="rustybt.data._adjustments",
        sources=["rustybt/data/_adjustments.pyx"],
        define_macros=[("NPY_NO_DEPRECATED_API", "NPY_1_7_API_VERSION")],
    ),
    Extension(
        name="rustybt.data._minute_bar_internal",
        sources=["rustybt/data/_minute_bar_internal.pyx"],
        define_macros=[("NPY_NO_DEPRECATED_API", "NPY_1_7_API_VERSION")],
    ),
    Extension(
        name="rustybt.data._resample",
        sources=["rustybt/data/_resample.pyx"],
        define_macros=[("NPY_NO_DEPRECATED_API", "NPY_1_7_API_VERSION")],
    ),
    # Protocol
    Extension(
        name="rustybt._protocol",
        sources=["rustybt/_protocol.pyx"],
        define_macros=[("NPY_NO_DEPRECATED_API", "NPY_1_7_API_VERSION")],
    ),
    # Finance
    Extension(
        name="rustybt.finance._finance_ext",
        sources=["rustybt/finance/_finance_ext.pyx"],
        define_macros=[("NPY_NO_DEPRECATED_API", "NPY_1_7_API_VERSION")],
    ),
    # Gens (simulation engine)
    Extension(
        name="rustybt.gens.sim_engine",
        sources=["rustybt/gens/sim_engine.pyx"],
        define_macros=[("NPY_NO_DEPRECATED_API", "NPY_1_7_API_VERSION")],
    ),
]


def build(setup_kwargs):
    """
    Optional hook for some build frontends. Populates setup_kwargs in-place.
    """
    setup_kwargs.update(default_setup_kwargs())


def default_setup_kwargs():
    """Return the keyword arguments to pass to setuptools.setup()."""
    return {
        "ext_modules": cythonize(ext_modules, **ext_options),
        "rust_extensions": [
            RustExtension(
                "rustybt._rustybt",
                path=str(ROOT_DIR / "rust" / "crates" / "rustybt" / "Cargo.toml"),
                binding=Binding.PyO3,
                debug=False,
            )
        ],
        "include_dirs": [numpy.get_include()],
        "zip_safe": False,
    }


# Always provide setup() so PEP 517 backends (pip/build) pick up extension modules
from setuptools import find_packages, setup

setup(
    packages=find_packages(
        where=".", include=["rustybt*"], exclude=["tests*", "deps*", "docs*", ".bmad-core*"]
    ),
    **default_setup_kwargs(),
)
