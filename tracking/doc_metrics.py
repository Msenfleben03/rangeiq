"""
Documentation health tracking and metrics reporting.

This module provides automated tools to monitor documentation coverage,
staleness, and quality across the sports betting project. It integrates
with pre-commit hooks and weekly audit workflows.

Example:
    Generate a coverage report:
    >>> from tracking.doc_metrics import generate_coverage_report
    >>> report = generate_coverage_report()
    >>> print(report['summary'])

    Check for stale documentation:
    >>> stale_docs = find_stale_documentation(days=30)
    >>> for doc in stale_docs:
    ...     print(f"{doc['file']}: {doc['days_old']} days old")
"""

import ast
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import git


@dataclass
class DocumentationMetrics:
    """Comprehensive documentation health metrics.

    Attributes:
        docstring_coverage: Percentage of public functions with docstrings (0.0-1.0).
        module_readme_coverage: Percentage of modules with README.md (0.0-1.0).
        adr_count: Number of Architecture Decision Records.
        stale_docs_count: Number of docs not updated in 30+ days.
        broken_links: Number of broken cross-references.
        avg_doc_age_days: Average age of documentation in days.
        total_public_functions: Total number of public functions/classes.
        documented_functions: Number with docstrings.
        missing_docstrings: List of functions without docstrings.
        module_readmes: Dict mapping module -> README status.
        stale_docs: List of stale documentation files.
    """

    docstring_coverage: float = 0.0
    module_readme_coverage: float = 0.0
    adr_count: int = 0
    stale_docs_count: int = 0
    broken_links: int = 0
    avg_doc_age_days: float = 0.0

    total_public_functions: int = 0
    documented_functions: int = 0
    missing_docstrings: list[str] = field(default_factory=list)

    module_readmes: dict[str, bool] = field(default_factory=dict)
    stale_docs: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to dictionary for JSON export."""
        return {
            "docstring_coverage": self.docstring_coverage,
            "module_readme_coverage": self.module_readme_coverage,
            "adr_count": self.adr_count,
            "stale_docs_count": self.stale_docs_count,
            "broken_links": self.broken_links,
            "avg_doc_age_days": self.avg_doc_age_days,
            "total_public_functions": self.total_public_functions,
            "documented_functions": self.documented_functions,
            "missing_docstrings": self.missing_docstrings,
            "module_readmes": self.module_readmes,
            "stale_docs": self.stale_docs,
        }


def get_project_root() -> Path:
    """Get project root directory.

    Returns:
        Path to project root (where .git directory exists).
    """
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / ".git").exists():
            return current
        current = current.parent
    raise RuntimeError("Could not find project root (no .git directory)")


def find_python_files(root: Path, exclude_patterns: list[str] = None) -> list[Path]:
    """Find all Python files in project.

    Args:
        root: Root directory to search from.
        exclude_patterns: List of glob patterns to exclude. Defaults to
            ['.venv', '__pycache__', '.git', 'tests'].

    Returns:
        List of Path objects for Python files.
    """
    if exclude_patterns is None:
        exclude_patterns = [".venv", "__pycache__", ".git", "tests"]

    python_files = []
    for py_file in root.rglob("*.py"):
        # Skip if matches exclude pattern
        if any(pattern in str(py_file) for pattern in exclude_patterns):
            continue
        python_files.append(py_file)

    return python_files


def extract_functions_classes(file_path: Path) -> list[dict[str, Any]]:
    """Extract public functions and classes from Python file.

    Args:
        file_path: Path to Python file.

    Returns:
        List of dicts with keys: 'name', 'type' ('function'/'class'),
        'has_docstring' (bool), 'line' (int).

    Example:
        >>> items = extract_functions_classes(Path('models/elo.py'))
        >>> items[0]
        {'name': 'EloRating', 'type': 'class', 'has_docstring': True, 'line': 15}
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=str(file_path))
    except SyntaxError:
        return []

    items = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            # Skip private functions/classes (start with _)
            if node.name.startswith("_"):
                continue

            item = {
                "name": node.name,
                "type": "class" if isinstance(node, ast.ClassDef) else "function",
                "has_docstring": ast.get_docstring(node) is not None,
                "line": node.lineno,
            }
            items.append(item)

    return items


def calculate_docstring_coverage(root: Path) -> tuple[float, list[str]]:
    """Calculate docstring coverage across project.

    Args:
        root: Project root directory.

    Returns:
        Tuple of (coverage_percentage, list_of_missing_docstrings).
        Missing docstrings formatted as "file.py:line:function_name".

    Example:
        >>> coverage, missing = calculate_docstring_coverage(Path('.'))
        >>> coverage
        0.85
        >>> missing[:3]
        ['models/elo.py:45:update_rating', 'betting/kelly.py:12:calculate_kelly']
    """
    python_files = find_python_files(root)

    total_items = 0
    documented_items = 0
    missing = []

    for py_file in python_files:
        items = extract_functions_classes(py_file)

        for item in items:
            total_items += 1
            if item["has_docstring"]:
                documented_items += 1
            else:
                rel_path = py_file.relative_to(root)
                missing.append(f"{rel_path}:{item['line']}:{item['name']}")

    coverage = documented_items / total_items if total_items > 0 else 0.0
    return coverage, missing


