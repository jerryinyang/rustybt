#!/usr/bin/env python
#
# Copyright 2014 Quantopian, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import numpy
from Cython.Build import cythonize
from setuptools import Extension, setup  # noqa: E402


def window_specialization(typename):
    """Make an extension for an AdjustedArrayWindow specialization."""
    return Extension(
        name=f"rustybt.lib._{typename}window",
        sources=[f"rustybt/lib/_{typename}window.pyx"],
        depends=["rustybt/lib/_windowtemplate.pxi"],
        define_macros=[("NPY_NO_DEPRECATED_API", "NPY_1_7_API_VERSION")],
    )


ext_options = dict(
    compiler_directives=dict(profile=True, language_level="3"),
    annotate=True,
)
ext_modules = [
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
    window_specialization("int64"),
    window_specialization("uint8"),
    window_specialization("label"),
    Extension(
        name="rustybt.lib.rank",
        sources=["rustybt/lib/rank.pyx"],
        define_macros=[("NPY_NO_DEPRECATED_API", "NPY_1_7_API_VERSION")],
    ),
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
        name="rustybt._protocol",
        sources=["rustybt/_protocol.pyx"],
        define_macros=[("NPY_NO_DEPRECATED_API", "NPY_1_7_API_VERSION")],
    ),
    Extension(
        name="rustybt.finance._finance_ext",
        sources=["rustybt/finance/_finance_ext.pyx"],
        define_macros=[("NPY_NO_DEPRECATED_API", "NPY_1_7_API_VERSION")],
    ),
    Extension(
        name="rustybt.gens.sim_engine",
        sources=["rustybt/gens/sim_engine.pyx"],
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
]
# for ext_module in ext_modules:
#     ext_module.cython_directives = dict(language_level="3")

setup(
    use_scm_version=True,
    ext_modules=cythonize(ext_modules, **ext_options),
    include_dirs=[numpy.get_include()],
)
