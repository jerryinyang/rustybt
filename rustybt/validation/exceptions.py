"""Custom exceptions for the rustybt validation framework.

This module defines domain-specific exceptions for handling duplicate
sessions and findings during the validation process.
"""


class DuplicateSessionError(Exception):
    """Raised when creating a session that duplicates an existing IN_PROGRESS session.

    When a user attempts to create a new validation session for a strategy that
    already has an IN_PROGRESS session, this exception is raised with helpful
    suggestions for resolution.

    Attributes:
        existing_session_id: ID of the existing session that conflicts
        strategy: Name of the strategy with the duplicate session

    Example:
        >>> raise DuplicateSessionError("20251124-143000-sma_crossover", "sma_crossover")
        DuplicateSessionError: Session 20251124-143000-sma_crossover already in progress for sma_crossover.
        Use 'rustybt-validate session resume 20251124-143000-sma_crossover' to continue
        or 'rustybt-validate session delete 20251124-143000-sma_crossover' to start fresh.
    """

    def __init__(self, existing_session_id: str, strategy: str) -> None:
        """Initialize DuplicateSessionError.

        Args:
            existing_session_id: ID of the existing session that conflicts
            strategy: Name of the strategy with the duplicate session
        """
        self.existing_session_id = existing_session_id
        self.strategy = strategy
        message = (
            f"Session {existing_session_id} already in progress for {strategy}. "
            f"Use 'rustybt-validate session resume {existing_session_id}' to continue "
            f"or 'rustybt-validate session delete {existing_session_id}' to start fresh."
        )
        super().__init__(message)


class DuplicateFindingError(Exception):
    """Raised when adding a finding that duplicates an existing finding.

    Findings are unique by their combination of layer, event, and timestamp.
    When a duplicate finding is detected, this exception is raised.

    Attributes:
        existing_finding_id: ID of the existing finding that conflicts

    Example:
        >>> raise DuplicateFindingError("layer_1_finding_001")
        DuplicateFindingError: Finding already exists: layer_1_finding_001
    """

    def __init__(self, existing_finding_id: str) -> None:
        """Initialize DuplicateFindingError.

        Args:
            existing_finding_id: ID of the existing finding that conflicts
        """
        self.existing_finding_id = existing_finding_id
        message = f"Finding already exists: {existing_finding_id}"
        super().__init__(message)
