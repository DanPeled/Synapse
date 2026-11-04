---
description: Run checks on a Synapse project with GitHub Actions.
icon: github
---

# Setting up CI for a Synapse Project using GitHub Actions

Continuous integration (CI) runs checks automatically when code is pushed or a pull request is opened. For a Synapse project, the most useful checks are:

- Every Python file compiles.
- Pipelines import correctly.
- Linting and formatting are consistent.
- Type checks pass (optional).

{% hint style="info" %}
This guide assumes your project is hosted on GitHub. For Git basics, see the [WPILib Git guide](https://docs.wpilib.org/en/stable/docs/software/basic-programming/git-getting-started.html).
{% endhint %}

## Before you start

A Synapse project contains:

```text
.synapseproject
main.py
pipelines/
config/
deploy/
```

If the repository root **is** the project root, use `PROJECT_DIR: "."` in the workflow. If the project lives in a subfolder, set `PROJECT_DIR` to that folder name.

## Example workflow

Create `.github/workflows/synapse-ci.yml`:

```yaml
name: Synapse Project CI

on:
  push:
    branches: [main]
    paths:
      - "pipelines/**"
      - "main.py"
      - "config/**"
      - "deploy/**"
      - ".github/workflows/synapse-ci.yml"
  pull_request:
    paths:
      - "pipelines/**"
      - "main.py"
      - "config/**"
      - "deploy/**"
  workflow_dispatch:

env:
  PYTHON_VERSION: "3.13"
  PROJECT_DIR: "."

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: pip

      - name: Install Synapse runtime
        run: pip install synapsefrc

      - name: Compile Python files
        run: python -m compileall -q $PROJECT_DIR

  lint:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: pip

      - name: Install lint tools
        run: pip install ruff isort

      - name: Ruff
        run: ruff check $PROJECT_DIR

      - name: isort
        run: isort --check-only --diff $PROJECT_DIR

  type-check:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: pip

      - name: Install Synapse runtime and Pyright
        run: |
          pip install synapsefrc pyright

      - name: Run Pyright
        run: pyright $PROJECT_DIR
```

## What each job does

| Job | Purpose |
| --- | --- |
| `build` | Catches syntax errors and import-time failures |
| `lint` | Enforces style with Ruff and import order with isort |
| `type-check` | Catches type errors before they reach the robot |

`compileall` only checks syntax. It does not import your pipelines, so it will not catch a missing dependency or a bad import. If you want to catch those, add a step that imports each pipeline module:

```yaml
      - name: Import pipelines
        run: |
          python - <<'PY'
          import importlib.util
          from pathlib import Path

          for path in Path("pipelines").rglob("*_pipeline.py"):
              spec = importlib.util.spec_from_file_location(path.stem, path)
              module = importlib.util.module_from_spec(spec)
              spec.loader.exec_module(module)
              print("Loaded", path)
          PY
```

## Running tests

If your project has tests, add pytest:

```yaml
      - name: Run tests
        run: |
          pip install pytest
          pytest -q
```

Keep tests independent of the camera, the network, and the robot. Test pure functions such as geometry helpers and result formatting.

## Using a matrix

To check multiple Python versions:

```yaml
jobs:
  build:
    strategy:
      matrix:
        python: ["3.11", "3.12", "3.13"]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python }}
      - run: pip install synapsefrc
      - run: python -m compileall -q .
```

Synapse supports Python 3.11 through 3.14, and the project's CI tests 3.11–3.13.

## Project in a subfolder

If your repository looks like this:

```text
robot-code/
└── synapse_project/
    ├── .synapseproject
    ├── main.py
    └── pipelines/
```

Set:

```yaml
env:
  PROJECT_DIR: "synapse_project"
```

and update the path filters:

```yaml
on:
  push:
    paths:
      - "synapse_project/**"
```

## Caching

`actions/setup-python` with `cache: pip` caches downloaded wheels, which helps because the Synapse runtime pulls in OpenCV and NumPy. If you use a `requirements.txt`, point the cache at it:

```yaml
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: pip
          cache-dependency-path: requirements.txt
```

## Common failures

| Failure | Cause |
| --- | --- |
| `ModuleNotFoundError: synapse` | `pip install synapsefrc` was skipped or ran in a different job |
| `No module named cv2` | The runtime install failed; check the pip log |
| Ruff reports many errors | Run `ruff check --fix` locally first |
| isort check fails | Run `isort .` locally |
| Workflow never runs | The `paths` filter does not match your changed files |
| Pyright reports missing imports | Install the runtime in the type-check job too |

## Next steps

- [Project Management](README.md)
- [Custom Pipelines](../custom-pipelines/README.md)
- [Synapse Manager](synapse-manager.md)
