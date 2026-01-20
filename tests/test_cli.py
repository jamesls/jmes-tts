from pathlib import Path

from typer.testing import CliRunner

import jmestts.cli as cli
from jmestts.pricing import PRICES


def _deny_aws_calls(*_args: object, **_kwargs: object) -> object:
    raise AssertionError("dry-run must not create AWS clients")


def test_dry_run_prints_chars_and_estimated_cost(monkeypatch):
    runner = CliRunner()
    monkeypatch.setattr(cli, "create_tts_client", _deny_aws_calls)

    text = "Hello  World"
    result = runner.invoke(
        cli.app, ["--text", text, "--engine", "standard", "--dry-run"]
    )

    expected_chars = 11
    expected_cost = PRICES["standard"] * expected_chars / 1_000_000

    assert result.exit_code == 0, result.output
    assert f"Num chars used: {expected_chars}" in result.output
    assert f"Total cost: ${expected_cost:.6f} USD" in result.output
    assert "Dry run: no AWS calls made." in result.output


def test_dry_run_does_not_write_output_file(monkeypatch):
    runner = CliRunner()
    monkeypatch.setattr(cli, "create_tts_client", _deny_aws_calls)

    with runner.isolated_filesystem():
        output_path = Path("dry_run.mp3")
        result = runner.invoke(
            cli.app,
            [
                "--text",
                "Hello",
                "--output",
                str(output_path),
                "--dry-run",
            ],
        )

        assert result.exit_code == 0, result.output
        assert not output_path.exists()


def test_dry_run_validates_3k_limit_for_sync_cases(monkeypatch):
    runner = CliRunner()
    monkeypatch.setattr(cli, "create_tts_client", _deny_aws_calls)

    result = runner.invoke(cli.app, ["--text", "A" * 3001, "--dry-run"])

    assert result.exit_code == 1
    assert "exceeds the max of 3000" in result.output
    assert "--bucket" in result.output


def test_dry_run_skips_3k_validation_when_bucket_provided(monkeypatch):
    runner = CliRunner()
    monkeypatch.setattr(cli, "create_tts_client", _deny_aws_calls)

    result = runner.invoke(
        cli.app, ["--text", "A" * 3001, "--bucket", "b", "--dry-run"]
    )

    assert result.exit_code == 0, result.output
    assert "Num chars used: 3001" in result.output
