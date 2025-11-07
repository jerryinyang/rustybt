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
"""Thread-local storage for the current algorithm instance.

This module provides a thread-safe way to access the currently executing
algorithm instance. This is useful for API functions that need access to
the algorithm context without explicit parameter passing.
"""
import threading
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from rustybt.algorithm import TradingAlgorithm

context = threading.local()


def get_algo_instance() -> "TradingAlgorithm | None":
    """Get the current algorithm instance from thread-local storage.

    Returns:
        The current TradingAlgorithm instance, or None if not set.
    """
    return getattr(context, "algorithm", None)


def set_algo_instance(algo: Any) -> None:
    """Set the current algorithm instance in thread-local storage.

    Args:
        algo: The TradingAlgorithm instance to store.
    """
    context.algorithm = algo
