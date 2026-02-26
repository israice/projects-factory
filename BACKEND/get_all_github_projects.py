#!/usr/bin/env python3
"""
Fetch all GitHub repositories (public and private) available to the authenticated user
and save a compact list to YAML.

Preserves the original observable behavior:
- Loads GITHUB_USERNAME and GITHUB_TOKEN from .env (via python-dotenv).
- Fetches repos via GitHub REST API /user/repos with affiliation=owner, per_page=100, paging.
- Writes YAML to BACKEND/get_all_github_projects.yaml
- Prints: "Fetched N repositories for user 'username'"

Improvements:
- Uses a requests.Session with retries and timeouts.
- Handles GitHub rate-limit / transient failures more gracefully.
- Ensures output directory exists.
- Uses modern Authorization header format ("Bearer") while keeping compatibility.
- Keeps YAML stable and readable, avoids dumping arbitrary fields.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import requests
import yaml
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


GITHUB_API_BASE = "https://api.github.com"
OUTPUT_PATH = Path("BACKEND/get_all_github_projects.yaml")


def load_credentials() -> tuple[str, str]:
    load_dotenv()
    username = os.getenv("GITHUB_USERNAME")
    token = os.getenv("GITHUB_TOKEN")

    if not username or not token:
        raise ValueError("GITHUB_USERNAME and GITHUB_TOKEN must be set in .env file")

    return username, token


def build_session(token: str) -> requests.Session:
    session = requests.Session()

    # GitHub recommends a User-Agent; some proxies/services behave better with it.
    session.headers.update(
        {
            # "token <PAT>" also works, but Bearer is the modern form.
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "get-all-github-projects/1.0",
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
    """
    Returns raw repo objects from GitHub REST API.

    Note: The API endpoint /user/repos returns repositories for the authenticated user;
    the username is only used for logging parity with the original script.
    """
    session = build_session(token)

    url = f"{GITHUB_API_BASE}/user/repos"
    params = {
        "affiliation": "owner",
        "per_page": 100,
        "page": 1,
    }

    all_repos: list[dict[str, Any]] = []
    timeout = (5, 30)  # (connect, read)

    while True:
        resp = session.get(url, params=params, timeout=timeout)

        # If retries exhausted and still error, provide a clearer message.
        if resp.status_code >= 400:
            # Try to extract GitHub-style error payload.
            try:
                payload = resp.json()
            except Exception:
                payload = None

            # Extra hint for rate limits.
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


def save_to_yaml(repos: list[dict[str, Any]], output_path: Path) -> None:
    data = {
        "repositories": [
            {
                "name": repo.get("name", ""),
                "url": repo.get("html_url", ""),
                "private": bool(repo.get("private", False)),
                "description": repo.get("description") or "",
                "created_at": repo.get("created_at") or "",
            }
            for repo in repos
        ]
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        # default_flow_style=False gives the same “pretty” block YAML intent.
        yaml.safe_dump(
            data,
            f,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
        )


def main() -> None:
    username, token = load_credentials()
    repos = fetch_all_repos(username, token)
    save_to_yaml(repos, OUTPUT_PATH)
    print(f"Fetched {len(repos)} repositories for user '{username}'")


if __name__ == "__main__":
    main()