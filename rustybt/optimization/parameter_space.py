"""Parameter space definitions for optimization."""

from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class ContinuousParameter(BaseModel):
    """Continuous parameter (float/Decimal) with bounds."""

    name: str
    min_value: float | Decimal
    max_value: float | Decimal
    prior: Literal["uniform", "log-uniform", "normal"] = "uniform"

    @field_validator("max_value")
    def validate_bounds(cls, v, info):
        """Validate max_value > min_value."""
        min_val = info.data.get("min_value")
        if min_val is not None and v <= min_val:
            raise ValueError("max_value must be > min_value")
        return v


class DiscreteParameter(BaseModel):
    """Discrete integer parameter with bounds and step."""

    name: str
    min_value: int
    max_value: int
    step: int = 1

    @field_validator("max_value")
    def validate_max_value(cls, v, info):
        """Validate max_value > min_value."""
        min_val = info.data.get("min_value")
        if min_val is not None and v <= min_val:
            raise ValueError("max_value must be > min_value")
        return v

    @field_validator("step")
    def validate_step(cls, v, info):
        """Validate step is positive and divides range."""
        if v <= 0:
            raise ValueError("step must be positive")

        min_val = info.data.get("min_value")
        max_val = info.data.get("max_value")
        if min_val is not None and max_val is not None:
            range_size = max_val - min_val
            if range_size % v != 0:
                raise ValueError(f"step {v} does not divide range evenly")
        return v


class CategoricalParameter(BaseModel):
    """Categorical parameter with fixed choices."""

    name: str
    choices: list[Any]

    @field_validator("choices")
    def validate_choices(cls, v):
        """Validate at least 2 unique choices."""
        if len(v) < 2:
            raise ValueError("Must have at least 2 choices")
        if len(v) != len(set(map(str, v))):
            raise ValueError("Choices must be unique")
        return v


class ParameterSpace(BaseModel):
    """Complete parameter space definition."""

    parameters: list[ContinuousParameter | DiscreteParameter | CategoricalParameter] = Field(
        ..., min_length=1
    )

    @field_validator("parameters")
    def validate_unique_names(cls, v):
        """Validate parameter names are unique."""
        names = [p.name for p in v]
        if len(names) != len(set(names)):
            raise ValueError("Parameter names must be unique")
        return v

    def get_parameter(
        self, name: str
    ) -> ContinuousParameter | DiscreteParameter | CategoricalParameter:
        """Get parameter by name.

        Args:
            name: Parameter name

        Returns:
            Parameter definition

        Raises:
            KeyError: If parameter not found
        """
        for param in self.parameters:
            if param.name == name:
                return param
        raise KeyError(f"Parameter '{name}' not found")

    def validate_params(self, params: dict) -> bool:
        """Validate parameter values against space constraints.

        Args:
            params: Dictionary of parameter name to value

        Returns:
            True if valid

        Raises:
            ValueError: If validation fails
        """
        # Check all parameters are present
        param_names = {p.name for p in self.parameters}
        provided_names = set(params.keys())

        missing = param_names - provided_names
        if missing:
            raise ValueError(f"Missing parameters: {missing}")

        extra = provided_names - param_names
        if extra:
            raise ValueError(f"Unknown parameters: {extra}")

        # Validate each parameter value
        for name, value in params.items():
            param = self.get_parameter(name)

            if isinstance(param, ContinuousParameter):
                # Convert to Decimal for comparison
                min_val = Decimal(str(param.min_value))
                max_val = Decimal(str(param.max_value))
                val = Decimal(str(value))

                if not (min_val <= val <= max_val):
                    raise ValueError(
                        f"Parameter '{name}' value {value} outside bounds "
                        f"[{param.min_value}, {param.max_value}]"
                    )

            elif isinstance(param, DiscreteParameter):
                # Convert numpy integers to Python int
                import numpy as np

                if isinstance(value, np.integer):
                    value = int(value)

                if not isinstance(value, int):
                    raise ValueError(f"Parameter '{name}' must be integer, got {type(value)}")
                if not (param.min_value <= value <= param.max_value):
                    raise ValueError(
                        f"Parameter '{name}' value {value} outside bounds "
                        f"[{param.min_value}, {param.max_value}]"
                    )
                if (value - param.min_value) % param.step != 0:
                    raise ValueError(
                        f"Parameter '{name}' value {value} does not match step {param.step}"
                    )

            elif isinstance(param, CategoricalParameter):
                # Allow string comparison for flexibility
                if value not in param.choices and str(value) not in map(str, param.choices):
                    raise ValueError(
                        f"Parameter '{name}' value {value} not in choices {param.choices}"
                    )

        return True

    def cardinality(self) -> int:
        """Calculate total number of possible parameter combinations.

        Returns:
            Total combinations, or -1 if infinite (continuous parameters)
        """
        total = 1
        for param in self.parameters:
            if isinstance(param, ContinuousParameter):
                return -1  # Infinite for continuous spaces
            elif isinstance(param, DiscreteParameter):
                count = ((param.max_value - param.min_value) // param.step) + 1
                total *= count
            elif isinstance(param, CategoricalParameter):
                total *= len(param.choices)
        return total
