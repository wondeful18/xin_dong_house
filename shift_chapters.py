from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


TITLE_RE = re.compile(r'^(title:\s*"第)([零〇一二两三四五六七八九十百千]+)(章)', re.MULTILINE)
FILENAME_RE = re.compile(r"^ch(\d+)\.md$")
CHINESE_DIGITS = {
    "零": 0,
    "〇": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}


@dataclass
class ChapterFile:
    path: Path
    chapter_no: int
    title_no: int
    text: str


@dataclass
class RenameStep:
    chapter: ChapterFile
    new_no: int
    new_path: Path
    new_text: str


def chinese_to_int(text: str) -> int:
    if not text:
        raise ValueError("empty Chinese numeral")

    total = 0
    current = 0
    unit_map = {"十": 10, "百": 100, "千": 1000}

    for ch in text:
        if ch in CHINESE_DIGITS:
            current = CHINESE_DIGITS[ch]
        elif ch in unit_map:
            unit = unit_map[ch]
            if current == 0:
                current = 1
            total += current * unit
            current = 0
        else:
            raise ValueError(f"unsupported Chinese numeral: {text}")

    return total + current


def int_to_chinese(num: int) -> str:
    if num <= 0:
        raise ValueError("chapter number must be positive")
    digits = "零一二三四五六七八九"
    if num < 10:
        return digits[num]
    if num < 100:
        tens, ones = divmod(num, 10)
        prefix = "十" if tens == 1 else digits[tens] + "十"
        return prefix if ones == 0 else prefix + digits[ones]
    if num < 1000:
        hundreds, remainder = divmod(num, 100)
        prefix = digits[hundreds] + "百"
        if remainder == 0:
            return prefix
        if remainder < 10:
            return prefix + "零" + int_to_chinese(remainder)
        return prefix + int_to_chinese(remainder)
    if num < 10000:
        thousands, remainder = divmod(num, 1000)
        prefix = digits[thousands] + "千"
        if remainder == 0:
            return prefix
        if remainder < 100:
            return prefix + "零" + int_to_chinese(remainder)
        return prefix + int_to_chinese(remainder)
    raise ValueError("chapter number too large")


def discover_chapter_files(root: Path) -> tuple[list[ChapterFile], list[tuple[Path, str]]]:
    chapters: list[ChapterFile] = []
    skipped: list[tuple[Path, str]] = []

    for subdir in sorted(p for p in root.iterdir() if p.is_dir() and p.name.startswith("v")):
        for path in sorted(subdir.glob("ch*.md")):
            match = FILENAME_RE.match(path.name)
            if not match:
                skipped.append((path, "filename does not match ch<number>.md"))
                continue

            chapter_no = int(match.group(1))
            text = path.read_text(encoding="utf-8")
            title_match = TITLE_RE.search(text)
            if not title_match:
                skipped.append((path, "title line does not start with 第...章"))
                continue

            try:
                title_no = chinese_to_int(title_match.group(2))
            except ValueError as exc:
                skipped.append((path, str(exc)))
                continue

            if title_no != chapter_no:
                skipped.append((path, f"title chapter {title_no} does not match filename {chapter_no}"))
                continue

            chapters.append(ChapterFile(path=path, chapter_no=chapter_no, title_no=title_no, text=text))

    chapters.sort(key=lambda item: item.chapter_no)
    return chapters, skipped


def replace_title_number(text: str, new_no: int) -> str:
    chinese = int_to_chinese(new_no)

    def repl(match: re.Match[str]) -> str:
        return f"{match.group(1)}{chinese}{match.group(3)}"

    updated, count = TITLE_RE.subn(repl, text, count=1)
    if count != 1:
        raise ValueError("failed to update title chapter number")
    return updated


def build_plan(chapters: list[ChapterFile], start: int, delta: int) -> list[RenameStep]:
    plan: list[RenameStep] = []
    for chapter in chapters:
        if chapter.chapter_no < start:
            continue
        new_no = chapter.chapter_no + delta
        if new_no <= 0:
            raise ValueError("resulting chapter number must stay positive")
        new_path = chapter.path.with_name(f"ch{new_no:02d}.md")
        new_text = replace_title_number(chapter.text, new_no)
        plan.append(RenameStep(chapter=chapter, new_no=new_no, new_path=new_path, new_text=new_text))
    return plan


