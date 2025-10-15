# License

RustyBT is licensed under the **Apache License, Version 2.0**.

## Apache License 2.0

```
Copyright 2024 RustyBT Contributors
Copyright 2023 Stefan Jansen
Copyright 2016 Quantopian, Inc.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
```

## Full License Text

See the [LICENSE](https://github.com/jerryinyang/rustybt/blob/main/LICENSE) file in the repository for the complete license text.

## Third-Party Licenses

RustyBT incorporates code from:

### Zipline & Zipline-Reloaded

- **License**: Apache License 2.0
- **Authors**: Quantopian Inc., Stefan Jansen
- **Repository**: [zipline-reloaded](https://github.com/stefan-jansen/zipline-reloaded)

### Known LGPL Dependencies

While RustyBT follows an **Apache 2.0/MIT-only dependency policy**, the following LGPL dependencies currently exist as transitive dependencies:

| Package | License | Type | Source | Status |
|---------|---------|------|--------|--------|
| `frozendict` | LGPL v3 | Production | Via `yfinance` (Yahoo Finance data) | Tracked for replacement |
| `chardet` | LGPL | Development | Via `tox` (testing tool) | Tracked for replacement |

**Legal Status**: LGPL allows use as a dynamically-linked library without GPL license contamination. RustyBT's Apache 2.0 license remains unaffected.

**Mitigation Plans**:
- **frozendict**: Evaluating alternative data providers or forking `yfinance` with MIT-licensed replacement
- **chardet**: Considering migration from `tox` to modern alternatives (`nox`, `hatch`)

## Contributing

By contributing to RustyBT, you agree that your contributions will be licensed under the Apache License 2.0. See [Contributing Guide](contributing.md) for more information.
