import typer
import sys

from jaudible.tts import TextToSpeech, LongFormTextToSpeech

app = typer.Typer()


@app.command()
def tts(
    filename: str = typer.Option(None, help="Input file to convert to speech"),
    text: str = typer.Option(None, help="Text to convert to speech"),
    bucket: str = typer.Option('', help="S3 bucket for long-form text"),
    output: str = typer.Option('output.mp3', help="Output audio file"),
):
    sys.excepthook = sys.__excepthook__

    if text is None and filename is None:
        typer.echo(
            "Error: Either --filename or --text must be provided", err=True
        )
        raise typer.Exit(code=1)

    if text is not None:
        print("Converting provided text to speech")
        contents = text
        tts = TextToSpeech()
    else:
        if bucket is None:
            typer.echo(
                "Error: --bucket must be provided when using --filename",
                err=True,
            )
            raise typer.Exit(code=1)
        print(f"Converting {filename} to speech")
        with open(filename) as f:
            contents = f.read()
        tts = LongFormTextToSpeech(bucket=bucket)

    stream = tts.convert_to_speech(contents)
    print(f"Num chars used: {tts.last_request_chars}")
    with open(output, 'wb') as f:
        f.write(stream.read())


if __name__ == "__main__":
    app()
