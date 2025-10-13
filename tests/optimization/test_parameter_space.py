"""Tests for parameter space definitions."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from rustybt.optimization.parameter_space import (
    CategoricalParameter,
    ContinuousParameter,
    DiscreteParameter,
    ParameterSpace,
)


class TestContinuousParameter:
    """Tests for ContinuousParameter."""

    def test_valid_continuous_parameter(self):
        """Test creating valid continuous parameter."""
        param = ContinuousParameter(name="learning_rate", min_value=0.001, max_value=0.1)

        assert param.name == "learning_rate"
        assert param.min_value == 0.001
        assert param.max_value == 0.1
        assert param.prior == "uniform"

    def test_continuous_parameter_with_log_uniform(self):
        """Test continuous parameter with log-uniform prior."""
        param = ContinuousParameter(
            name="learning_rate", min_value=0.001, max_value=0.1, prior="log-uniform"
        )

        assert param.prior == "log-uniform"

    def test_continuous_parameter_invalid_bounds(self):
        """Test continuous parameter with max <= min raises error."""
        with pytest.raises(ValidationError) as exc_info:
            ContinuousParameter(name="lr", min_value=0.1, max_value=0.1)

        assert "max_value must be > min_value" in str(exc_info.value)

        with pytest.raises(ValidationError):
            ContinuousParameter(name="lr", min_value=0.1, max_value=0.05)

    def test_continuous_parameter_with_decimal(self):
        """Test continuous parameter with Decimal values."""
        param = ContinuousParameter(
            name="threshold", min_value=Decimal("0.5"), max_value=Decimal("0.9")
        )

        assert param.min_value == Decimal("0.5")
        assert param.max_value == Decimal("0.9")


class TestDiscreteParameter:
    """Tests for DiscreteParameter."""

    def test_valid_discrete_parameter(self):
        """Test creating valid discrete parameter."""
        param = DiscreteParameter(name="window", min_value=10, max_value=50, step=5)

        assert param.name == "window"
        assert param.min_value == 10
        assert param.max_value == 50
        assert param.step == 5

    def test_discrete_parameter_default_step(self):
        """Test discrete parameter with default step=1."""
        param = DiscreteParameter(name="n_layers", min_value=1, max_value=10)

        assert param.step == 1

    def test_discrete_parameter_invalid_bounds(self):
        """Test discrete parameter with max <= min raises error."""
        with pytest.raises(ValidationError):
            DiscreteParameter(name="n", min_value=10, max_value=10)

        with pytest.raises(ValidationError):
            DiscreteParameter(name="n", min_value=10, max_value=5)

    def test_discrete_parameter_invalid_step(self):
        """Test discrete parameter with step that doesn't divide range."""
        with pytest.raises(ValidationError) as exc_info:
            DiscreteParameter(name="window", min_value=10, max_value=50, step=7)

        assert "does not divide range evenly" in str(exc_info.value)

    def test_discrete_parameter_zero_step(self):
        """Test discrete parameter with step=0 raises error."""
        with pytest.raises(ValidationError) as exc_info:
            DiscreteParameter(name="n", min_value=1, max_value=10, step=0)

        assert "step must be positive" in str(exc_info.value)


class TestCategoricalParameter:
    """Tests for CategoricalParameter."""

    def test_valid_categorical_parameter(self):
        """Test creating valid categorical parameter."""
        param = CategoricalParameter(name="optimizer", choices=["adam", "sgd", "rmsprop"])

        assert param.name == "optimizer"
        assert param.choices == ["adam", "sgd", "rmsprop"]

    def test_categorical_parameter_mixed_types(self):
        """Test categorical parameter with mixed type choices."""
        param = CategoricalParameter(name="activation", choices=["relu", "tanh", 123])

        assert len(param.choices) == 3

    def test_categorical_parameter_single_choice(self):
        """Test categorical parameter with single choice raises error."""
        with pytest.raises(ValidationError) as exc_info:
            CategoricalParameter(name="opt", choices=["adam"])

        assert "at least 2 choices" in str(exc_info.value)

    def test_categorical_parameter_duplicate_choices(self):
        """Test categorical parameter with duplicate choices raises error."""
        with pytest.raises(ValidationError) as exc_info:
            CategoricalParameter(name="opt", choices=["adam", "adam", "sgd"])

        assert "must be unique" in str(exc_info.value)


