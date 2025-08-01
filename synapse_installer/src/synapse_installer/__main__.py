import sys

COMMAND_ARGV_IDX = 1


def main():
    argv = sys.argv

    cmd = argv[COMMAND_ARGV_IDX]

    if cmd == "deploy":
        from .deploy import setupAndRunDeploy

        setupAndRunDeploy(argv[1::])
    elif cmd == "create":
        from .create import createProject

        createProject()
    elif cmd == "sync":
        from .sync import sync

        sync(argv[1::])
    elif cmd == "install":
        from .deploy import setupAndRunDeploy
        from .sync import sync

        sync(argv[1::])
        setupAndRunDeploy(argv[1::])
    else:
        print(f"Unknown command: `{cmd}`!\nvalid commands: `create` or `deploy`")


if __name__ == "__main__":
    main()
