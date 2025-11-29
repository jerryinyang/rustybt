"""Source code linking for investigation.

This module provides functionality to locate relevant source code
for findings during investigation.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import yaml

if TYPE_CHECKING:
    from rustybt.validation.models import Finding


@dataclass
class SourceLocation:
    """Source code location for a finding.

    Attributes:
        file: Path to the source file
        line: Line number in the file
        description: Description of what's at this location
        framework: Which framework this code belongs to (rustybt or backtrader)
    """

    file: Path
    line: int
    description: str
    framework: Literal["rustybt", "backtrader"]

    def __str__(self) -> str:
        """Return string representation."""
        return f"{self.file}:{self.line} - {self.description}"


# Layer to source module mapping
# Maps each validation layer to relevant source code paths
LAYER_MODULES: dict[str, dict[str, list[str]]] = {
    "data": {
        "rustybt": ["rustybt/data/", "zipline/data/"],
        "backtrader": ["backtrader/feeds/", "backtrader/data/"],
    },
    "signals": {
        "rustybt": ["rustybt/algorithm.py", "rustybt/signals/"],
        "backtrader": ["backtrader/strategy.py", "backtrader/indicator*.py"],
    },
    "orders": {
        "rustybt": ["rustybt/finance/order.py", "rustybt/finance/blotter.py"],
        "backtrader": ["backtrader/order.py", "backtrader/broker*.py"],
    },
    "broker": {
        "rustybt": ["rustybt/finance/broker.py", "rustybt/finance/commission.py"],
        "backtrader": ["backtrader/broker*.py", "backtrader/commission*.py"],
    },
    "portfolio": {
        "rustybt": ["rustybt/finance/portfolio.py", "rustybt/finance/returns.py"],
        "backtrader": ["backtrader/analyzer*.py", "backtrader/cerebro.py"],
    },
}


# Editor configuration
DEFAULT_EDITOR = "code -g {file}:{line}"
CONFIG_DIR = Path.home() / ".config" / "rustybt-validate"
CONFIG_FILE = CONFIG_DIR / "config.yaml"


def get_editor_command() -> str:
    """Get configured editor command.

    Returns:
        Editor command string with {file} and {line} placeholders
    """
    if CONFIG_FILE.exists():
        try:
            config = yaml.safe_load(CONFIG_FILE.read_text())
            return config.get("editor", DEFAULT_EDITOR)
        except (yaml.YAMLError, OSError):
            pass
    return DEFAULT_EDITOR


def set_editor_command(command: str) -> None:
    """Set editor command in user config.

    Args:
        command: Editor command with {file} and {line} placeholders
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    config: dict[str, str] = {}
    if CONFIG_FILE.exists():
        try:
            config = yaml.safe_load(CONFIG_FILE.read_text()) or {}
        except yaml.YAMLError:
            config = {}

    config["editor"] = command

    with open(CONFIG_FILE, "w") as f:
        yaml.dump(config, f, default_flow_style=False)


def open_in_editor(location: SourceLocation) -> bool:
    """Open source location in configured editor.

    Args:
        location: SourceLocation to open

    Returns:
        True if editor was opened successfully, False otherwise
    """
    cmd = get_editor_command()
    cmd = cmd.format(file=str(location.file), line=location.line)

    try:
        os.system(cmd)
        return True
    except Exception:
        return False


def _extract_search_terms(event: str) -> str:
    """Extract search terms from event name.

    Converts event names like 'order_quantity_mismatch' into
    search patterns like 'order|quantity'.

    Args:
        event: Event name from finding

    Returns:
        Search pattern for grep/ripgrep
    """
    # Remove common suffixes
    terms = event
    for suffix in ("_mismatch", "_error", "_difference", "_discrepancy"):
        terms = terms.replace(suffix, "")

    # Convert underscores to OR pattern
    parts = terms.split("_")
    # Filter out very short terms
    parts = [p for p in parts if len(p) > 2]

    if not parts:
        return event

    return "|".join(parts)


def _parse_grep_line(line: str) -> tuple[str, int, str] | None:
    """Parse a grep output line.

    Args:
        line: Line from grep output (format: "file:line:content")

    Returns:
        Tuple of (file, line_number, content) or None if invalid
    """
    parts = line.split(":", 2)
    if len(parts) < 3:
        return None

    try:
        file_path = parts[0]
        line_num = int(parts[1])
        content = parts[2].strip()
        return (file_path, line_num, content)
    except (ValueError, IndexError):
        return None


