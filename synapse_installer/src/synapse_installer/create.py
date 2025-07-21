import os
from pathlib import Path
from typing import Final, Optional

import questionary
from .deploy import loadDeviceData

baseMainPy: Final[str] = """import os
from pathlib import Path

from synapse.core import Synapse


def main():
    Synapse.createAndRunRuntime(root=Path(os.getcwd()))


if __name__ == "__main__":
    main()""".lstrip()


def createProject() -> None:
    cwd: Path = Path.cwd()
    projectName = ""
    print(
        "This will create a folder with the provided project name\nat the current working directory with the project files inside it"
    )
    while projectName is None or len(projectName) == 0:
        projectName: Optional[str] = questionary.text("Project Name").ask()
        if projectName is None:
            return

    projectPath = cwd / projectName
    if not projectPath.exists():
        os.makedirs(projectPath)

    with open(projectPath / ".synapseproject", "w") as projectFile:
        projectFile.write(f"name: {projectName}")

    deployConfigPath = projectPath / ".deployconfig"
    setupDeviceConfig = questionary.confirm("Setup coprocessor info").ask()
    if setupDeviceConfig:
        loadDeviceData(deployConfigPath)
    with open(projectPath / "main.py", "w") as f:
        f.write(baseMainPy)

    if not (projectPath / "pipelines").exists():
        os.makedirs(projectPath / "pipelines")
    deployDir = projectPath / "deploy"
    if not (deployDir).exists():
        os.makedirs(deployDir)
    deployReadme = f"# {projectName} Deploy Directory\nPlace here all files you want to deploy onto the coprocessor"

    with open(deployDir / "readme.md", "w") as readmeFile:
        readmeFile.write(deployReadme)

    print(f"Created project `{projectName}` at:\n{projectPath.absolute()}")
