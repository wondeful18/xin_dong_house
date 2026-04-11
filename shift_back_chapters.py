from __future__ import annotations

import argparse
from pathlib import Path

import shift_chapters


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Shift chapter filenames and title chapter numbers backward across vXX subfolders."
    )
    parser.add_argument("start", type=int, help="first chapter number to shift back, e.g. 16")
    parser.add_argument("--delta", type=int, default=1, help="how many chapter numbers to move back; default: 1")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="project root; default: script directory",
    )
    parser.add_argument("--dry-run", action="store_true", help="show planned changes without writing files")
    parser.add_argument("--yes", action="store_true", help="skip confirmation prompt")
    parser.add_argument("--use-git", action="store_true", help="use git mv for renames when inside a git repo")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    forwarded = [
        str(args.start),
        "--delta",
        str(-args.delta),
        "--root",
        str(args.root),
    ]
    if args.dry_run:
        forwarded.append("--dry-run")
    if args.yes:
        forwarded.append("--yes")
    if args.use_git:
        forwarded.append("--use-git")
    return shift_chapters.main(forwarded)


if __name__ == "__main__":
    raise SystemExit(main())
