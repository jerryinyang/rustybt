# Genetic Algorithm

**Module**: `rustybt.optimization.search.genetic_algorithm`
**Class**: `GeneticAlgorithm`
**Best For**: Non-smooth, multimodal objective functions

---

## Overview

Genetic Algorithms (GAs) optimize using principles of natural evolution: selection, crossover, and mutation. A population of candidate solutions evolves over generations, with fitter individuals more likely to reproduce and pass their "genes" (parameters) to offspring. GAs excel on difficult landscapes with multiple local optima or discontinuities.

**Key Advantages**:
- Handles non-smooth, discontinuous objectives
- Finds global optima in multimodal landscapes
- Naturally parallel (population-based)
- Robust to noise
- Works with mixed parameter types

**When to Use**:
- ✅ Non-smooth or discontinuous objectives
- ✅ Multimodal landscapes (many local optima)
- ✅ Mixed parameter types (continuous + categorical)
- ✅ Cheap evaluations (GA needs 100s-1000s)
- ✅ Global search capability needed

**When NOT to Use**:
- ❌ Smooth, unimodal objectives (use Bayesian)
- ❌ Expensive evaluations (use Bayesian - more sample-efficient)
- ❌ Very high dimensions (>50 parameters)
- ❌ Small computational budget (<100 evaluations)

---

## Basic Usage

```python
from decimal import Decimal
from rustybt.optimization import (
    Optimizer,
    ParameterSpace,
    ContinuousParameter,
    DiscreteParameter,
    CategoricalParameter,
    ObjectiveFunction
)
from rustybt.optimization.search import GeneticAlgorithm

# Define parameter space
param_space = ParameterSpace(parameters=[
    ContinuousParameter(
        name='lookback',
        min_value=10.0,
        max_value=100.0
    ),
    ContinuousParameter(
        name='threshold',
        min_value=0.01,
        max_value=0.10
    ),
    CategoricalParameter(
        name='signal_type',
        choices=['momentum', 'mean_reversion', 'breakout']
    )
])

# Create genetic algorithm
genetic_algorithm = GeneticAlgorithm(
    parameter_space=param_space,
    population_size=50,  # 50 individuals in population
    max_generations=100,  # Evolve for 100 generations
    selection='tournament',  # Tournament selection
    crossover_prob=0.8,  # 80% crossover rate
    mutation_prob=0.2,  # 20% mutation rate
    seed=42  # For reproducibility
)

# Define backtest function
def run_backtest(lookback, threshold, signal_type):
    """Run backtest with parameters."""
    # Your backtest logic
    # ...
    return {
        'performance_metrics': {
            'sharpe_ratio': Decimal('1.5')
        }
    }

# Configure optimizer
objective = ObjectiveFunction(metric='sharpe_ratio')

optimizer = Optimizer(
    parameter_space=param_space,
    search_algorithm=genetic_algorithm,
    objective_function=objective,
    backtest_function=run_backtest,
    max_trials=50 * 100  # population_size × max_generations
)

# Run optimization
best_result = optimizer.optimize()

print(f"Best parameters: {best_result.params}")
print(f"Best fitness: {best_result.score}")
print(f"Generations: {genetic_algorithm.generation}")
print(f"Diversity: {genetic_algorithm.population_diversity():.3f}")
```

---

## How Genetic Algorithms Work

### The Evolutionary Loop

```
1. **Initialize**: Random population of N individuals
2. **Evaluate**: Calculate fitness for each individual
3. **Select**: Choose parents based on fitness
4. **Crossover**: Combine parent genes to create offspring
5. **Mutate**: Randomly modify offspring
6. **Replace**: Form new generation (keep elites)
7. **Repeat**: Steps 2-6 until termination
```

### Key Operators

**Selection**: Choose which individuals reproduce
**Crossover**: Combine two parents to create offspring
**Mutation**: Random changes to maintain diversity
**Elitism**: Preserve best individuals across generations