def detect_conflicts(plan: list[RenameStep]) -> list[str]:
    moving_from = {step.chapter.path.resolve() for step in plan}
    conflicts: list[str] = []
    for step in plan:
        target = step.new_path.resolve()
        if target == step.chapter.path.resolve():
            continue
        if target.exists() and target not in moving_from:
            conflicts.append(f"{step.new_path} already exists and is not part of this move set")
    return conflicts


def run_git(root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def get_git_state(root: Path) -> tuple[bool, str]:
    inside = run_git(root, ["rev-parse", "--is-inside-work-tree"])
    if inside.returncode != 0:
        message = inside.stderr.strip() or inside.stdout.strip() or "not a git repository"
        return False, message
    status = run_git(root, ["status", "--short"])
    if status.returncode != 0:
        message = status.stderr.strip() or status.stdout.strip() or "unable to read git status"
        return True, f"git repository detected, but status check failed: {message}"
    dirty = "clean" if not status.stdout.strip() else "has uncommitted changes"
    return True, dirty


def print_plan(root: Path, start: int, delta: int, skipped: list[tuple[Path, str]], plan: list[RenameStep]) -> None:
    direction = "by" if delta >= 0 else "backward by"
    amount = delta if delta >= 0 else -delta
    print(f"Root: {root}")
    print(f"Shifting chapters >= {start} {direction} {amount}")
    print(f"Planned updates: {len(plan)}")

    if skipped:
        print("\nSkipped files:")
        for path, reason in skipped:
            print(f"  - {path.relative_to(root)}: {reason}")

    print("\nPlanned renames:")
    for step in plan:
        old_rel = step.chapter.path.relative_to(root)
        new_rel = step.new_path.relative_to(root)
        print(f"  - {old_rel} -> {new_rel}")

    print("\nPlanned title updates:")
    for step in plan[:10]:
        old_cn = int_to_chinese(step.chapter.chapter_no)
        new_cn = int_to_chinese(step.new_no)
        print(f"  - 第{old_cn}章 -> 第{new_cn}章 ({step.chapter.path.relative_to(root)})")
    if len(plan) > 10:
        print(f"  ... and {len(plan) - 10} more")


def confirm_execution() -> bool:
    answer = input("\nProceed with these changes? [y/N]: ").strip().lower()
    return answer in {"y", "yes"}


def apply_plan(root: Path, plan: list[RenameStep], use_git: bool) -> None:
    for step in plan:
        step.chapter.path.write_text(step.new_text, encoding="utf-8")

    rename_order = sorted(plan, key=lambda item: item.chapter.chapter_no, reverse=plan[0].new_no > plan[0].chapter.chapter_no)
    for step in rename_order:
        if use_git:
            result = run_git(root, ["mv", str(step.chapter.path), str(step.new_path)])
            if result.returncode != 0:
                message = result.stderr.strip() or result.stdout.strip() or "git mv failed"
                raise RuntimeError(message)
        else:
            step.chapter.path.rename(step.new_path)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Shift chapter filenames and title chapter numbers across vXX subfolders."
    )
    parser.add_argument("start", type=int, help="first chapter number to shift, e.g. 15")
    parser.add_argument("--delta", type=int, default=1, help="how much to shift chapter numbers by; default: 1")
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
    root = args.root.resolve()
    chapters, skipped = discover_chapter_files(root)
    plan = build_plan(chapters, args.start, args.delta)

    if not plan:
        print("No matching chapters to shift.")
        return 0

    conflicts = detect_conflicts(plan)
    if conflicts:
        print("Refusing to run because of filename conflicts:")
        for conflict in conflicts:
            print(f"  - {conflict}")
        return 1

    print_plan(root, args.start, args.delta, skipped, plan)

    git_ok, git_message = get_git_state(root)
    print(f"\nGit: {git_message}")
    if args.use_git and not git_ok:
        print("Cannot use --use-git in the current repository state.")
        return 1

    if args.dry_run:
        print("\nDry run only. No files changed.")
        return 0

    if not args.yes and not confirm_execution():
        print("Aborted.")
        return 1

    try:
        apply_plan(root, plan, use_git=args.use_git)
    except RuntimeError as exc:
        print(f"Failed: {exc}")
        return 1

    mode = "git mv" if args.use_git else "filesystem rename"
    print(f"\nDone via {mode}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
