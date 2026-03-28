from repo_tooling import ROOT, format_failure, iter_projects, python_command, run_command


def main():
    failures = []
    config_file = ROOT / "mypy.ini"

    for project_dir in iter_projects():
        result = run_command(
            python_command(
                "-m",
                "mypy",
                ".",
                "--config-file",
                str(config_file),
            ),
            cwd=project_dir,
        )
        if result.returncode != 0:
            failures.append(format_failure(project_dir.as_posix(), result))

    if failures:
        raise SystemExit("\n\n".join(failures))


if __name__ == "__main__":
    main()