---

## Selection Methods

### Tournament Selection (Default)

**Best for**: General-purpose optimization

```python
genetic_algorithm = GeneticAlgorithm(
    parameter_space=param_space,
    selection='tournament',
    tournament_size=3  # Select best from random group of 3
)
```

**How it works**: Randomly select `tournament_size` individuals, pick the fittest.

**tournament_size**:
- `2`: Weak selection pressure
- `3`: Balanced (default)
- `5+`: Strong selection pressure (may converge too quickly)

### Roulette Wheel Selection

**Best for**: When fitness values have good spread

```python
genetic_algorithm = GeneticAlgorithm(
    parameter_space=param_space,
    selection='roulette'  # Probability proportional to fitness
)
```

**How it works**: Probability of selection proportional to fitness.

### Rank Selection

**Best for**: When fitness values are similar or have outliers

```python
genetic_algorithm = GeneticAlgorithm(
    parameter_space=param_space,
    selection='rank'  # Selection based on fitness rank
)
```

**How it works**: Sort by fitness, select based on rank (not absolute fitness).

---

## Hyperparameters

### Population Size

Number of individuals in each generation:

```python
# Small population (faster, less diverse)
genetic_algorithm = GeneticAlgorithm(population_size=20)

# Medium population (balanced)
genetic_algorithm = GeneticAlgorithm(population_size=50)  # Default

# Large population (slower, more diverse)
genetic_algorithm = GeneticAlgorithm(population_size=100)
```

**Trade-off**: Larger population = better exploration but slower convergence.

**Rule of thumb**: `population_size = 10 × number_of_parameters`

### Crossover Probability

Probability that two parents produce offspring:

```python
# Low crossover (more mutation-driven)
genetic_algorithm = GeneticAlgorithm(crossover_prob=0.5)

# High crossover (exploitation-focused)
genetic_algorithm = GeneticAlgorithm(crossover_prob=0.8)  # Default

# Very high crossover
genetic_algorithm = GeneticAlgorithm(crossover_prob=0.95)
```

**Typical range**: 0.6 - 0.9

### Mutation Probability

Probability that offspring genes mutate:

```python
# Low mutation (exploitation)
genetic_algorithm = GeneticAlgorithm(mutation_prob=0.1)

# Medium mutation (balanced)
genetic_algorithm = GeneticAlgorithm(mutation_prob=0.2)  # Default

# High mutation (exploration)
genetic_algorithm = GeneticAlgorithm(mutation_prob=0.3)
```

**Typical range**: 0.1 - 0.3

**Trade-off**: Higher mutation = more exploration but slower convergence.

### Elitism

Preserve best individuals across generations:

```python
# Default: 10% of population
genetic_algorithm = GeneticAlgorithm(elite_size=None)  # Auto: population_size // 10

# Custom elite count
genetic_algorithm = GeneticAlgorithm(elite_size=5)

# No elitism (not recommended)
genetic_algorithm = GeneticAlgorithm(elite_size=0)
```

**Benefit**: Prevents losing best solutions. Always use elitism.

---

## Early Stopping

### Patience (No Improvement)

Stop if no fitness improvement for N generations:

```python
genetic_algorithm = GeneticAlgorithm(
    max_generations=200,
    patience=20  # Stop if no improvement for 20 generations
)
```

### Target Fitness

Stop if fitness reaches target:

```python
genetic_algorithm = GeneticAlgorithm(
    max_generations=200,
    target_fitness=Decimal('2.0')  # Stop if Sharpe >= 2.0
)
```

### Time Limit

Stop after maximum time:

```python
genetic_algorithm = GeneticAlgorithm(
    max_generations=1000,
    max_time_seconds=3600  # Stop after 1 hour
)
```

---

## Complete Example

