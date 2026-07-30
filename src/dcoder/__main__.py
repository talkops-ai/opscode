"""Allow running the CLI as: `python -m dcoder`."""

def main() -> None:
    from dcoder.cli.main import cli_main
    cli_main()

if __name__ == "__main__":
    main()
