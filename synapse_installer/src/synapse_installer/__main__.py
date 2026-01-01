# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import sys
from pathlib import Path
from typing import Callable, Dict, List

from .util import NOT_IN_SYNAPSE_PROJECT_ERR, SYNAPSE_PROJECT_FILE

HELP_TEXT = """
Usage: python -m synapse_installer <command> [options]

Commands:
  create       Create a new project
  deploy       Deploy the project
  sync         Sync files or data
  install      Run sync then deploy
  device       Device actions (e.g. `add`)
"""


def cmd_create(args: List[str]) -> int:
    if args and args[0] in ("-h", "--help"):
        print("Usage: python -m synapse_installer create\nCreate a new project.")
        return 0

    from .create import createProject

    createProject()
    return 0


def cmd_deploy(args: List[str]) -> int:
    if args and args[0] in ("-h", "--help"):
        print("Usage: python -m synapse_installer deploy [hostnames]")
        return 0

    from .deploy import setupAndRunDeploy

    setupAndRunDeploy(args)
    return 0


def cmd_sync(args: List[str]) -> int:
    from .sync import sync

    return sync(args)


def cmd_install(args: List[str]) -> int:
    if args and args[0] in ("-h", "--help"):
        print("Usage: python -m synapse_installer install [hostnames]")
        return 0

    from .deploy import setupAndRunDeploy
    from .sync import sync

    result_sync = sync(args)
    result_deploy = setupAndRunDeploy(args)
    return 0 if result_sync == 0 and result_deploy == 0 else 1


def cmd_device(args: List[str]) -> int:
    if not args or args[0] in ("-h", "--help"):
        print("Usage: python -m synapse_installer device add")
        return 0

    config_path = Path.cwd() / SYNAPSE_PROJECT_FILE
    if not config_path.exists():
        print(NOT_IN_SYNAPSE_PROJECT_ERR)
        return 1

    action = args[0]

    if action == "add":
        from synapse_installer.deploy import addDeviceConfig

        addDeviceConfig(config_path)
        return 0

    print(f"Unknown device action: `{action}`")
    return 1


COMMANDS: Dict[str, Callable[[List[str]], int]] = {
    "create": cmd_create,
    "deploy": cmd_deploy,
    "sync": cmd_sync,
    "install": cmd_install,
    "device": cmd_device,
}


def main() -> None:
    argv = sys.argv[1:]

    if not argv or argv[0] in ("-h", "--help"):
        print(HELP_TEXT)
        sys.exit(0)

    cmd, *args = argv
    handler = COMMANDS.get(cmd)

    if not handler or handler is None:
        print(f"Unknown command: `{cmd}`\n{HELP_TEXT}")
        sys.exit(1)
        return

    sys.exit(handler(args))


if __name__ == "__main__":
    main()
