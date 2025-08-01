import sys

COMMAND_ARGV_IDX = 1

HELP_TEXT = """
Usage: <python> -m synapse_installer <command> [options]

Commands:
  create       Create a new project
  deploy       Deploy the project
  sync         Sync files or data
  install      Run sync then deploy

Use `<python> -m synapse_installer <command> -h` for more information on a command.
"""


def main():
    argv = sys.argv

    if len(argv) <= COMMAND_ARGV_IDX:
        print(HELP_TEXT)
        return

    cmd = argv[COMMAND_ARGV_IDX]

    if cmd in ("-h", "--help"):
        print(HELP_TEXT)
        return

    if cmd == "deploy":
        from .deploy import setupAndRunDeploy

        # If user requests help for deploy
        if len(argv) > COMMAND_ARGV_IDX + 1 and argv[COMMAND_ARGV_IDX + 1] in (
            "-h",
            "--help",
        ):
            print(
                "Usage: <python> -m synapse_installer deploy [hostnames]\nDeploy the project."
            )
            return

        setupAndRunDeploy(argv[1:])
    elif cmd == "create":
        from .create import createProject

        if len(argv) > COMMAND_ARGV_IDX + 1 and argv[COMMAND_ARGV_IDX + 1] in (
            "-h",
            "--help",
        ):
            print("Usage: <python> -m synapse_installer create\nCreate a new project.")
            return

        createProject()
    elif cmd == "sync":
        from .sync import sync

        if len(argv) > COMMAND_ARGV_IDX + 1 and argv[COMMAND_ARGV_IDX + 1] in (
            "-h",
            "--help",
        ):
            print(
                "Usage: <python> -m synapse_installer sync [hostnames]\nSync files or data."
            )
            return

        sync(argv[1:])
    elif cmd == "install":
        from .deploy import setupAndRunDeploy
        from .sync import sync

        if len(argv) > COMMAND_ARGV_IDX + 1 and argv[COMMAND_ARGV_IDX + 1] in (
            "-h",
            "--help",
        ):
            print(
                "Usage: <python> -m synapse_installer install [hostnames]\nRun sync then deploy."
            )
            return

        sync(argv[1:])
        setupAndRunDeploy(argv[1:])
    else:
        print(f"Unknown command: `{cmd}`!\n{HELP_TEXT}")


if __name__ == "__main__":
    main()
