# Genetic Algorithm Optimization

Evolutionary optimization using population-based search and genetic operators.

## Overview

Genetic algorithms (GA) use principles from biological evolution to search parameter spaces. They maintain a population of candidate solutions and evolve them through selection, crossover, and mutation operations.

## When to Use

✅ **Use genetic algorithms when**:
- Objective function is non-smooth or discontinuous
- Parameter space has many local optima
- Parameters are discrete or categorical
- You want population-based diversity
- Parallel evaluation is beneficial

❌ **Don't use genetic algorithms when**:
- Parameter space is smooth and continuous (use Bayesian instead)
- You need deterministic results
- Population size would be too large for computational budget
- Objective function is very noisy

## Basic Usage

```python
from rustybt.optimization.search import GeneticAlgorithm
from rustybt.optimization.parameter_space import ParameterSpace, DiscreteParameter

# Define parameter space
param_space = ParameterSpace(parameters=[
    DiscreteParameter('lookback', 10, 100, step=5),
    DiscreteParameter('threshold_x100', 1, 10, step=1)  # Will divide by 100
])

# Create genetic algorithm
ga = GeneticAlgorithm(
    parameter_space=param_space,
    population_size=50,
    n_generations=100,
    mutation_rate=0.1,
    crossover_rate=0.7
)

# Optimization loop
while not ga.is_complete():
    params = ga.suggest()
    score = run_backtest(params)
    ga.update(params, score)

# Get best parameters
best_params = ga.get_best_params()
```

## Constructor

```python
GeneticAlgorithm(
    parameter_space: ParameterSpace,
    population_size: int = 50,
    n_generations: int = 100,
    mutation_rate: float = 0.1,
    crossover_rate: float = 0.7,
    tournament_size: int = 3,
    elitism_count: int = 2,
    random_seed: Optional[int] = None
)
```

**Parameters**:
- `parameter_space`: Parameter space to search
- `population_size`: Number of individuals per generation
- `n_generations`: Number of generations to evolve
- `mutation_rate`: Probability of mutation (0.0-1.0)
- `crossover_rate`: Probability of crossover (0.0-1.0)
- `tournament_size`: Number of individuals in tournament selection
- `elitism_count`: Top individuals preserved each generation
- `random_seed`: Random seed for reproducibility

## Key Concepts

### Population

A collection of candidate solutions (individuals).

```python
# Generation 0 (initial population):
population = [
    {'lookback': 20, 'threshold': 0.05},
    {'lookback': 50, 'threshold': 0.03},
    {'lookback': 30, 'threshold': 0.07},
    # ... 47 more individuals
]
```

### Fitness

Score assigned to each individual (Sharpe ratio, profit, etc.).

```python
fitness = [
    ('individual_1', Decimal('1.5')),
    ('individual_2', Decimal('2.1')),
    ('individual_3', Decimal('0.8')),
    # ...
]
```

### Selection

Choosing individuals for reproduction (tournament selection).

```python
def tournament_selection(population, fitness, tournament_size=3):
    """Select individual via tournament."""
    tournament = random.sample(list(zip(population, fitness)), tournament_size)
    winner = max(tournament, key=lambda x: x[1])
    return winner[0]
```

### Crossover

Combining two parents to create offspring.

```python
def crossover(parent1, parent2):
    """Single-point crossover."""
    offspring = {}
    for param in parent1.keys():
        # Random choice from each parent
        if random.random() < 0.5:
            offspring[param] = parent1[param]
        else:
            offspring[param] = parent2[param]
    return offspring
```

### Mutation

Random changes to individual parameters.

```python
def mutate(individual, mutation_rate=0.1):
    """Mutate individual parameters."""
    mutated = individual.copy()
    for param in mutated.keys():
        if random.random() < mutation_rate:
            # Random valid value for this parameter
            mutated[param] = sample_random_value(param)
    return mutated
```

### Elitism

Preserving best individuals unchanged.

```python
# Top 2 individuals pass to next generation unchanged
elites = sorted(population, key=lambda x: fitness[x], reverse=True)[:2]
```

## Complete Example

