# jmes-tts

Generate audio books from text documents

## Installation

```sh
pip install jmes-tts
```

## Development

This project requires Python 3.12 and uses
[uv](https://github.com/astral-sh/uv) to manage dependencies.

You can create a virtual environment with all the necessary dependencies
by running:

```sh
uv sync --all-extras --dev
```

This will install all necessary dependencies and install this project
in editable mode.

You can activate the venv with:

```sh
. .venv/bin/activate
```

### Testing

[Poe the Poet](https://github.com/nat-n/poethepoet) is the task runner
used for this project, it's automatically installed as part of the
dev dependencies.  To see a list of available tasks, run the
`poe` command with no args.

To run the tests for this project run:


```sh
poe test
```

Before submitting a PR, ensure the `prcheck` task runs successfully:

```sh
poe prcheck
```

## Usage

The `jmes-tts` command is the main interface for converting text to speech.
It offers several options to customize the conversion process.

### Basic Usage

```sh
jmes-tts --text "Hello, world!" --output hello.mp3
```

This will convert the text "Hello, world!" to speech and save it as "hello.mp3".

### Command Options

- `--filename`: Input file to convert to speech
- `--text`: Text to convert to speech
- `--bucket`: S3 bucket for long-form text (optional)
- `--output`: Output audio file (default: output.mp3)
- `--language`: Language of phrase (default: english)
- `--language-code`: Language code override (optional)
- `--voice`: Voice to use for text-to-speech (optional)
- `--engine`: TTS engine (optional)
- `--list-languages`: List language presets and Polly language codes

Supported `--language` values:

- `english` (default)
- `french`
- `spanish`
- `cantonese`
- `mandarin`

Run `jmes-tts --list-languages` to see all presets and the full list of
supported language codes.

### Converting a File

For longer texts, you can specify an S3 bucket and the path to a local file:

```sh
jmes-tts --filename long_text.txt --bucket my-s3-bucket --output long_audio.mp3
```

### Notes

- You must provide either `--filename` or `--text`, but not both.
- If your text is larger than 3000 (billable) characters, you need to provide
  the `--bucket` argument.  Otherwise synchronous TTS will be used.
- If no output file is specified, the audio will be saved as
  `output.mp3` in the current directory.
