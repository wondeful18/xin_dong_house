import argparse
import html
import re
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
VOLUMES = [
    ("卷一：初来咋到", ROOT / "v01_chudao"),
]
DEFAULT_TITLE = "心跳出租屋"
DEFAULT_AUTHOR = "余鸣"


def html_heading(level: int, text: str, anchor_id: str | None = None) -> str:
    id_attr = f' id="{anchor_id}"' if anchor_id else ""
    return f"<h{level}{id_attr}>{html.escape(text)}</h{level}>"


def chapter_sort_key(path: Path) -> int:
    match = re.search(r"(\d+)", path.stem)
    if not match:
        raise ValueError(f"无法从文件名提取章节序号: {path}")
    return int(match.group(1))


def split_front_matter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---"):
        return {}, text

    lines = text.splitlines()
    if len(lines) < 3:
        return {}, text

    metadata: dict[str, str] = {}
    end_index = None
    for index in range(1, len(lines)):
        line = lines[index]
        if line.strip() == "---":
            end_index = index
            break
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip('"').strip("'")

    if end_index is None:
        return {}, text

    body = "\n".join(lines[end_index + 1 :]).lstrip()
    return metadata, body


def load_chapter_markdown(path: Path) -> tuple[str, str]:
    text = path.read_text(encoding="utf-8")
    metadata, body = split_front_matter(text)
    title = metadata.get("title", path.stem)
    return title, body.rstrip()


def collect_book_structure() -> list[tuple[str, list[tuple[Path, str, str]]]]:
    structure: list[tuple[str, list[tuple[Path, str, str]]]] = []

    for volume_index, (volume_title, volume_dir) in enumerate(VOLUMES, start=1):
        if not volume_dir.is_dir():
            raise FileNotFoundError(f"目录不存在: {volume_dir}")

        chapter_files = sorted(volume_dir.glob("ch*.md"), key=chapter_sort_key)
        if not chapter_files:
            raise FileNotFoundError(f"目录中未找到章节文件: {volume_dir}")

        chapters: list[tuple[Path, str, str]] = []
        for chapter_index, chapter_file in enumerate(chapter_files, start=1):
            chapter_title, _ = load_chapter_markdown(chapter_file)
            anchor_id = f"v{volume_index:02d}-ch{chapter_index:02d}"
            chapters.append((chapter_file, chapter_title, anchor_id))

        structure.append((volume_title, chapters))

    return structure


def build_inline_toc(
    structure: list[tuple[str, list[tuple[Path, str, str]]]],
) -> list[str]:
    parts = [html_heading(2, "目录", "toc"), ""]

    for volume_title, chapters in structure:
        parts.extend([html_heading(3, volume_title), ""])
        for _, chapter_title, anchor_id in chapters:
            safe_title = html.escape(chapter_title)
            parts.append(f'<p><a href="#{anchor_id}">{safe_title}</a></p>')
        parts.append("")

    return parts


def build_book_markdown(title: str) -> str:
    structure = collect_book_structure()
    parts = [html_heading(1, title, "book-title"), ""]
    parts.extend(build_inline_toc(structure))

    for volume_title, chapters in structure:
        parts.extend([html_heading(1, volume_title), ""])

        for chapter_file, chapter_title, anchor_id in chapters:
            chapter_title, body = load_chapter_markdown(chapter_file)
            parts.extend([html_heading(2, chapter_title, anchor_id), "", body, ""])

    return "\n".join(parts).rstrip() + "\n"


def ensure_ebook_convert() -> None:
    try:
        subprocess.run(
            ["ebook-convert", "--version"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError as exc:
        raise SystemExit(
            "未找到 ebook-convert。请先安装 Calibre，并将其命令行工具加入 PATH。"
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise SystemExit("ebook-convert 无法正常执行，请检查 Calibre 安装。") from exc


def convert_to_azw3(markdown_text: str, output_path: Path, title: str, author: str) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_md = Path(temp_dir) / "merged_novel.md"
        temp_md.write_text(markdown_text, encoding="utf-8")

        cmd = [
            "ebook-convert",
            str(temp_md),
            str(output_path),
            "--authors",
            author,
            "--title",
            title,
            "--chapter",
            "//*[name()='h1' or name()='h2']",
            "--level1-toc",
            "//*[name()='h1']",
            "--level2-toc",
            "//*[name()='h2']",
            "--page-breaks-before",
            "//*[name()='h2']",
            "--insert-blank-line",
            "--extra-css",
            "body { font-size: 1.2em; line-height: 1.6; }",
        ]
        subprocess.run(cmd, check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="将四卷 Markdown 章节合并并转换为 AZW3。"
    )
    parser.add_argument(
        "-o",
        "--output",
        default=str(ROOT / f"{DEFAULT_TITLE}.azw3"),
        help="输出文件路径，默认生成到项目根目录。",
    )
    parser.add_argument(
        "--title",
        default=DEFAULT_TITLE,
        help="电子书标题。",
    )
    parser.add_argument(
        "--author",
        default=DEFAULT_AUTHOR,
        help="电子书作者。",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ensure_ebook_convert()

    output_path = Path(args.output).resolve()
    markdown_text = build_book_markdown(args.title)
    convert_to_azw3(markdown_text, output_path, args.title, args.author)

    print(f"已生成: {output_path}")


if __name__ == "__main__":
    main()
