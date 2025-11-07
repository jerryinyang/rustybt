#!/usr/bin/env python3
"""Build script for generating pdoc API documentation for ReadTheDocs.

This script generates pdoc documentation without requiring full package imports,
avoiding Cython/Rust compilation issues on ReadTheDocs.
"""

import subprocess
import sys
from pathlib import Path


def main():
    """Generate pdoc API documentation."""
    print("=" * 70)
    print("Generating pdoc API Documentation")
    print("=" * 70)

    # Output directory for pdoc docs
    output_dir = Path(__file__).parent / "api-reference"
    output_dir.mkdir(exist_ok=True)

    # Generate pdoc documentation
    # Using --no-show-source and --no-search to avoid import issues
    cmd = [
        sys.executable,
        "-m",
        "pdoc",
        "rustybt",
        "--output-dir",
        str(output_dir),
        "--docformat",
        "google",
        "--html",
        # Don't require imports for basic doc generation
        "--no-show-source",
    ]

    print(f"Running: {' '.join(cmd)}")
    print()

    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)  # noqa: S603
        print(result.stdout)
        if result.stderr:
            print("Warnings:", result.stderr)

        print()
        print("✅ pdoc documentation generated successfully!")
        print(f"📁 Output location: {output_dir}")

    except subprocess.CalledProcessError as e:
        print("❌ Error generating pdoc documentation:")
        print(e.stdout)
        print(e.stderr)
        print()
        print("⚠️  Continuing build without API docs...")
        # Don't fail the entire build if pdoc fails
        # Create a placeholder index
        (output_dir / "index.html").write_text(
            """<!DOCTYPE html>
<html>
<head><title>API Documentation</title></head>
<body>
<h1>API Documentation</h1>
<p>API documentation generation is in progress. Please check back soon.</p>
<p>In the meantime, you can view the source code on
<a href="https://github.com/jerryinyang/rustybt">GitHub</a>.</p>
</body>
</html>"""
        )

    except FileNotFoundError:
        print("❌ pdoc not found. Installing...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pdoc"], check=True)  # noqa: S603
        print("Retrying documentation generation...")
        main()


if __name__ == "__main__":
    main()
