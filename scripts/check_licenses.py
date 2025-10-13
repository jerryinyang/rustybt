#!/usr/bin/env python3
"""Check licenses of installed Python packages.

This script verifies that no GPL-licensed dependencies are present,
as required by the project's licensing policy (Apache 2.0/MIT only).

Exit codes:
    0: All dependencies have acceptable licenses
    1: One or more dependencies have forbidden licenses or unknown licenses
"""

import argparse
import sys
from typing import Dict, List, Set

try:
    import importlib.metadata as metadata
except ImportError:
    import importlib_metadata as metadata


# Acceptable licenses (case-insensitive matching)
ACCEPTABLE_LICENSES = {
    "apache",
    "apache 2.0",
    "apache-2.0",
    "apache software license",
    "mit",
    "mit license",
    "bsd",
    "bsd license",
    "bsd-3-clause",
    "bsd-2-clause",
    "isc",
    "isc license",
    "python software foundation",
    "psf",
    "mpl",
    "mozilla public license",
    "lgpl",  # LGPL is acceptable (not GPL)
}

# Forbidden licenses (contains these strings)
FORBIDDEN_LICENSES = {
    "gpl",  # Matches GPL, GPLv2, GPLv3, but NOT LGPL
    "agpl",
    "commercial",
}


def get_package_license(package_name: str) -> str:
    """Get license for a package.

    Args:
        package_name: Name of the package

    Returns:
        License string or "Unknown"
    """
    try:
        dist = metadata.distribution(package_name)
        license_str = dist.metadata.get("License", "Unknown")

        # Try classifiers if license field is empty
        if not license_str or license_str == "Unknown":
            classifiers = dist.metadata.get_all("Classifier") or []
            license_classifiers = [c for c in classifiers if c.startswith("License ::")]
            if license_classifiers:
                # Extract license from classifier (e.g., "License :: OSI Approved :: MIT License")
                license_str = license_classifiers[0].split("::")[-1].strip()

        return license_str

    except metadata.PackageNotFoundError:
        return "Unknown"


def check_license(license_str: str) -> tuple[bool, str]:
    """Check if a license is acceptable.

    Args:
        license_str: License string

    Returns:
        Tuple of (is_acceptable, reason)
    """
    license_lower = license_str.lower()

    # Check for forbidden licenses (but exclude LGPL from GPL check)
    for forbidden in FORBIDDEN_LICENSES:
        if forbidden in license_lower and forbidden == "gpl":
            # Special case: Allow LGPL but not GPL
            if "lgpl" not in license_lower:
                return False, f"Forbidden license: {license_str}"
        elif forbidden in license_lower:
            return False, f"Forbidden license: {license_str}"

    # Check for acceptable licenses
    for acceptable in ACCEPTABLE_LICENSES:
        if acceptable in license_lower:
            return True, ""

    # Unknown or unrecognized license
    return False, f"Unknown or unrecognized license: {license_str}"


def main():
    parser = argparse.ArgumentParser(description="Check licenses of installed Python packages")
    parser.add_argument(
        "--fail-on-unknown",
        action="store_true",
        help="Fail if any package has unknown license",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show all packages and their licenses",
    )

    args = parser.parse_args()

    print("Checking licenses of installed packages...")
    print()

    violations: List[tuple[str, str, str]] = []
    acceptable: List[tuple[str, str]] = []

    # Get all installed packages
    distributions = list(metadata.distributions())

    for dist in distributions:
        package_name = dist.metadata.get("Name", "Unknown")
        license_str = get_package_license(package_name)

        is_acceptable, reason = check_license(license_str)

        if is_acceptable:
            acceptable.append((package_name, license_str))
        else:
            violations.append((package_name, license_str, reason))

    # Print results
    if args.verbose:
        print("Acceptable licenses:")
        for package, license_str in sorted(acceptable):
            print(f"  ✅ {package}: {license_str}")
        print()

    if violations:
        print(f"❌ Found {len(violations)} license violations:\n")
        for package, license_str, reason in sorted(violations):
            print(f"  Package: {package}")
            print(f"  License: {license_str}")
            print(f"  Reason: {reason}")
            print()

        print("Action required:")
        print("1. Remove packages with forbidden licenses (GPL, AGPL)")
        print("2. Find alternatives with Apache 2.0 or MIT licenses")
        print("3. For unknown licenses, manually verify and update ACCEPTABLE_LICENSES if needed")
        sys.exit(1)
    else:
        print(f"✅ All {len(acceptable)} packages have acceptable licenses")
        sys.exit(0)


if __name__ == "__main__":
    main()
