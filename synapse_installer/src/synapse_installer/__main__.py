import sys

COMMAND_ARGV_IDX = 1

if __name__ == "__main__":
    argv = sys.argv
    argc = len(argv)

    cmd = argv[COMMAND_ARGV_IDX]

    if cmd == "deploy":
        from .deploy import setupAndRunDeploy

        setupAndRunDeploy(argv[1::])
    elif cmd == "create":
        from .create import createProject

        createProject()
    else:
        print(f"Unknown command: `{cmd}`!\nvalid commands: `create` or `deploy`")
