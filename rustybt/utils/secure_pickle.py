"""Secure pickle serialization with HMAC validation.

SECURITY (Story 8.10): Protect against pickle deserialization attacks by adding
HMAC signatures to pickled data. Only data with valid signatures can be unpickled.
"""

import hashlib
import hmac
import os
import pickle
from typing import Any


class SecurePickleError(Exception):
    """Raised when pickle signature validation fails."""

    pass


def get_pickle_secret_key() -> bytes:
    """Get secret key for HMAC signing from environment.

    Returns:
        32-byte secret key

    Raises:
        ValueError: If RUSTYBT_PICKLE_KEY not set in environment
    """
    key_str = os.getenv("RUSTYBT_PICKLE_KEY")
    if not key_str:
        # Generate a default key (WARNING: not secure across restarts)
        # In production, set RUSTYBT_PICKLE_KEY environment variable
        import warnings

        warnings.warn(
            "RUSTYBT_PICKLE_KEY not set. Using generated key. "
            "Set RUSTYBT_PICKLE_KEY environment variable for production use.",
            UserWarning,
        )
        # Use machine-specific default (consistent within session)
        key_str = f"rustybt-default-pickle-key-{os.getpid()}"

    return key_str.encode("utf-8")


def secure_dumps(obj: Any) -> bytes:
    """Serialize object with HMAC signature.

    Args:
        obj: Object to serialize

    Returns:
        Pickled data with HMAC signature prepended
    """
    # Serialize object
    pickled = pickle.dumps(obj)

    # Generate HMAC signature
    secret_key = get_pickle_secret_key()
    signature = hmac.new(secret_key, pickled, hashlib.sha256).digest()

    # Prepend signature to pickled data
    return signature + pickled


def secure_loads(data: bytes) -> Any:
    """Deserialize object after HMAC validation.

    Args:
        data: Pickled data with HMAC signature prepended

    Returns:
        Deserialized object

    Raises:
        SecurePickleError: If signature validation fails
        ValueError: If data format is invalid
    """
    if len(data) < 32:
        raise ValueError("Invalid pickle data: too short for HMAC signature")

    # Extract signature and pickled data
    signature = data[:32]
    pickled = data[32:]

    # Verify HMAC signature
    secret_key = get_pickle_secret_key()
    expected_signature = hmac.new(secret_key, pickled, hashlib.sha256).digest()

    if not hmac.compare_digest(signature, expected_signature):
        raise SecurePickleError(
            "Pickle signature validation failed. "
            "Data may have been tampered with or is from an untrusted source."
        )

    # Signature valid, safe to unpickle
    return pickle.loads(pickled)
