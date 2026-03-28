from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
PROJECT_BASES = (ROOT / "services", ROOT / "orchestrators")


def iter_projects():
    for base in PROJECT_BASES:
        for project_dir in sorted(path for path in base.iterdir() if path.is_dir()):
            yield project_dir


def iter_test_projects():
    for project_dir in iter_projects():
        if (project_dir / "tests").is_dir():
            yield project_dir


def run_command(command, cwd):
    return subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def format_failure(label, result):
    output = "\n".join(part for part in (result.stdout, result.stderr) if part.strip())
    return f"{label}\n{output}".strip()


def python_command(*args):
    return [sys.executable, *args]
