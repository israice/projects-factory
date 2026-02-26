#!/usr/bin/env python3
from __future__ import annotations

import argparse
import io
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path


VERSION_PATTERN = re.compile(r"^\s*v(\d+)\.(\d+)\.(\d+)\b", re.MULTILINE)


def run_git(repo_root: Path, args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    return result.stdout


def parse_next_version(version_text: str) -> str:
    matches = list(VERSION_PATTERN.finditer(version_text))
    if not matches:
        return "v0.0.1"
    major, minor, patch = map(int, matches[-1].groups())
    return f"v{major}.{minor}.{patch + 1}"


def parse_name_status(raw: str) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            continue
        status, path = parts
        if "->" in path:
            path = path.split("->", 1)[1].strip()
        items.append((status, path))
    return items


def scope_from_path(path: str) -> str:
    p = path.replace("\\", "/")
    if p.startswith("FRONTEND/"):
        return "frontend"
    if p.startswith("BACKEND/"):
        return "backend"
    if p.startswith("TEST") or "/TEST" in p:
        return "tests"
    if p in ("main.py", "run.py"):
        return "server"
    if p.startswith(".github/"):
        return "ci"
    if p.endswith(".md"):
        return "docs"
    return "project"


def summarize_changed_files(items: list[tuple[str, str]]) -> str:
    if not items:
        return "working tree clean"
    scopes = [scope_from_path(path) for _, path in items]
    scope_counts = Counter(scopes)
    top_scopes = [name for name, _ in scope_counts.most_common(2)]
    return " + ".join(top_scopes)


def infer_highlights(diff_text: str) -> list[str]:
    text = diff_text.lower()
    rules: list[tuple[str, str]] = [
        ("open-folder-explorer", "added project folder open action"),
        ("open-repository", "added repository link button"),
        ("action-btn", "updated action buttons"),
        ("/api/", "updated backend logic"),
        ("confirmdialog", "added confirmation dialog"),
        ("rename", "added project rename action"),
        ("push", "added Push button in project row panel"),
        ("delete", "improved project delete flow"),
        ("rownum", "updated project row behavior"),
        ("version.md", "updated versioning"),
    ]
    highlights: list[str] = []
    for needle, phrase in rules:
        if needle in text and phrase not in highlights:
            highlights.append(phrase)
        if len(highlights) >= 3:
            break
    return highlights


def scope_to_human(scope_text: str) -> str:
    mapping = {
        "frontend": "updated frontend",
        "backend": "updated backend",
        "tests": "updated tests",
        "server": "updated server",
        "ci": "updated CI",
        "docs": "updated documentation",
        "project": "updated project",
    }
    parts = [p.strip() for p in scope_text.split("+")]
    human_parts = [mapping.get(part, "updated project") for part in parts if part]
    return " and ".join(human_parts) if human_parts else "updated project"


def build_human_summary(repo_root: Path) -> str:
    raw_status = run_git(repo_root, ["status", "--porcelain", "--untracked-files=all"])
    status_items = parse_name_status(raw_status)
    if not status_items:
        return "working tree clean"

    raw_diff = run_git(repo_root, ["diff", "--", ".", ":(exclude)VERSION.md"])
    raw_diff_cached = run_git(repo_root, ["diff", "--cached", "--", ".", ":(exclude)VERSION.md"])
    combined_diff = f"{raw_diff}\n{raw_diff_cached}"[:20000]

    scope_text = summarize_changed_files(status_items)
    highlights = infer_highlights(combined_diff)

    if highlights:
        return "; ".join(highlights)
    return scope_to_human(scope_text)


def build_version_line(version_text: str, summary: str) -> str:
    next_version = parse_next_version(version_text)
    return f"{next_version} - {summary}"


def append_line(version_file: Path, line: str) -> None:
    text = version_file.read_text(encoding="utf-8") if version_file.exists() else ""
    needs_newline = bool(text) and not text.endswith("\n")
    with version_file.open("a", encoding="utf-8", newline="\n") as f:
        if needs_newline:
            f.write("\n")
        f.write(line + "\n")


def print_safe(text: str) -> None:
    try:
        if isinstance(sys.stdout, io.TextIOWrapper):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        print(text)
    except UnicodeEncodeError:
        encoding = sys.stdout.encoding or "utf-8"
        safe_text = text.encode(encoding, errors="replace").decode(encoding, errors="replace")
        print(safe_text)


def main() -> int:
    parser = argparse.ArgumentParser(description="Append next version line to VERSION.md")
    parser.add_argument("--dry-run", action="store_true", help="Print generated line without writing VERSION.md")
    parser.add_argument("--message", type=str, default="", help="Manual short message instead of auto summary")
    parser.add_argument("repo_path", nargs="?", default=".", help="Target project path")
    args = parser.parse_args()

    repo_root = Path(args.repo_path).expanduser().resolve()
    version_file = repo_root / "VERSION.md"

    version_text = version_file.read_text(encoding="utf-8") if version_file.exists() else ""
    summary = args.message.strip() or build_human_summary(repo_root)
    line = build_version_line(version_text, summary)

    if not args.dry_run:
        append_line(version_file, line)
    print_safe(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