def check_module_readmes(root: Path) -> dict[str, bool]:
    """Check which modules have README.md files.

    Args:
        root: Project root directory.

    Returns:
        Dict mapping module_path -> has_readme (bool).

    Example:
        >>> readmes = check_module_readmes(Path('.'))
        >>> readmes
        {'models': False, 'betting': False, 'tracking': True, ...}
    """
    # Key directories that should have READMEs
    key_modules = [
        "models",
        "features",
        "betting",
        "tracking",
        "backtesting",
        "pipelines",
        "models/sport_specific/ncaab",
        "models/sport_specific/mlb",
    ]

    readme_status = {}

    for module in key_modules:
        module_path = root / module
        readme_path = module_path / "README.md"
        readme_status[module] = readme_path.exists()

    return readme_status


def count_adrs(root: Path) -> int:
    """Count Architecture Decision Records.

    Args:
        root: Project root directory.

    Returns:
        Number of ADRs found in docs/DECISIONS.md.

    Note:
        Counts sections starting with "# ADR-" or "## ADR-".
    """
    decisions_file = root / "docs" / "DECISIONS.md"

    if not decisions_file.exists():
        return 0

    with open(decisions_file, "r", encoding="utf-8") as f:
        content = f.read()

    # Count ADR headers (# ADR-XXX or ## ADR-XXX)
    adr_pattern = re.compile(r"^#{1,2}\s+ADR-\d+", re.MULTILINE)
    matches = adr_pattern.findall(content)

    return len(matches)


def find_stale_documentation(root: Path, days: int = 30) -> list[dict[str, Any]]:
    """Find documentation files not updated in specified days.

    Uses git history to determine last modification date. Files not in git
    are considered "never updated" (age = infinity).

    Args:
        root: Project root directory.
        days: Number of days to consider stale. Defaults to 30.

    Returns:
        List of dicts with keys:
            - file: Relative path to file
            - last_modified: Datetime of last change
            - days_old: Days since last change
            - status: 'stale' or 'never_updated'

    Example:
        >>> stale = find_stale_documentation(Path('.'), days=30)
        >>> stale[0]
        {
            'file': 'docs/DATA_DICTIONARY.md',
            'last_modified': datetime(2025, 12, 15),
            'days_old': 40,
            'status': 'stale'
        }
    """
    try:
        repo = git.Repo(root)
    except git.InvalidGitRepositoryError:
        return []

    # Documentation files to check
    doc_patterns = [
        "docs/**/*.md",
        "*.md",
        "**/README.md",
    ]

    doc_files = []
    for pattern in doc_patterns:
        doc_files.extend(root.glob(pattern))

    # Remove duplicates
    doc_files = list(set(doc_files))

    stale_docs = []
    now = datetime.now()

    for doc_file in doc_files:
        try:
            rel_path = doc_file.relative_to(root)

            # Get last commit that touched this file
            commits = list(repo.iter_commits(paths=str(rel_path), max_count=1))

            if not commits:
                # File exists but never committed
                stale_docs.append(
                    {
                        "file": str(rel_path),
                        "last_modified": None,
                        "days_old": float("inf"),
                        "status": "never_updated",
                    }
                )
                continue

            last_commit = commits[0]
            last_modified = datetime.fromtimestamp(last_commit.committed_date)
            age_days = (now - last_modified).days

            if age_days > days:
                stale_docs.append(
                    {
                        "file": str(rel_path),
                        "last_modified": last_modified,
                        "days_old": age_days,
                        "status": "stale",
                    }
                )

        except Exception:
            # Skip files that cause issues
            continue

    return stale_docs


def generate_coverage_report(root: Path = None) -> DocumentationMetrics:
    """Generate comprehensive documentation coverage report.

    Args:
        root: Project root directory. If None, auto-detect.

    Returns:
        DocumentationMetrics object with all metrics.

    Example:
        >>> report = generate_coverage_report()
        >>> print(f"Coverage: {report.docstring_coverage:.1%}")
        Coverage: 85.3%
        >>> print(f"Stale docs: {report.stale_docs_count}")
        Stale docs: 3
    """
    if root is None:
        root = get_project_root()

    metrics = DocumentationMetrics()

    # Docstring coverage
    coverage, missing = calculate_docstring_coverage(root)
    metrics.docstring_coverage = coverage
    metrics.documented_functions = len(missing)  # Will fix below
    metrics.total_public_functions = int(
        metrics.documented_functions / (1 - coverage) if coverage < 1.0 else len(missing)
    )
    metrics.missing_docstrings = missing

    # Fix documented_functions count
    metrics.documented_functions = metrics.total_public_functions - len(missing)

    # Module READMEs
    readme_status = check_module_readmes(root)
    metrics.module_readmes = readme_status
    total_modules = len(readme_status)
    modules_with_readme = sum(1 for has_readme in readme_status.values() if has_readme)
    metrics.module_readme_coverage = (
        modules_with_readme / total_modules if total_modules > 0 else 0.0
    )

    # ADRs
    metrics.adr_count = count_adrs(root)

    # Stale docs
    stale_docs = find_stale_documentation(root, days=30)
    metrics.stale_docs = stale_docs
    metrics.stale_docs_count = len(stale_docs)

    # Average doc age
    if stale_docs:
        valid_ages = [doc["days_old"] for doc in stale_docs if doc["days_old"] != float("inf")]
        metrics.avg_doc_age_days = sum(valid_ages) / len(valid_ages) if valid_ages else 0.0

    return metrics


