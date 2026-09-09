import sys


def _boot_notice() -> None:
    if getattr(sys, "frozen", False):
        print("resume-cli 启动中…", file=sys.stderr, flush=True)


def _run() -> None:
    from resume_cli.cli import main

    main()


if __name__ == "__main__":
    _boot_notice()
    _run()