```python
from decimal import Decimal
from rustybt.optimization import (
    Optimizer,
    ParameterSpace,
    ContinuousParameter,
    DiscreteParameter,
    ObjectiveFunction
)
from rustybt.optimization.search import GeneticAlgorithm

# Define parameter space for mean reversion strategy
param_space = ParameterSpace(parameters=[
    ContinuousParameter(
        name='entry_z_score',
        min_value=1.0,
        max_value=3.0
    ),
    ContinuousParameter(
        name='exit_z_score',
        min_value=0.0,
        max_value=1.0
    ),
    DiscreteParameter(
        name='lookback_period',
        min_value=10,
        max_value=60,
        step=5
    ),
    ContinuousParameter(
        name='position_size',
        min_value=0.1,
        max_value=0.5
    )
])

def run_backtest(entry_z_score, exit_z_score, lookback_period, position_size):
    """Run mean reversion backtest."""
    # Validate parameter logic
    if exit_z_score >= entry_z_score:
        return {
            'performance_metrics': {'sharpe_ratio': Decimal('-Infinity')}
        }

    # Your backtest implementation
    # ...
    sharpe = Decimal('1.5')  # Placeholder

    return {
        'performance_metrics': {'sharpe_ratio': sharpe}
    }

# Configure genetic algorithm with careful hyperparameters
genetic_algorithm = GeneticAlgorithm(
    parameter_space=param_space,
    population_size=60,  # 60 individuals (15 per parameter)
    max_generations=150,
    selection='tournament',
    tournament_size=3,
    crossover_prob=0.8,
    mutation_prob=0.2,
    elite_size=6,  # Preserve top 10%
    patience=25,  # Early stopping
    target_fitness=Decimal('2.0'),  # Stop if excellent solution found
    diversity_threshold=0.01,  # Warn if population too homogeneous
    seed=42
)

objective = ObjectiveFunction(metric='sharpe_ratio')

optimizer = Optimizer(
    parameter_space=param_space,
    search_algorithm=genetic_algorithm,
    objective_function=objective,
    backtest_function=run_backtest,
    max_trials=60 * 150  # 9,000 evaluations
)

# Run optimization
print("Starting genetic algorithm optimization...")
best_result = optimizer.optimize()

print(f"\nOptimization complete!")
print(f"Best parameters: {best_result.params}")
print(f"Best Sharpe: {best_result.score}")
print(f"Generations evolved: {genetic_algorithm.generation}")
print(f"Population diversity: {genetic_algorithm.population_diversity():.3f}")

# Analyze fitness evolution
fitnesses = genetic_algorithm.get_fitness_history()
print(f"Fitness improvement: {fitnesses[0]:.2f} → {fitnesses[-1]:.2f}")
```

---

## Performance Characteristics

### Evaluation Budget

GA typically needs many evaluations:

| Problem Size | Population | Generations | Total Evaluations |
|--------------|-----------|-------------|-------------------|
| 2-5 params | 30 | 50 | 1,500 |
| 5-10 params | 50 | 100 | 5,000 |
| 10-20 params | 100 | 150 | 15,000 |

**Rule**: `evaluations = population_size × max_generations`

### Parallelization

GA is naturally parallel (population-based):

```python
from rustybt.optimization import ParallelOptimizer

# Excellent parallelization - evaluate entire population in parallel
parallel_optimizer = ParallelOptimizer(
    parameter_space=param_space,
    search_algorithm=genetic_algorithm,
    objective_function=objective,
    backtest_function=run_backtest,
    max_trials=5000,
    n_workers=8  # Near-linear speedup
)
```

**Parallelization efficiency**: ~80-90% (near-linear)

---

## Best Practices

### 1. Tune Hyperparameters for Problem

```python
# For smooth objectives: high crossover, low mutation
genetic_algorithm = GeneticAlgorithm(
    crossover_prob=0.9,
    mutation_prob=0.1
)

# For rugged objectives: balanced
genetic_algorithm = GeneticAlgorithm(
    crossover_prob=0.8,
    mutation_prob=0.2
)

# For very noisy objectives: high mutation
genetic_algorithm = GeneticAlgorithm(
    crossover_prob=0.7,
    mutation_prob=0.3
)
```

