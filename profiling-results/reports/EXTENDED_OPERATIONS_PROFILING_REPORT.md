# Extended Heavy Operations Profiling Report

**Generated**: 2025-10-22T18:59:03.809502Z
**Story**: X4.1 - Setup and Validation Infrastructure
**Acceptance Criteria**: AC2 - Heavy Operation Profiling

---

## Scenario 1: Batch Initialization Profiling

### Summary

Profiled batch initialization across varying bundle sizes (10-500 assets) with 100 backtests each.

| Assets | Total Time (s) | CPU Time (s) | Avg Init Time (ms) |
|--------|----------------|--------------|--------------------|
|   10 |         0.100 |       0.517 | TBD                |
|   50 |         0.155 |       0.568 | TBD                |
|  100 |         0.230 |       0.655 | TBD                |
|  500 |         0.892 |       1.311 | TBD                |

## Scenario 2: Parallel Coordinator Efficiency

### Summary

Profiled parallel coordinator at different worker counts (2-16 workers) with 100 tasks each.

| Workers | Total Time (s) | CPU Time (s) | Throughput (tasks/s) |
|---------|----------------|--------------|----------------------|
|       2 |         2.649 |       0.021 | TBD                  |
|       4 |         2.433 |       0.022 | TBD                  |
|       8 |         2.784 |       0.042 | TBD                  |
|      16 |         5.009 |       0.089 | TBD                  |

## Scenario 3: GridSearch Optimization

### Summary

- **Total Time**: 0.079s
- **CPU Time**: 0.164s
- **Note**: BOHB not implemented - comparison deferred

## Scenario 4: Missing Components

### BOHB

BOHB (Bayesian Optimization and HyperBand) multi-fidelity optimization not implemented. Would require HpBandSter library integration. Comparison with GridSearch deferred to future story.

### Ray

Ray distributed scheduler not implemented. Currently using multiprocessing.Pool for parallelization. Ray vs multiprocessing comparison deferred to future story when Ray integration is added.

## Flame Graph Visualizations

Flame graphs generated for all scenarios in: `profiling-results/flame_graphs/`

### Batch Initialization
- `batch_init_10_assets.svg`
- `batch_init_50_assets.svg`
- `batch_init_100_assets.svg`
- `batch_init_500_assets.svg`

### Parallel Coordinator
- `parallel_coord_2_workers.svg`
- `parallel_coord_4_workers.svg`
- `parallel_coord_8_workers.svg`
- `parallel_coord_16_workers.svg`

### GridSearch
- `grid_search_optimization.svg`

## Recommendations for Future Stories

1. **BOHB Integration**: Implement BOHB multi-fidelity optimization for comparison with GridSearch
2. **Ray Integration**: Add Ray distributed scheduler for comparison with multiprocessing.Pool
3. **Bundle Loading Optimization**: Profile shows potential overhead in bundle initialization
4. **Parallel Coordinator Tuning**: Analyze worker utilization and coordination overhead
