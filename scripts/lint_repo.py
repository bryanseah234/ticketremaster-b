from repo_tooling import format_failure, iter_projects, python_command, run_command


def main():
    failures = []
    for project_dir in iter_projects():
        result = run_command(
            python_command(
                "-m",
                "ruff",
                "check",
                ".",
                "--select",
                "F,E9",
                "--extend-exclude",
                "*_pb2.py,*_pb2_grpc.py,migrations/versions",
            ),
            cwd=project_dir,
        )
        if result.returncode != 0:
            failures.append(format_failure(project_dir.as_posix(), result))

    if failures:
        raise SystemExit("\n\n".join(failures))


if __name__ == "__main__":
    main()
