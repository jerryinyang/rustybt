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

"""Futures contract month code mappings.

This module provides standardized month code mappings used for futures contract symbols.
The CME (Chicago Mercantile Exchange) month codes are the industry standard for representing
contract expiration months in futures symbols.

The month codes follow the CME standard where each letter represents a specific month:

- F: January
- G: February
- H: March
- J: April
- K: May
- M: June
- N: July
- Q: August
- U: September
- V: October
- X: November
- Z: December

Note that the letters I, L, O, S, and W are intentionally omitted to avoid confusion
with numbers and other letters.

Examples:
    Converting month to CME code:
        >>> from rustybt.assets.futures import MONTH_TO_CMES_CODE
        >>> MONTH_TO_CMES_CODE[3]  # March
        'H'
        >>> MONTH_TO_CMES_CODE[12]  # December
        'Z'

    Converting CME code to month:
        >>> from rustybt.assets.futures import CMES_CODE_TO_MONTH
        >>> CMES_CODE_TO_MONTH['H']  # March
        3
        >>> CMES_CODE_TO_MONTH['Z']  # December
        12

    Constructing a futures symbol:
        >>> root = "ES"  # E-mini S&P 500
        >>> year = "24"
        >>> month_code = MONTH_TO_CMES_CODE[6]  # June
        >>> symbol = f"{root}{month_code}{year}"
        >>> print(symbol)
        ESM24

See Also:
    CME Month Codes: https://www.cmegroup.com/month-codes.html
"""

# CME standard month code to month number mapping (1-12)
CMES_CODE_TO_MONTH = dict(zip("FGHJKMNQUVXZ", range(1, 13), strict=False))

# Reverse mapping: month number (1-12) to CME code
MONTH_TO_CMES_CODE = dict(zip(range(1, 13), "FGHJKMNQUVXZ", strict=False))
