"""Allow running the CLI as: `python -m opscode`."""

def main() -> None:
    from opscode.cli.main import cli_main
    cli_main()

if __name__ == "__main__":
    main()
