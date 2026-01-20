from typer.testing import CliRunner

import jmestts.cli as cli
from jmestts.tts import list_polly_language_codes
from jmestts.voices import LANGUAGES


def test_list_languages_prints_presets_and_polly_codes() -> None:
    runner = CliRunner()
    result = runner.invoke(cli.app, ['--list-languages'])

    assert result.exit_code == 0, result.output

    output_lines = result.output.splitlines()
    assert 'Language presets (--language):' in output_lines
    for name in LANGUAGES:
        assert any(line.startswith(f'- {name}:') for line in output_lines)
    assert 'Polly language codes (--language-code):' in output_lines
    for code in list_polly_language_codes():
        assert f'- {code}' in output_lines