class TestParameterSpace:
    """Tests for ParameterSpace."""

    def test_valid_parameter_space(self):
        """Test creating valid parameter space."""
        space = ParameterSpace(
            parameters=[
                ContinuousParameter(name="lr", min_value=0.001, max_value=0.1),
                DiscreteParameter(name="batch_size", min_value=16, max_value=128, step=16),
                CategoricalParameter(name="optimizer", choices=["adam", "sgd"]),
            ]
        )

        assert len(space.parameters) == 3

    def test_parameter_space_empty(self):
        """Test parameter space with no parameters raises error."""
        with pytest.raises(ValidationError):
            ParameterSpace(parameters=[])

    def test_parameter_space_duplicate_names(self):
        """Test parameter space with duplicate names raises error."""
        with pytest.raises(ValidationError) as exc_info:
            ParameterSpace(
                parameters=[
                    ContinuousParameter(name="lr", min_value=0.001, max_value=0.1),
                    DiscreteParameter(name="lr", min_value=1, max_value=10),
                ]
            )

        assert "must be unique" in str(exc_info.value)

    def test_get_parameter(self):
        """Test getting parameter by name."""
        space = ParameterSpace(
            parameters=[
                ContinuousParameter(name="lr", min_value=0.001, max_value=0.1),
                DiscreteParameter(name="window", min_value=10, max_value=50, step=5),
            ]
        )

        param = space.get_parameter("lr")
        assert isinstance(param, ContinuousParameter)
        assert param.name == "lr"

        param = space.get_parameter("window")
        assert isinstance(param, DiscreteParameter)
        assert param.name == "window"

    def test_get_parameter_not_found(self):
        """Test getting non-existent parameter raises KeyError."""
        space = ParameterSpace(
            parameters=[
                ContinuousParameter(name="lr", min_value=0.001, max_value=0.1),
            ]
        )

        with pytest.raises(KeyError) as exc_info:
            space.get_parameter("nonexistent")

        assert "not found" in str(exc_info.value)

    def test_validate_params_valid(self):
        """Test validate_params with valid parameters."""
        space = ParameterSpace(
            parameters=[
                ContinuousParameter(name="lr", min_value=0.001, max_value=0.1),
                DiscreteParameter(name="window", min_value=10, max_value=50, step=5),
                CategoricalParameter(name="opt", choices=["adam", "sgd"]),
            ]
        )

        params = {"lr": 0.01, "window": 20, "opt": "adam"}
        assert space.validate_params(params) is True

        params = {"lr": Decimal("0.05"), "window": 45, "opt": "sgd"}
        assert space.validate_params(params) is True

    def test_validate_params_missing_parameter(self):
        """Test validate_params with missing parameter."""
        space = ParameterSpace(
            parameters=[
                ContinuousParameter(name="lr", min_value=0.001, max_value=0.1),
                DiscreteParameter(name="window", min_value=10, max_value=50, step=5),
            ]
        )

        params = {"lr": 0.01}  # Missing 'window'

        with pytest.raises(ValueError) as exc_info:
            space.validate_params(params)

        assert "Missing parameters" in str(exc_info.value)
        assert "window" in str(exc_info.value)

    def test_validate_params_extra_parameter(self):
        """Test validate_params with extra parameter."""
        space = ParameterSpace(
            parameters=[
                ContinuousParameter(name="lr", min_value=0.001, max_value=0.1),
            ]
        )

        params = {"lr": 0.01, "extra": 123}

        with pytest.raises(ValueError) as exc_info:
            space.validate_params(params)

        assert "Unknown parameters" in str(exc_info.value)
        assert "extra" in str(exc_info.value)

    def test_validate_params_continuous_out_of_bounds(self):
        """Test validate_params with continuous parameter out of bounds."""
        space = ParameterSpace(
            parameters=[
                ContinuousParameter(name="lr", min_value=0.001, max_value=0.1),
            ]
        )

        params = {"lr": 0.5}  # Out of bounds

        with pytest.raises(ValueError) as exc_info:
            space.validate_params(params)

        assert "outside bounds" in str(exc_info.value)

    def test_validate_params_discrete_out_of_bounds(self):
        """Test validate_params with discrete parameter out of bounds."""
        space = ParameterSpace(
            parameters=[
                DiscreteParameter(name="window", min_value=10, max_value=50, step=5),
            ]
        )

        params = {"window": 100}

        with pytest.raises(ValueError) as exc_info:
            space.validate_params(params)

        assert "outside bounds" in str(exc_info.value)

    def test_validate_params_discrete_wrong_step(self):
        """Test validate_params with discrete parameter not matching step."""
        space = ParameterSpace(
            parameters=[
                DiscreteParameter(name="window", min_value=10, max_value=50, step=5),
            ]
        )

        params = {"window": 17}  # Not a multiple of step from min_value

        with pytest.raises(ValueError) as exc_info:
            space.validate_params(params)

        assert "does not match step" in str(exc_info.value)

    def test_validate_params_discrete_not_integer(self):
        """Test validate_params with discrete parameter as non-integer."""
        space = ParameterSpace(
            parameters=[
                DiscreteParameter(name="window", min_value=10, max_value=50, step=5),
            ]
        )

        params = {"window": 20.5}

        with pytest.raises(ValueError) as exc_info:
            space.validate_params(params)

        assert "must be integer" in str(exc_info.value)

    def test_validate_params_categorical_invalid_choice(self):
        """Test validate_params with categorical parameter invalid choice."""
        space = ParameterSpace(
            parameters=[
                CategoricalParameter(name="opt", choices=["adam", "sgd"]),
            ]
        )

        params = {"opt": "rmsprop"}

        with pytest.raises(ValueError) as exc_info:
            space.validate_params(params)

        assert "not in choices" in str(exc_info.value)

    def test_cardinality_finite(self):
        """Test cardinality calculation for finite space."""
        space = ParameterSpace(
            parameters=[
                DiscreteParameter(name="window", min_value=10, max_value=50, step=10),  # 5 values
                CategoricalParameter(name="opt", choices=["adam", "sgd"]),  # 2 values
            ]
        )

        # 5 * 2 = 10
        assert space.cardinality() == 10

    def test_cardinality_infinite(self):
        """Test cardinality returns -1 for continuous space."""
        space = ParameterSpace(
            parameters=[
                ContinuousParameter(name="lr", min_value=0.001, max_value=0.1),
                DiscreteParameter(name="window", min_value=10, max_value=50, step=10),
            ]
        )

        assert space.cardinality() == -1
