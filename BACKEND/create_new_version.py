#!/usr/bin/env python3
from __future__ import annotations

import argparse
import io
import keyword
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path


VERSION_PATTERN = re.compile(r"^\s*v(\d+)\.(\d+)\.(\d+)\b", re.MULTILINE)
TOKEN_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_]{2,}")


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
    if p in ("run.py", "BACKEND/main.py"):
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


def split_identifier(token: str) -> list[str]:
    parts: list[str] = []
    for chunk in token.split("_"):
        chunk = chunk.strip()
        if not chunk:
            continue
        camel_parts = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)|\d+", chunk)
        parts.extend(camel_parts or [chunk])
    return [p.lower() for p in parts if len(p) >= 3 and not p.isdigit()]


def keyword_counts_from_diff(diff_text: str) -> Counter[str]:
    stop_words = {
        "for",
        "while",
        "if",
        "elif",
        "else",
        "try",
        "except",
        "raise",
        "pass",
        "break",
        "continue",
        "def",
        "str",
        "int",
        "bool",
        "line",
        "lines",
        "word",
        "words",
        "text",
        "count",
        "counter",
        "status",
        "scope",
        "update",
        "updated",
        "project",
        "the",
        "and",
        "with",
        "from",
        "into",
        "true",
        "false",
        "none",
        "null",
        "return",
        "class",
        "const",
        "let",
        "var",
        "function",
        "import",
        "export",
        "default",
        "async",
        "await",
        "self",
        "this",
        "args",
        "path",
        "data",
        "list",
        "dict",
        "string",
        "value",
        "values",
        "items",
        "index",
        "main",
        "utils",
        "helper",
        "helpers",
        "tests",
        "test",
    }
    counts: Counter[str] = Counter()
    for raw_line in diff_text.splitlines():
        if not raw_line.startswith("+"):
            continue
        if raw_line.startswith("+++"):
            continue
        line = raw_line[1:]
        for token in TOKEN_PATTERN.findall(line):
            for word in split_identifier(token):
                if word in stop_words or word in keyword.kwlist or len(word) < 3:
                    continue
                counts[word] += 1
    return counts


def keyword_counts_from_paths(items: list[tuple[str, str]]) -> Counter[str]:
    stop_words = {
        "frontend",
        "backend",
        "version",
        "readme",
        "main",
        "run",
        "test",
        "tests",
        "index",
        "init",
        "app",
        "utils",
        "helper",
        "helpers",
        "create",
        "new",
        "version",
        "python",
        "file",
    }
    counts: Counter[str] = Counter()
    for _, path in items:
        normalized = path.replace("\\", "/")
        for token in TOKEN_PATTERN.findall(normalized):
            for word in split_identifier(token):
                if word in stop_words or word in keyword.kwlist or len(word) < 3:
                    continue
                counts[word] += 1
    return counts


def infer_change_action(items: list[tuple[str, str]], keywords: Counter[str]) -> str:
    statuses = {status for status, _ in items}
    joined = " ".join(keywords.keys())
    if "A" in statuses or "??" in statuses:
        return "add"
    if "D" in statuses:
        return "remove"
    if any(word in joined for word in ("fix", "bug", "error", "guard", "validate", "fallback")):
        return "fix"
    if any(word in joined for word in ("refactor", "rename", "cleanup", "rework")):
        return "refactor"
    return "update"


def infer_feature_phrase(tokens: set[str], scope_human: str) -> str:
    if "version" in tokens and any(t in tokens for t in ("summary", "message", "keyword", "scope", "action")):
        return "auto version message generation"
    if {"api", "request", "response"} & tokens:
        return "API request handling"
    if {"auth", "login", "token", "session"} & tokens:
        return "authentication flow"
    if {"dialog", "modal", "button", "form"} & tokens:
        return "UI interactions"
    if {"error", "exception", "validate", "fallback"} & tokens:
        return "error handling and validation"
    if {"test", "assert", "mock", "fixture"} & tokens:
        return "test coverage"
    if {"config", "settings", "env"} & tokens:
        return "configuration loading"
    if {"rename", "name"} & tokens:
        return "rename behavior"
    if {"delete", "remove"} & tokens:
        return "delete flow"
    if {"create", "new"} & tokens:
        return "creation flow"
    if {"parser", "parse"} & tokens:
        return "parsing logic"
    return f"{scope_human} behavior"


def build_summary_phrase(action: str, feature: str) -> str:
    verb_map = {
        "add": "added",
        "remove": "removed",
        "fix": "fixed",
        "refactor": "refactored",
        "update": "improved",
    }
    verb = verb_map.get(action, "updated")
    return f"{verb} {feature}"


def scope_to_human(scope_text: str) -> str:
    mapping = {
        "frontend": "frontend",
        "backend": "backend",
        "tests": "tests",
        "server": "server",
        "ci": "CI",
        "docs": "documentation",
        "project": "project",
    }
    parts = [p.strip() for p in scope_text.split("+")]
    human_parts = [mapping.get(part, "project") for part in parts if part]
    return " and ".join(human_parts) if human_parts else "project"


def build_human_summary(repo_root: Path) -> str:
    raw_status = run_git(repo_root, ["status", "--porcelain", "--untracked-files=all"])
    status_items = parse_name_status(raw_status)
    if not status_items:
        return "working tree clean"

    raw_diff = run_git(repo_root, ["diff", "--", ".", ":(exclude)VERSION.md"])
    raw_diff_cached = run_git(repo_root, ["diff", "--cached", "--", ".", ":(exclude)VERSION.md"])
    combined_diff = f"{raw_diff}\n{raw_diff_cached}"[:20000]

    scope_text = summarize_changed_files(status_items)
    scope_human = scope_to_human(scope_text)
    diff_keywords = keyword_counts_from_diff(combined_diff)
    path_keywords = keyword_counts_from_paths(status_items)
    action = infer_change_action(status_items, diff_keywords + path_keywords)
    token_set = set(diff_keywords.keys()) | set(path_keywords.keys()) | set(scope_human.lower().split())
    feature = infer_feature_phrase(token_set, scope_human)
    return build_summary_phrase(action, feature)


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
