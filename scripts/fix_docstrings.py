#!/usr/bin/env python3
"""Fix docstring style to comply with D212 (summary on first line)."""
import re
from pathlib import Path


def fix_docstrings(content: str) -> str:
    """Fix docstrings to have summary on first line."""
    # Pattern to match docstrings with summary on second line
    # Matches: """<newline>Summary text...
    pattern = r'"""[\n\r]+\s*([A-Z][^"\n]+)'

    def replace_docstring(match):
        summary = match.group(1).strip()
        # Ensure summary ends with period
        if not summary.endswith((".", "?", "!")):
            summary += "."
        return f'"""{summary}'

    return re.sub(pattern, replace_docstring, content)


def process_file(filepath: Path) -> bool:
    """Process a single file and fix its docstrings."""
    print(f"Processing {filepath}...")

    content = filepath.read_text(encoding="utf-8")
    fixed = fix_docstrings(content)

    if content != fixed:
        filepath.write_text(fixed, encoding="utf-8")
        print(f"  Fixed docstrings in {filepath.name}")
        return True
    else:
        print(f"  No changes needed in {filepath.name}")
        return False


def main():
    """Fix docstrings in all Python files."""
    project_root = Path(__file__).parent.parent

    files_to_fix = [
        project_root / "tracking" / "forecasting_db.py",
        project_root / "tracking" / "database.py",
        project_root / "pipelines" / "polymarket_fetcher.py",
        project_root / "config" / "settings.py",
    ]

    fixed_count = 0
    for filepath in files_to_fix:
        if filepath.exists():
            if process_file(filepath):
                fixed_count += 1
        else:
            print(f"  File not found: {filepath}")

    print(f"\nFixed {fixed_count} files")


if __name__ == "__main__":
    main()
