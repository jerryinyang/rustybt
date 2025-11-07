"""Pipeline API for computing cross-sectional factors, filters, and classifiers.

The Pipeline API provides a declarative framework for computing multi-asset
computations over historical data. Pipelines consist of Terms that represent
computational expressions, and the engine executes these terms efficiently
by managing dependencies and minimizing redundant computations.

Core Components:
    - Pipeline: Container for named expressions to be computed
    - Factor: Numerical computation producing float/datetime values
    - Filter: Boolean computation for asset selection
    - Classifier: Categorical computation producing discrete labels
    - Domain: Defines the calendar and asset universe for computations
    - SimplePipelineEngine: Executes pipeline computations

Basic Usage Example:
    >>> from rustybt.pipeline import Pipeline, SimplePipelineEngine
    >>> from rustybt.pipeline.factors import SimpleMovingAverage
    >>> from rustybt.pipeline.data import EquityPricing
    >>>
    >>> # Create a pipeline with a simple moving average
    >>> pipe = Pipeline()
    >>> sma_10 = SimpleMovingAverage(
    ...     inputs=[EquityPricing.close],
    ...     window_length=10
    ... )
    >>> pipe.add(sma_10, name='sma_10')
    >>>
    >>> # Run the pipeline
    >>> engine = SimplePipelineEngine(...)  # Configure with loader and finder
    >>> result = engine.run_pipeline(pipe, start_date, end_date)

The Pipeline framework automatically:
    - Resolves dependencies between terms
    - Loads required data efficiently
    - Handles missing data and asset lifetimes
    - Optimizes memory usage during computation

See Also:
    Pipeline: Main pipeline container class
    SimplePipelineEngine: Engine for executing pipelines
    Factor: Numerical computations
    Filter: Boolean asset selections
    Classifier: Categorical groupings
"""
from .classifiers import Classifier, CustomClassifier
from .domain import Domain

# NOTE: this needs to come after the import of `graph`, or else we get circular
# dependencies.
from .engine import SimplePipelineEngine
from .factors import CustomFactor, Factor
from .filters import CustomFilter, Filter
from .graph import ExecutionPlan, TermGraph
from .pipeline import Pipeline
from .term import ComputableTerm, LoadableTerm, Term

__all__ = (
    "Classifier",
    "ComputableTerm",
    "CustomClassifier",
    "CustomFactor",
    "CustomFilter",
    "Domain",
    "ExecutionPlan",
    "Factor",
    "Filter",
    "LoadableTerm",
    "Pipeline",
    "SimplePipelineEngine",
    "Term",
    "TermGraph",
)
