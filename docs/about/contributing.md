# Contributing to RustyBT

We welcome contributions to RustyBT! This guide will help you get started.

## Code of Conduct

By participating in this project, you agree to maintain a respectful and inclusive environment for all contributors.

## How to Contribute

### Reporting Bugs

1. Check if the bug has already been reported in [GitHub Issues](https://github.com/jerryinyang/rustybt/issues)
2. If not, create a new issue with:
   - Clear title and description
   - Steps to reproduce
   - Expected vs. actual behavior
   - Environment details (OS, Python version, RustyBT version)

### Suggesting Enhancements

1. Check [GitHub Discussions](https://github.com/jerryinyang/rustybt/discussions) for similar ideas
2. Create a new discussion or issue describing:
   - The problem you're trying to solve
   - Your proposed solution
   - Any alternative approaches considered

### Contributing Code

#### Development Setup

1. **Fork and Clone**
   ```bash
   git clone https://github.com/YOUR_USERNAME/rustybt.git
   cd rustybt
   ```

2. **Install Development Dependencies**
   ```bash
   # Using uv (recommended)
   uv sync --all-extras

   # Or using pip
   pip install -e ".[dev,test]"
   ```

3. **Install Pre-commit Hooks**
   ```bash
   pre-commit install
   ```

#### Development Workflow

1. **Create a Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make Changes**
   - Follow PEP 8 and project conventions
   - Write tests for new functionality
   - Update documentation as needed

3. **Run Tests**
   ```bash
   # Run full test suite
   pytest tests/ -v

   # Run with coverage
   pytest tests/ --cov=rustybt --cov-report=html

   # Run specific tests
   pytest tests/finance/test_decimal_ledger.py
   ```

4. **Code Quality Checks**
   ```bash
   # Format code
   black rustybt/ tests/

   # Lint code
   ruff check rustybt/ tests/

   # Type check
   mypy rustybt/ --strict
   ```

5. **Commit Changes**
   ```bash
   git add .
   git commit -m "feat: add your feature description"
   ```

   Follow [Conventional Commits](https://www.conventionalcommits.org/):
   - `feat:` - New feature
   - `fix:` - Bug fix
   - `docs:` - Documentation changes
   - `test:` - Test changes
   - `refactor:` - Code refactoring
   - `perf:` - Performance improvements

6. **Push and Create Pull Request**
   ```bash
   git push origin feature/your-feature-name
   ```

   Then create a pull request on GitHub with:
   - Clear description of changes
   - Related issue numbers
   - Test results

## Development Guidelines

### Testing Standards

- **Zero-Mock Policy**: We prefer integration tests over mocks whenever possible
- **Property-Based Testing**: Use Hypothesis for financial calculations
- **Coverage Target**: Aim for 90%+ test coverage

### Code Style

- Follow [PEP 8](https://peps.python.org/pep-0008/)
- Use type hints (Python 3.12+)
- Write docstrings in Google style
- Keep functions focused and small

### Documentation

- Update user guides for user-facing changes
- Update architecture docs for design changes
- Add code examples for new features
- Keep API documentation current

## Project Structure

```
rustybt/
├── rustybt/          # Source code
│   ├── finance/      # Financial calculations
│   ├── data/         # Data management
│   ├── live/         # Live trading
│   └── ...
├── tests/            # Test suite
├── docs/             # Documentation
├── examples/         # Example strategies
└── benchmarks/       # Performance benchmarks
```

## Areas for Contribution

### High Priority

- Broker adapter implementations
- Data source adapters
- Performance optimizations
- Documentation improvements
- Bug fixes

### Medium Priority

- New order types
- Additional metrics
- UI/visualization improvements
- Example strategies

### Research/Experimental

- Rust module implementations
- Machine learning integrations
- Alternative data sources
- Advanced analytics

## Questions?

- **GitHub Discussions**: For general questions and ideas
- **GitHub Issues**: For bugs and feature requests
- **Documentation**: Check the [User Guides](../guides/decimal-precision-configuration.md) and [Examples](../examples/README.md)

## License

By contributing, you agree that your contributions will be licensed under the Apache License 2.0. See [License](license.md) for details.

## Acknowledgments

Thank you for contributing to RustyBT! Every contribution helps make algorithmic trading more accessible and robust.
