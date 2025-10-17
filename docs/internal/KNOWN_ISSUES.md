# Known Issues

## Documentation Build

### Pydantic V2 Deprecation Warning in mkdocstrings

**Status**: Informational only - No action required

**Issue**: During `mkdocs build`, an INFO-level message appears:

```
INFO - PydanticDeprecatedSince20: Using extra keyword arguments on `Field` is deprecated...
```

**Source**: `mkdocstrings-python` v1.18.2 (third-party dependency)

**Impact**: None
- Build completes successfully
- Documentation quality unaffected
- `--strict` mode passes (only blocks on WARNING/ERROR)
- Future deprecation notice (won't break until Pydantic V3)

**Resolution**:
- No action needed from our side
- Will be fixed in future mkdocstrings-python release
- Monitor upstream: https://github.com/mkdocstrings/python

**Workaround** (optional): Filter the message during CI/CD:
```bash
mkdocs build --strict 2>&1 | grep -v "PydanticDeprecatedSince20"
```

**Last Checked**: 2025-10-17
**Dependencies**: mkdocstrings 0.30.1, mkdocstrings-python 1.18.2
