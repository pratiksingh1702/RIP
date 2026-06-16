from pathlib import Path


def test_phase0_expected_paths_exist() -> None:
    root = Path(__file__).resolve().parents[2]
    expected_paths = [
        root / "pyproject.toml",
        root / "docker-compose.yml",
        root / "cli" / "main.py",
        root / "server" / "app.py",
        root / "core" / "parser" / "base.py",
        root / "vscode-extension" / "package.json",
        root / "tests" / "fixtures" / "sample_repos" / "python_simple" / "app.py",
    ]

    missing = [str(path.relative_to(root)) for path in expected_paths if not path.exists()]
    assert missing == []
