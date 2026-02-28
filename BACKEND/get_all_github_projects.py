#!/usr/bin/env python3
"""Fetch all GitHub repositories (public and private) for the authenticated user."""

from __future__ import annotations

import os
from typing import Any

import requests
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

GITHUB_API_BASE = "https://api.github.com"


def load_credentials() -> tuple[str, str]:
    load_dotenv()
    username = os.getenv("GITHUB_USERNAME", "").strip()
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if not username or not token:
        raise ValueError("GITHUB_USERNAME and GITHUB_TOKEN must be set in .env file")
    return username, token


def build_session(token: str) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "projects-factory/github-repos",
        }
    )
    retry = Retry(
        total=5,
        connect=5,
        read=5,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def fetch_all_repos(username: str, token: str) -> list[dict[str, Any]]:
    session = build_session(token)
    url = f"{GITHUB_API_BASE}/user/repos"
    params = {"affiliation": "owner", "per_page": 100, "page": 1}
    timeout = (5, 30)
    all_repos: list[dict[str, Any]] = []

    while True:
        resp = session.get(url, params=params, timeout=timeout)
        if resp.status_code >= 400:
            try:
                payload = resp.json()
            except Exception:
                payload = None

            if resp.status_code == 403 and resp.headers.get("X-RateLimit-Remaining") == "0":
                reset = resp.headers.get("X-RateLimit-Reset")
                raise RuntimeError(f"GitHub rate limit exceeded. X-RateLimit-Reset={reset}")

            msg = payload.get("message") if isinstance(payload, dict) else resp.text
            raise RuntimeError(f"GitHub API error {resp.status_code}: {msg}")

        repos = resp.json()
        if not isinstance(repos, list):
            raise RuntimeError(f"Unexpected GitHub response shape: {type(repos)}")

        if not repos:
            break
        all_repos.extend(repos)
        params["page"] += 1

    return all_repos


def to_compact_repo(repo: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": repo.get("name", ""),
        "url": repo.get("html_url", ""),
        "private": bool(repo.get("private", False)),
        "description": repo.get("description") or "",
        "created_at": repo.get("created_at") or "",
    }


def fetch_compact_repos(username: str, token: str) -> list[dict[str, Any]]:
    repos = fetch_all_repos(username, token)
    return [to_compact_repo(repo) for repo in repos]


def main() -> None:
    username, token = load_credentials()
    repos = fetch_compact_repos(username, token)
    print(f"Fetched {len(repos)} repositories for user '{username}'")


if __name__ == "__main__":
    main()