def format_coverage_report(metrics: DocumentationMetrics) -> str:
    """Format metrics as human-readable report.

    Args:
        metrics: DocumentationMetrics object.

    Returns:
        Formatted markdown report.

    Example:
        >>> metrics = generate_coverage_report()
        >>> print(format_coverage_report(metrics))
    """
    report = [
        "# Documentation Health Report",
        f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Coverage Summary",
        "",
        f"- **Docstring Coverage**: {metrics.docstring_coverage:.1%} "
        f"({'✅' if metrics.docstring_coverage >= 0.80 else '⚠️'})",
        f"  - Total Functions/Classes: {metrics.total_public_functions}",
        f"  - Documented: {metrics.documented_functions}",
        f"  - Missing Docstrings: {len(metrics.missing_docstrings)}",
        "",
        f"- **Module README Coverage**: {metrics.module_readme_coverage:.1%} "
        f"({'✅' if metrics.module_readme_coverage >= 0.70 else '⚠️'})",
    ]

    # Module README details
    report.append("")
    report.append("### Module READMEs")
    for module, has_readme in sorted(metrics.module_readmes.items()):
        status = "✅" if has_readme else "❌"
        report.append(f"  - {status} `{module}/README.md`")

    # ADRs
    report.append("")
    report.append(f"- **ADR Count**: {metrics.adr_count} ")
    target_adrs = 8
    if metrics.adr_count >= target_adrs:
        report.append(f"  ✅ Met target ({target_adrs}+)")
    else:
        report.append(f"  ⚠️ Below target ({target_adrs}+), current: {metrics.adr_count}")

    # Stale docs
    report.append("")
    report.append(
        f"- **Stale Documentation**: {metrics.stale_docs_count} files (>30 days old) "
        f"({'✅' if metrics.stale_docs_count == 0 else '⚠️'})"
    )

    if metrics.stale_docs:
        report.append("")
        report.append("### Stale Files")
        for doc in sorted(metrics.stale_docs, key=lambda d: d["days_old"], reverse=True):
            if doc["days_old"] == float("inf"):
                report.append(f"  - `{doc['file']}` — Never updated")
            else:
                report.append(f"  - `{doc['file']}` — {doc['days_old']} days old")

    # Missing docstrings
    if metrics.missing_docstrings:
        report.append("")
        report.append("## Missing Docstrings")
        report.append("")
        report.append("The following functions/classes need docstrings:")
        report.append("")
        for item in sorted(metrics.missing_docstrings)[:20]:  # Show first 20
            report.append(f"- `{item}`")

        if len(metrics.missing_docstrings) > 20:
            report.append(f"- ... and {len(metrics.missing_docstrings) - 20} more")

    # Action items
    report.append("")
    report.append("## Action Items")
    report.append("")

    if metrics.docstring_coverage < 0.80:
        report.append("1. **Priority: Add missing docstrings**")
        report.append(
            f"   - Target: {metrics.total_public_functions - metrics.documented_functions} functions"
        )

    missing_readmes = [m for m, exists in metrics.module_readmes.items() if not exists]
    if missing_readmes:
        report.append("2. **Create module READMEs**:")
        for module in missing_readmes:
            report.append(f"   - `{module}/README.md`")

    if metrics.adr_count < 8:
        report.append("3. **Document architectural decisions**")
        report.append(f"   - Current: {metrics.adr_count} ADRs")
        report.append("   - Target: 8+ ADRs")

    if metrics.stale_docs_count > 0:
        report.append("4. **Update stale documentation**")
        report.append(f"   - {metrics.stale_docs_count} files need review")

    return "\n".join(report)


def export_metrics_json(metrics: DocumentationMetrics, output_path: Path) -> None:
    """Export metrics to JSON file.

    Args:
        metrics: DocumentationMetrics object.
        output_path: Path to write JSON file.
    """
    import json

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(metrics.to_dict(), f, indent=2, default=str)


if __name__ == "__main__":
    """Run coverage report when executed directly."""
    print("Generating documentation coverage report...\n")

    root = get_project_root()
    metrics = generate_coverage_report(root)

    # Print report
    report = format_coverage_report(metrics)
    print(report)

    # Save to file
    report_dir = root / "docs" / "reports"
    report_dir.mkdir(exist_ok=True)

    # Save markdown
    report_path = report_dir / f"doc_health_{datetime.now().strftime('%Y%m%d')}.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)

    # Save JSON
    json_path = report_dir / f"doc_metrics_{datetime.now().strftime('%Y%m%d')}.json"
    export_metrics_json(metrics, json_path)

    print("\n✅ Reports saved:")
    print(f"   - {report_path}")
    print(f"   - {json_path}")