```python
from decimal import Decimal
from rustybt.optimization.search import GeneticAlgorithm
from rustybt.optimization.parameter_space import (
    ParameterSpace,
    DiscreteParameter,
    CategoricalParameter
)

# Define parameter space
param_space = ParameterSpace(parameters=[
    DiscreteParameter('ma_short', 10, 50, step=5),
    DiscreteParameter('ma_long', 50, 200, step=25),
    CategoricalParameter('signal_type', ['momentum', 'mean_reversion'])
])

# Create genetic algorithm
ga = GeneticAlgorithm(
    parameter_space=param_space,
    population_size=40,
    n_generations=50,
    mutation_rate=0.15,  # 15% mutation rate
    crossover_rate=0.75,  # 75% crossover rate
    tournament_size=3,
    elitism_count=2,  # Keep top 2 individuals
    random_seed=42
)

print("Starting genetic algorithm optimization...")
print(f"Population size: {ga.population_size}")
print(f"Generations: {ga.n_generations}")

generation = 0
while not ga.is_complete():
    params = ga.suggest()
    score = run_backtest(params)
    ga.update(params, score)

    # Print progress each generation
    if ga.current_individual == 0:  # New generation started
        generation += 1
        best_score = ga.get_best_score()
        avg_score = ga.get_average_fitness()
        print(f"Generation {generation}/{ga.n_generations}: "
              f"Best={best_score:.3f}, Avg={avg_score:.3f}")

# Get results
best_params = ga.get_best_params()
best_score = ga.get_best_score()

print(f"\n=== Optimization Complete ===")
print(f"Best Sharpe: {best_score:.3f}")
print(f"Best Parameters: {best_params}")

# Get population diversity
diversity = ga.get_population_diversity()
print(f"Final diversity: {diversity:.2f}")
```

## Tuning Parameters

### Population Size

**Rule of thumb**: 20-100 individuals

```python
# Small spaces
population_size = 20

# Medium spaces
population_size = 50

# Large spaces or complex problems
population_size = 100
```

**Trade-offs**:
- Larger = better exploration but slower
- Smaller = faster but may miss solutions

### Mutation Rate

**Rule of thumb**: 0.05-0.20 (5-20%)

```python
# Low mutation (exploitation)
mutation_rate = 0.05

# Medium mutation (balanced)
mutation_rate = 0.10

# High mutation (exploration)
mutation_rate = 0.20
```

**Trade-offs**:
- Higher = more exploration, slower convergence
- Lower = faster convergence, may get stuck

### Crossover Rate

**Rule of thumb**: 0.60-0.90 (60-90%)

```python
# Low crossover
crossover_rate = 0.60

# Medium crossover
crossover_rate = 0.70

# High crossover
crossover_rate = 0.90
```

**Trade-offs**:
- Higher = more recombination of good traits
- Lower = more mutation-driven evolution

### Tournament Size

**Rule of thumb**: 2-5

```python
# Weak selection pressure
tournament_size = 2

# Medium selection pressure
tournament_size = 3

# Strong selection pressure
tournament_size = 5
```

**Trade-offs**:
- Larger = stronger selection pressure, faster convergence
- Smaller = weaker selection, more diversity

### Elitism Count

**Rule of thumb**: 1-5% of population

```python
# Small elitism
elitism_count = 1

# Medium elitism (2-5% of population)
elitism_count = 2  # For population of 50

# Large elitism
elitism_count = 5
```

**Trade-offs**:
- More elites = preserves best solutions better
- Fewer elites = more diversity, slower convergence

## Visualization

### Convergence Plot

```python
import matplotlib.pyplot as plt

def plot_ga_convergence(ga):
    """Plot best and average fitness over generations."""
    history = ga.get_history()

    best_fitness = [gen['best_fitness'] for gen in history]
    avg_fitness = [gen['avg_fitness'] for gen in history]
    generations = range(1, len(history) + 1)

    plt.figure(figsize=(12, 6))
    plt.plot(generations, best_fitness, 'b-', linewidth=2, label='Best')
    plt.plot(generations, avg_fitness, 'g--', linewidth=2, label='Average')
    plt.xlabel('Generation')
    plt.ylabel('Fitness (Sharpe Ratio)')
    plt.title('Genetic Algorithm Convergence')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()
```

### Population Diversity

```python
def plot_population_diversity(ga):
    """Plot population diversity over generations."""
    history = ga.get_history()

    diversity = [gen['diversity'] for gen in history]
    generations = range(1, len(history) + 1)

    plt.figure(figsize=(12, 6))
    plt.plot(generations, diversity, 'r-', linewidth=2)
    plt.xlabel('Generation')
    plt.ylabel('Population Diversity')
    plt.title('Population Diversity Over Generations')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()
```

### Fitness Distribution

```python
def plot_fitness_distribution(ga):
    """Plot fitness distribution in final generation."""
    final_fitness = ga.get_final_population_fitness()

    plt.figure(figsize=(10, 6))
    plt.hist(final_fitness, bins=20, alpha=0.7, edgecolor='black')
    plt.axvline(ga.get_best_score(), color='r', linestyle='--',
                linewidth=2, label='Best')
    plt.axvline(ga.get_average_fitness(), color='g', linestyle='--',
                linewidth=2, label='Average')
    plt.xlabel('Fitness (Sharpe Ratio)')
    plt.ylabel('Count')
    plt.title('Final Population Fitness Distribution')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()
```

