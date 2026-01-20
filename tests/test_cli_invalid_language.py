from typer.testing import CliRunner

import jmestts.cli as cli
from jmestts.voices import LANGUAGES


def test_unknown_language_lists_valid_languages() -> None:
    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        [
            '--text',
            'Hello',
            '--language',
            'klingon',
            '--dry-run',
        ],
    )

    assert result.exit_code == 1
    assert "Error: Invalid language: klingon." in result.output
    assert "Valid languages:" in result.output
    assert "Traceback" not in result.output
    for language in sorted(LANGUAGES):
        assert language in result.output
