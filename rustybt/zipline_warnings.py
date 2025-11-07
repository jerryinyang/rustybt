#
# Copyright 2016 Quantopian, Inc.
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
"""Custom warning categories for rustybt deprecations and changes."""


class ZiplineDeprecationWarning(DeprecationWarning):
    """Warning for deprecated rustybt/zipline features.

    This warning is used to indicate that a feature or API is deprecated
    and will be removed in a future version. Users should update their
    code to use the recommended alternatives.
    """
    pass
