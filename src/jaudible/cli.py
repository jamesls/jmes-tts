import typer
import sys

from jaudible.tts import TextTooLongError, create_tts_client

app = typer.Typer()


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
    language: str = typer.Option(
        'english', help="Language of phrase (e.g. english, french)"
    ),
    voice: str | None = typer.Option(
        None, help="Voice to use for text-to-speech"
    ),
    engine: str | None = typer.Option(
        None, help="TTS engine (neural or generative)"
    ),
):
    sys.excepthook = sys.__excepthook__

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

    tts = create_tts_client(
        contents=text,
        filename=filename,
        bucket=bucket,
        language=language,
        voice=voice,
        engine=engine,
    )
    contents: str
    if filename is not None:
        with open(filename) as f:
            contents = f.read()
    else:
        assert text is not None
        contents = text
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
