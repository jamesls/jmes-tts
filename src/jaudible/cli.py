import typer
import sys

from jaudible.tts import create_tts_client

app = typer.Typer()


@app.command()
def tts(
    filename: str = typer.Option(None, help="Input file to convert to speech"),
    text: str = typer.Option(None, help="Text to convert to speech"),
    bucket: str = typer.Option(None, help="S3 bucket for long-form text"),
    output: str = typer.Option('output.mp3', help="Output audio file"),
    language: str = typer.Option('en', help="Language of phrase"),
):
    sys.excepthook = sys.__excepthook__

    if text is None and filename is None:
        typer.echo(
            "Error: Either --filename or --text must be provided", err=True
        )
        raise typer.Exit(code=1)

    tts = create_tts_client(
        contents=text, filename=filename, bucket=bucket, language=language
    )
    if filename is not None:
        with open(filename) as f:
            contents = f.read()
    else:
        contents = text
    stream = tts.convert_to_speech(contents)
    print(f"Num chars used: {tts.last_request_chars}")
    print(f"Total cost: ${tts.last_cost:.6f} USD")
    with open(output, 'wb') as f:
        f.write(stream.read())
    print(f"Output written to {output}")


if __name__ == "__main__":
    app()
