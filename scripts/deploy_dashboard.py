"""Thin wrapper to call deploy-dashboard.ps1 from the nightly pipeline."""

import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PS_SCRIPT = os.path.join(SCRIPT_DIR, "deploy-dashboard.ps1")


def main() -> int:
    """Deploy dashboard by running the PowerShell deploy script."""
    result = subprocess.run(
        ["powershell", "-ExecutionPolicy", "Bypass", "-File", PS_SCRIPT],
        cwd=os.path.dirname(SCRIPT_DIR),
        capture_output=False,
    )
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
