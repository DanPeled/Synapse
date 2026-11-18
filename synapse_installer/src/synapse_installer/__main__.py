# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import sys
from pathlib import Path
from typing import Callable, Dict, List

from .util import NOT_IN_SYNAPSE_PROJECT_ERR, SYNAPSE_PROJECT_FILE

HELP_TEXT = """
Usage: python -m synapse_installer <command> [options] [devices...]

Commands:
  create       Create a new project
  deploy       Deploy the project to one or more devices
  sync         Install or update Python dependencies on devices
  install      Run sync, then deploy
  device       Manage devices (add, list, remove)

Deploy/install options:
  -y, --yes        Don't ask for confirmation before deploying
  -n, --dry-run    Show the deployment targets without changing anything
      --no-logs    Don't follow the runtime logs after deploying

If no device names are given, deploy and install use every configured device.
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
        print(
            "Usage: python -m synapse_installer deploy [options] [devices...]\n"
            "Options: -y/--yes, -n/--dry-run, --no-logs"
        )
        return 0

    from .deploy import setupAndRunDeploy

    return setupAndRunDeploy(args)


def cmd_sync(args: List[str]) -> int:
    from .sync import sync

    return sync(args)


def cmd_install(args: List[str]) -> int:
    if args and args[0] in ("-h", "--help"):
        print(
            "Usage: python -m synapse_installer install [options] [devices...]\n"
            "Options: -y/--yes, -n/--dry-run, --no-logs"
        )
        return 0

    from .deploy import DeploymentError, parseDeployArgs, setupAndRunDeploy
    from .sync import sync

    try:
        options = parseDeployArgs(args)
    except DeploymentError as error:
        print(f"Error: {error}")
        return 1

    if options.dryRun:
        print("Dry run: skipping dependency sync.")
        return setupAndRunDeploy(options)

    resultSync = sync(options.devices)
    if resultSync != 0:
        print("Sync failed; skipping deployment.")
        return 1

    return setupAndRunDeploy(options)


def cmd_device(args: List[str]) -> int:
    if not args or args[0] in ("-h", "--help"):
        print("Usage: python -m synapse_installer device <add|list|remove> [device]")
        return 0

    configPath = Path.cwd() / SYNAPSE_PROJECT_FILE
    if not configPath.exists():
        print(NOT_IN_SYNAPSE_PROJECT_ERR)
        return 1

    action = args[0]

    if action == "add":
        from synapse_installer.deploy import addDeviceConfig

        addDeviceConfig(configPath)
        return 0

    if action == "list":
        from synapse_installer.deploy import listDevices

        return listDevices(configPath)

    if action == "remove":
        if len(args) < 2:
            print("Usage: python -m synapse_installer device remove <device>")
            return 1

        from synapse_installer.deploy import removeDevice

        return removeDevice(configPath, args[1])

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
