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

This project requires at Python 3.9+ and uses
[Poetry](https://python-poetry.org/) to manage dependencies.

Once you've created and activated your virtual environment, run:

```sh
poetry install
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