## Advanced Techniques

### Adaptive Mutation

Adjust mutation rate based on diversity:

```python
class AdaptiveGeneticAlgorithm(GeneticAlgorithm):
    def update(self, params, score):
        super().update(params, score)

        # Increase mutation if diversity too low
        diversity = self.get_population_diversity()
        if diversity < 0.1:
            self.mutation_rate = min(0.3, self.mutation_rate * 1.5)
        else:
            self.mutation_rate = max(0.05, self.mutation_rate * 0.95)
```

### Multi-Objective Optimization

Optimize multiple objectives:

```python
def multi_objective_fitness(params):
    """Return tuple of (sharpe, -max_drawdown)."""
    result = run_backtest(params)
    return (result['sharpe'], -abs(result['max_drawdown']))

# Use Pareto ranking
ga = GeneticAlgorithm(
    parameter_space=param_space,
    fitness_function=multi_objective_fitness,
    selection='pareto'  # Pareto-based selection
)
```

### Island Model

Multiple populations evolving independently with migration:

## Best Practices

### 1. Start with Standard Settings

```python
ga = GeneticAlgorithm(
    parameter_space=param_space,
    population_size=50,      # Standard
    n_generations=100,       # Standard
    mutation_rate=0.1,       # 10%
    crossover_rate=0.7,      # 70%
    tournament_size=3,       # Standard
    elitism_count=2          # Top 2
)
```

### 2. Monitor Convergence

```python
# Stop if no improvement for 20 generations
ga = GeneticAlgorithm(
    ...,
    early_stopping_generations=20
)
```

### 3. Use Seeding for Warm Start

```python
# Seed with known good solutions
initial_population = [
    {'lookback': 30, 'threshold': 0.05},  # From previous optimization
    {'lookback': 50, 'threshold': 0.03},  # Domain knowledge
]

ga = GeneticAlgorithm(
    ...,
    initial_population=initial_population
)
```

### 4. Balance Exploration and Exploitation

```python
# Early: High exploration
ga_phase1 = GeneticAlgorithm(
    ...,
    mutation_rate=0.20,  # High mutation
    crossover_rate=0.60,  # Low crossover
    n_generations=50
)

# Late: High exploitation
ga_phase2 = GeneticAlgorithm(
    ...,
    mutation_rate=0.05,  # Low mutation
    crossover_rate=0.90,  # High crossover
    n_generations=50,
    initial_population=ga_phase1.get_final_population()
)
```

## Comparison with Other Algorithms

| Aspect | Genetic | Grid | Random | Bayesian |
|--------|---------|------|--------|----------|
| **Handles discontinuities** | Excellent | Good | Good | Poor |
| **Handles categorical** | Excellent | Excellent | Excellent | Poor |
| **Sample efficiency** | Medium | Low | Low | High |
| **Parallelizable** | Excellent | Excellent | Excellent | Limited |
| **Deterministic** | No | Yes | No | No |
| **Convergence speed** | Medium | Slow | Fast | Fast |

## Common Pitfalls

### ❌ Population Too Small

```python
# Bad: Only 10 individuals for 5 parameters
ga = GeneticAlgorithm(population_size=10, ...)

# Good: ~10 individuals per parameter
ga = GeneticAlgorithm(population_size=50, ...)
```

### ❌ Mutation Too High

```python
# Bad: 50% mutation destroys good solutions
ga = GeneticAlgorithm(mutation_rate=0.5, ...)

# Good: 10-20% mutation
ga = GeneticAlgorithm(mutation_rate=0.1, ...)
```

### ❌ No Elitism

```python
# Bad: Best solutions can be lost
ga = GeneticAlgorithm(elitism_count=0, ...)

# Good: Preserve top solutions
ga = GeneticAlgorithm(elitism_count=2, ...)
```

### ❌ Premature Convergence

```python
# Bad: Too strong selection pressure
ga = GeneticAlgorithm(tournament_size=10, mutation_rate=0.01, ...)

# Good: Balanced selection
ga = GeneticAlgorithm(tournament_size=3, mutation_rate=0.1, ...)
```

## Dependencies

Requires `deap` package:

```bash
pip install deap
```

## See Also

- [Grid Search](grid-search.md)
- [Bayesian Optimization](bayesian.md)
- [Parameter Spaces](../framework/parameter-spaces.md)
- [Parallel Processing](../parallel/multiprocessing.md)
