# jaudible

[![PyPI](https://img.shields.io/pypi/v/jaudible?style=flat-square)](https://pypi.python.org/pypi/jaudible/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/jaudible?style=flat-square)](https://pypi.python.org/pypi/jaudible/)
[![PyPI - License](https://img.shields.io/pypi/l/jaudible?style=flat-square)](https://pypi.python.org/pypi/jaudible/)


---

**Source Code**: [https://github.com/jamesls/jaudible](https://github.com/jamesls/jaudible)
**PyPI**: [https://pypi.org/project/jaudible/](https://pypi.org/project/jaudible/)

---

Generate audio books from text documents

## Installation

```sh
pip install jaudible
```

## Development

This project requires at Python 3.12 and uses
[uv](https://docs.astral.sh/uv/) to manage dependencies.

Once you've created and activated your virtual environment, run:

```sh
uv sync
```

This will install all necessary dependencies and install this project
in editable mode.


### Testing

[Poe the Poet](https://github.com/nat-n/poethepoet) is the task runner
used for this project, it's automatically installed as part of the
`poetry install` step.  To see a list of available tasks, run the
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

The `jmes-tts` command is the main interface for converting text to speech. It offers several options to customize the conversion process.

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
- `--language`: Language of phrase (default: en)

For languages you can specify `en` for English (the default), `fr` for French, and `es` for Spanish.

### Converting a File

For longer texts, you can specify an S3 bucket and the path to a local file:

```sh
jmes-tts --filename long_text.txt --bucket my-s3-bucket --output long_audio.mp3
```

### Notes

- You must provide either `--filename` or `--text`, but not both.
- If you provide `--filename` you must also provide `--bucket`.
- If no output file is specified, the audio will be saved as
  `output.mp3` in the current directory.
