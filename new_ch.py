from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


VOLUME_RE = re.compile(r"^v(\d+)_")
CHAPTER_RE = re.compile(r"^ch(\d+)\.md$")

CHINESE_DIGITS = "零一二三四五六七八九"
CHINESE_UNITS = [(1000, "千"), (100, "百"), (10, "十")]


def int_to_chinese(num: int) -> str:
    if num <= 0:
        raise ValueError("chapter number must be positive")
    if num < 10:
        return CHINESE_DIGITS[num]
    if num < 100:
        tens, ones = divmod(num, 10)
        prefix = "十" if tens == 1 else CHINESE_DIGITS[tens] + "十"
        return prefix if ones == 0 else prefix + CHINESE_DIGITS[ones]
    if num < 10000:
        parts: list[str] = []
        remainder = num
        need_zero = False
        for value, unit in CHINESE_UNITS:
            digit, remainder = divmod(remainder, value)
            if digit:
                if need_zero:
                    parts.append("零")
                    need_zero = False
                parts.append(CHINESE_DIGITS[digit] + unit)
            elif parts and remainder:
                need_zero = True
        if remainder:
            if need_zero:
                parts.append("零")
            parts.append(int_to_chinese(remainder))
        return "".join(parts)
    raise ValueError("chapter number too large")


def find_latest_volume(root: Path) -> Path:
    volumes: list[tuple[int, Path]] = []
    for path in root.iterdir():
        if not path.is_dir():
            continue
        match = VOLUME_RE.match(path.name)
        if match:
            volumes.append((int(match.group(1)), path))
    if not volumes:
        raise FileNotFoundError("no vNN_* directories found")
    return max(volumes, key=lambda item: item[0])[1]


def find_latest_chapter(volume_dir: Path) -> int:
    chapter_numbers: list[int] = []
    for path in volume_dir.iterdir():
        if not path.is_file():
            continue
        match = CHAPTER_RE.match(path.name)
        if match:
            chapter_numbers.append(int(match.group(1)))
    if not chapter_numbers:
        raise FileNotFoundError(f"no chNN.md files found in {volume_dir}")
    return max(chapter_numbers)


def build_header(chapter_no: int) -> str:
    title_no = int_to_chinese(chapter_no)
    return f'---\ntitle: "第{title_no}章："\n---\n'


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create the next chapter file in the latest vNN_* volume directory."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="project root path; default: script directory",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the next chapter path and content without creating the file",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.root.resolve()

    try:
        latest_volume = find_latest_volume(root)
        latest_chapter = find_latest_chapter(latest_volume)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    next_chapter = latest_chapter + 1
    target_path = latest_volume / f"ch{next_chapter:02d}.md"
    content = build_header(next_chapter)

    if target_path.exists():
        print(f"Error: target file already exists: {target_path}", file=sys.stderr)
        return 1

    if args.dry_run:
        print(f"Latest volume: {latest_volume.name}")
        print(f"Latest chapter: ch{latest_chapter:02d}.md")
        print(f"New chapter: {target_path.relative_to(root)}")
        print()
        print(content, end="")
        return 0

    target_path.write_text(content, encoding="utf-8")
    print(f"Created: {target_path.relative_to(root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
