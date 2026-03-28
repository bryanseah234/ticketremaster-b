from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _test_projects():
    projects = []
    for base_name in ("services", "orchestrators"):
        base = ROOT / base_name
        for project_dir in sorted(path for path in base.iterdir() if path.is_dir()):
            if (project_dir / "tests").is_dir():
                projects.append(project_dir)
    return projects


@pytest.mark.parametrize(
    "project_dir",
    _test_projects(),
    ids=lambda project_dir: project_dir.relative_to(ROOT).as_posix(),
)
def test_project_suite(project_dir):
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "tests"],
        cwd=project_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    output = "\n".join(part for part in (result.stdout, result.stderr) if part.strip())
    assert result.returncode == 0, output
