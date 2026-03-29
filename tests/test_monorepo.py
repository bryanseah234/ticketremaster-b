import configparser
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
MYPY_CONFIG = ROOT / "mypy.ini"


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


def test_mypy_config_parses():
    parser = configparser.ConfigParser()
    loaded_files = parser.read(MYPY_CONFIG, encoding="utf-8")
    assert loaded_files == [str(MYPY_CONFIG)]
    assert parser.get("mypy", "mypy_path") == "$MYPY_CONFIG_FILE_DIR"


def test_ci_docker_build_is_not_masked():
    workflow = CI_WORKFLOW.read_text(encoding="utf-8")
    assert "docker compose build --no-cache 2>&1 || true" not in workflow
    assert "docker compose build --no-cache 2>&1" in workflow
