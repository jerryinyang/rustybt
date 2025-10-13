class SingleValueMapping:
    """
    Utility class that provides a mapping interface for singular values.

    This class wraps a single value and returns it for any key access,
    implementing the Null Object pattern for mapping-like interfaces.
    """

    def __init__(self, value):
        self._value = value

    def __getitem__(self, key):
        return self._value
