# Random Search Algorithm

Random sampling-based optimization for large parameter spaces.

## Overview

Random search randomly samples parameter combinations from the search space. Despite its simplicity, it often outperforms grid search for high-dimensional problems and serves as an excellent baseline for more sophisticated algorithms.

## When to Use

✅ **Use random search when**:
- Parameter space is large or high-dimensional
- Initial exploration phase
- Need a fast baseline for comparison
- Grid search would take too long
- Some parameters more important than others

❌ **Don't use random search when**:
- Parameter space is small (<100 combinations) - use grid search
- Need deterministic, reproducible results - use grid search
- Sample efficiency critical - use Bayesian optimization
- Budget allows sophisticated methods

## See Also

- [Grid Search](grid-search.md)
- [Bayesian Optimization](bayesian.md)
- [Parameter Spaces](../framework/parameter-spaces.md)
- [Parallel Processing](../parallel/multiprocessing.md)
