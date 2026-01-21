import sys
from importlib.metadata import version

import typer

from jmestts.tts import (
    InvalidLanguageError,
    TextTooLongError,
    count_chars,
    create_tts_client,
    estimate_cost,
    list_polly_language_codes,
    resolve_tts_params,
    validate_max_chars,
)
from jmestts.voices import LANGUAGES

app = typer.Typer()


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"jmes-tts {version('jmes-tts')}")
        raise typer.Exit()


def _print_languages() -> None:
    typer.echo('Language presets (--language):')
    for name in sorted(LANGUAGES):
        preset = LANGUAGES[name]
        typer.echo(
            f'- {name}: voice={preset["voice"]} engine={preset["engine"]} '
            f'language_code={preset["language_code"]}'
        )
    typer.echo()
    typer.echo('Polly language codes (--language-code):')
    for code in list_polly_language_codes():
        typer.echo(f'- {code}')


@app.command()
def tts(
    filename: str | None = typer.Option(
        None, help="Input file to convert to speech"
    ),
    text: str | None = typer.Option(None, help="Text to convert to speech"),
    bucket: str | None = typer.Option(
        None, help="S3 bucket for long-form text"
    ),
    output: str = typer.Option('output.mp3', help="Output audio file"),
    language: str | None = typer.Option(
        None, help="Language of phrase (e.g. english, french)"
    ),
    language_code: str | None = typer.Option(
        None, help="Language code override (e.g. en-US, fr-FR)"
    ),
    voice: str | None = typer.Option(
        None, help="Voice to use for text-to-speech"
    ),
    engine: str | None = typer.Option(
        None, help="TTS engine (neural or generative)"
    ),
    list_languages: bool = typer.Option(
        False,
        '--list-languages',
        help=('List language presets and Polly language codes, then exit'),
    ),
    dry_run: bool = typer.Option(
        False,
        help=(
            "Estimate cost and validate parameters without "
            "making any AWS calls"
        ),
    ),
    version: bool | None = typer.Option(
        None,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
) -> None:
    sys.excepthook = sys.__excepthook__

    if list_languages:
        _print_languages()
        raise typer.Exit(code=0)

    if text is None and filename is None:
        typer.echo(
            "Error: Either --filename or --text must be provided", err=True
        )
        raise typer.Exit(code=1)
    if text is not None and filename is not None:
        typer.echo(
            "Error: Provide either --filename or --text, but not both",
            err=True,
        )
        raise typer.Exit(code=1)

    contents: str
    if filename is not None:
        with open(filename) as f:
            contents = f.read()
    else:
        assert text is not None
        contents = text

    if dry_run:
        try:
            resolved = resolve_tts_params(
                language,
                voice=voice,
                engine=engine,
                language_code=language_code,
            )
            if bucket is None:
                validate_max_chars(contents)
        except (InvalidLanguageError, TextTooLongError) as exc:
            typer.echo(f"Error: {exc}", err=True)
            raise typer.Exit(code=1) from exc

        billable_chars = count_chars(contents)
        resolved_engine: str = resolved['engine']
        estimated_cost = estimate_cost(
            engine=resolved_engine, billable_chars=billable_chars
        )
        print(f"Num chars used: {billable_chars}")
        print(f"Total cost: ${estimated_cost:.6f} USD")
        print("Dry run: no AWS calls made.")
        raise typer.Exit(code=0)

    try:
        tts = create_tts_client(
            contents=text,
            filename=filename,
            bucket=bucket,
            language=language,
            language_code=language_code,
            voice=voice,
            engine=engine,
        )
    except InvalidLanguageError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    try:
        stream = tts.convert_to_speech(contents)
    except TextTooLongError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    print(f"Num chars used: {tts.last_request_chars}")
    print(f"Total cost: ${tts.last_cost:.6f} USD")
    with open(output, 'wb') as f:
        f.write(stream.read())
    print(f"Output written to {output}")


if __name__ == "__main__":
    app()