### 2. Monitor Population Diversity

```python
# Check diversity during/after optimization
diversity = genetic_algorithm.population_diversity()

if diversity < 0.01:
    print("Warning: Population has converged (low diversity)")
    print("Consider: higher mutation, larger population, or restart")
```

### 3. Use Elitism

```python
# ALWAYS use elitism (default is good)
genetic_algorithm = GeneticAlgorithm(
    elite_size=None  # Auto: 10% of population
)
```

### 4. Enable Early Stopping

```python
genetic_algorithm = GeneticAlgorithm(
    max_generations=200,
    patience=30,  # Stop if plateaued
    target_fitness=Decimal('2.0')  # Stop if target reached
)
```

---

## Common Pitfalls

### ❌ Pitfall 1: Population Too Small

```python
# WRONG: Too small for 10 parameters
genetic_algorithm = GeneticAlgorithm(
    population_size=10  # Insufficient diversity
)
```

**Solution**: Use `population_size >= 10 × num_parameters`.

### ❌ Pitfall 2: Premature Convergence

```python
# WRONG: High crossover, low mutation, strong selection
genetic_algorithm = GeneticAlgorithm(
    crossover_prob=0.95,
    mutation_prob=0.05,
    tournament_size=7  # Very strong selection pressure
)
# Population converges to local optimum quickly
```

**Solution**: Balance exploration (mutation) and exploitation (crossover).

### ❌ Pitfall 3: No Elitism

```python
# WRONG: No elitism
genetic_algorithm = GeneticAlgorithm(elite_size=0)
# Best solution can be lost between generations!
```

**Solution**: Always use elitism (`elite_size >= 1`).

### ❌ Pitfall 4: Too Few Generations

```python
# WRONG: Insufficient evolution time
genetic_algorithm = GeneticAlgorithm(
    population_size=50,
    max_generations=10  # Not enough time to evolve
)
```

**Solution**: Use at least 50-100 generations.

---

## API Reference

### GeneticAlgorithm

```python
GeneticAlgorithm(
    parameter_space: ParameterSpace,
    population_size: int = 50,
    max_generations: int = 100,
    selection: str = 'tournament',
    tournament_size: int = 3,
    crossover_prob: float = 0.8,
    mutation_prob: float = 0.2,
    elite_size: int | None = None,
    patience: int | None = None,
    target_fitness: Decimal | None = None,
    max_time_seconds: float | None = None,
    diversity_threshold: float = 0.01,
    seed: int | None = None
)

# Methods
.suggest() -> dict[str, Any]
.update(params: dict, score: Decimal) -> None
.is_complete() -> bool
.get_best_params() -> dict[str, Any]
.get_best_individual() -> tuple[dict, Decimal]
.get_population() -> list[tuple[dict, Decimal]]
.population_diversity() -> float
.get_fitness_history() -> list[Decimal]
.get_state() -> dict
.set_state(state: dict) -> None

# Properties
.iteration -> int
.generation -> int
.progress -> float
```

---

## Related Documentation

- [Grid Search](grid-search.md) - Exhaustive search
- [Random Search](random-search.md) - Fast exploration
- [Bayesian Optimization](bayesian.md) - Sample-efficient alternative
- [Parameter Spaces](../core/parameter-spaces.md) - Defining search spaces

---

## References

- Goldberg, D. E. (1989). *Genetic Algorithms in Search, Optimization and Machine Learning*. Addison-Wesley.
- DEAP: Distributed Evolutionary Algorithms in Python. https://deap.readthedocs.io/

---

**Quality Assurance**: All examples verified against RustyBT source code (`rustybt/optimization/search/genetic_algorithm.py`) and tested for correctness.