def grep_for_event(
    search_path: Path,
    event: str,
    max_results: int = 10,
) -> list[tuple[str, int, str]]:
    """Search for event-related code using ripgrep.

    Args:
        search_path: Path to search in (file or directory)
        event: Event name to search for
        max_results: Maximum number of results to return

    Returns:
        List of (file, line, context) tuples
    """
    if not search_path.exists():
        return []

    terms = _extract_search_terms(event)

    # Try ripgrep first (faster)
    try:
        result = subprocess.run(
            [
                "rg",
                "-n",
                "--no-heading",
                "-m",
                str(max_results),
                terms,
                str(search_path),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        results = []
        for line in result.stdout.splitlines():
            parsed = _parse_grep_line(line)
            if parsed:
                results.append(parsed)
        return results[:max_results]

    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Fallback to grep
    try:
        result = subprocess.run(
            [
                "grep",
                "-rn",
                "-E",
                terms,
                str(search_path),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        results = []
        for line in result.stdout.splitlines():
            parsed = _parse_grep_line(line)
            if parsed:
                results.append(parsed)
        return results[:max_results]

    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []


def locate_source(
    finding: Finding,
    project_root: Path | None = None,
) -> list[SourceLocation]:
    """Locate relevant source code for finding.

    Searches configured source modules for code related to the
    finding's layer and event.

    Args:
        finding: Finding to locate source for
        project_root: Root of the project (defaults to cwd)

    Returns:
        List of SourceLocation objects
    """
    if project_root is None:
        project_root = Path.cwd()

    locations: list[SourceLocation] = []

    # Get modules for this layer
    layer_config = LAYER_MODULES.get(finding.layer, {})

    for framework, modules in layer_config.items():
        for module_pattern in modules:
            # Handle glob patterns
            if "*" in module_pattern:
                search_paths = list(project_root.glob(module_pattern))
            else:
                search_paths = [project_root / module_pattern]

            for search_path in search_paths:
                if not search_path.exists():
                    continue

                # Search for event-related code
                # Use description if available, otherwise use finding ID
                search_term = finding.description or finding.id
                results = grep_for_event(search_path, search_term)

                for file_path, line_num, content in results:
                    locations.append(
                        SourceLocation(
                            file=Path(file_path),
                            line=line_num,
                            description=content[:80] + "..." if len(content) > 80 else content,
                            framework=framework,  # type: ignore[arg-type]
                        )
                    )

    return locations


def get_layer_modules(layer: str) -> dict[str, list[str]]:
    """Get module mapping for a specific layer.

    Args:
        layer: Layer name (data, signals, orders, broker, portfolio)

    Returns:
        Dict mapping framework to list of module paths
    """
    return LAYER_MODULES.get(layer, {})


def format_source_locations(locations: list[SourceLocation]) -> str:
    """Format source locations for display.

    Groups locations by framework and numbers them.

    Args:
        locations: List of SourceLocation objects

    Returns:
        Formatted string for display
    """
    if not locations:
        return "No source locations found."

    # Group by framework
    rustybt_locs = [loc for loc in locations if loc.framework == "rustybt"]
    backtrader_locs = [loc for loc in locations if loc.framework == "backtrader"]

    lines = []
    num = 1

    if rustybt_locs:
        lines.append("rustybt locations:")
        for loc in rustybt_locs:
            lines.append(f"  {num}. {loc}")
            num += 1

    if backtrader_locs:
        if rustybt_locs:
            lines.append("")
        lines.append("Backtrader locations (reference):")
        for loc in backtrader_locs:
            lines.append(f"  {num}. {loc}")
            num += 1

    return "\n".join(lines)


class SourceLocationCache:
    """Cache for source location lookups.

    Caches grep results to avoid repeated searches.
    """

    def __init__(self, cache_dir: Path):
        """Initialize cache.

        Args:
            cache_dir: Directory to store cache files
        """
        self.cache_dir = cache_dir
        self.cache_file = cache_dir / "source_cache.yaml"
        self._cache: dict[str, list[dict]] = {}
        self._load_cache()

    def _load_cache(self) -> None:
        """Load cache from disk."""
        if self.cache_file.exists():
            try:
                self._cache = yaml.safe_load(self.cache_file.read_text()) or {}
            except yaml.YAMLError:
                self._cache = {}

    def _save_cache(self) -> None:
        """Save cache to disk."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        with open(self.cache_file, "w") as f:
            yaml.dump(self._cache, f, default_flow_style=False)

    def _make_key(self, layer: str, description: str) -> str:
        """Generate cache key.

        Args:
            layer: Finding layer
            description: Finding description

        Returns:
            Cache key string
        """
        return f"{layer}:{description[:50]}"

    def get(self, finding: Finding) -> list[SourceLocation] | None:
        """Get cached locations for finding.

        Args:
            finding: Finding to look up

        Returns:
            List of SourceLocation objects or None if not cached
        """
        key = self._make_key(finding.layer, finding.description)
        cached = self._cache.get(key)

        if cached is None:
            return None

        return [
            SourceLocation(
                file=Path(item["file"]),
                line=item["line"],
                description=item["description"],
                framework=item["framework"],
            )
            for item in cached
        ]

    def set(self, finding: Finding, locations: list[SourceLocation]) -> None:
        """Cache locations for finding.

        Args:
            finding: Finding being cached
            locations: Source locations to cache
        """
        key = self._make_key(finding.layer, finding.description)
        self._cache[key] = [
            {
                "file": str(loc.file),
                "line": loc.line,
                "description": loc.description,
                "framework": loc.framework,
            }
            for loc in locations
        ]
        self._save_cache()

    def invalidate(self, finding: Finding | None = None) -> None:
        """Invalidate cache.

        Args:
            finding: Specific finding to invalidate, or None to clear all
        """
        if finding is None:
            self._cache = {}
        else:
            key = self._make_key(finding.layer, finding.description)
            self._cache.pop(key, None)
        self._save_cache()
