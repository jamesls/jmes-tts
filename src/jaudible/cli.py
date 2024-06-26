import typer
import sys

import boto3

from jaudible.tts import TextToSpeech

app = typer.Typer()


@app.command()
def tts(filename: str, bucket: str = '', output: str = 'output.mp3'):
    sys.excepthook = sys.__excepthook__
    print(f"Converting {filename} to speech")
    with open(filename) as f:
        contents = f.read()
    session = boto3.Session()
    tts = TextToSpeech(bucket=bucket, session=session)
    stream = tts.convert_to_speech(contents)
    print(f"Num chars used: {tts.last_request_chars}")
    with open(output, 'wb') as f:
        f.write(stream.read())


if __name__ == "__main__":
    app()
