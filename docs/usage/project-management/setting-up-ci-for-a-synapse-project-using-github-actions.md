# Setting up CI for a Synapse Project using GitHub Actions

{% hint style="success" %}
This part is mostly taken from [WPILib's Robot Code CI tutorial](https://docs.wpilib.org/en/stable/docs/software/advanced-gradlerio/robot-code-ci.html)
{% endhint %}

An important aspect of working in a team environment is being able to test code that is pushed to a central repository such as GitHub. For example, a project manager or lead developer might want to run a set of unit tests before merging a pull request or might want to ensure that all code on the main branch of a repository is in working order.

[GitHub Actions](https://github.com/features/actions) is a service that allows for teams and individuals to build and run unit tests on code on various branches and on pull requests. These types of services are more commonly known as “Continuous Integration” services. This tutorial will show you how to setup GitHub Actions on robot code projects.&#x20;

{% hint style="info" %}
This tutorial assumes that your team’s robot code is being hosted on GitHub. For an introduction to Git and GitHub, please see this [introduction guide](https://docs.wpilib.org/en/stable/docs/software/basic-programming/git-getting-started.html).
{% endhint %}

## Example Actions File

{% hint style="info" %}
In this example, the project dir is defined as a variable where possible, and the action will only be ran when files in that directory are modified
{% endhint %}

```yaml
name: Synapse Project CI

# Controls when the action will run. Triggers the workflow on push or pull request
# events but only for the main branch.
on:
  push:
    branches:
      - main
    paths:
      - "synapse_opi/**"
  pull_request:
    paths:
      - "synapse_opi/**"

env:
  PYTHON_VERSION: "3.10.7"
  PROJECT_DIR: "synapse_opi"

jobs:
  build:
    # The type of runner that the job will run on
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Install Synapse Runtime
        run: |
          pip install synapsefrc

      - name: Compile all Python files
        run: python -m compileall -q $PROJECT_DIR

  lint:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Install Ruff and isort
        run: pip install ruff isort

      - name: Run Ruff linting
        run: ruff check $PROJECT_DIR

      - name: Run isort check
        run: isort --check-only --diff $PROJECT_DIR

  type-check:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Install Synapse Runtime
        run: |
          pip install synapsefrc

      - name: Install Pyright
        run: pip install pyright

      - name: Run Pyright type checks
        run: pyright $PROJECT_DIR
```
