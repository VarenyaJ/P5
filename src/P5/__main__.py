"""
Deprecated entry point.
We now use the console script `p5` as the canonical CLI.
"""

import sys
import click


def main():
    click.echo(
        "`python -m P5` is deprecated. Please use the console script `p5` instead.\n"
        "Try:  p5 --help",
        err=False,
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
