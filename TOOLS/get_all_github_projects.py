"""Fetch all GitHub repositories (public and private) for a user and save to YAML."""
import os, warnings
warnings.filterwarnings("ignore")
import requests, yaml
from dotenv import load_dotenv

def load_credentials() -> tuple[str, str]:
    load_dotenv()
    username, token = os.getenv("GITHUB_USERNAME"), os.getenv("GITHUB_TOKEN")
    if not username or not token:
        raise ValueError("GITHUB_USERNAME and GITHUB_TOKEN must be set in .env file")
    return username, token

def fetch_all_repos(username: str, token: str) -> list[dict]:
    url = "https://api.github.com/user/repos"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    params = {"affiliation": "owner", "per_page": 100, "page": 1}
    all_repos = []
    while True:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        repos = response.json()
        if not repos: break
        all_repos.extend(repos)
        params["page"] += 1
    return all_repos

def save_to_yaml(repos: list[dict], output_path: str) -> None:
    data = {"repositories": [{"name": repo["name"], "url": repo["html_url"], "private": repo["private"], "description": repo.get("description", ""), "created_at": repo.get("created_at", "")} for repo in repos]}
    with open(output_path, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False, default_flow_style=False)

def main():
    username, token = load_credentials()
    repos = fetch_all_repos(username, token)
    save_to_yaml(repos, "TOOLS/get_all_github_projects.yaml")
    print(f"Fetched {len(repos)} repositories for user '{username}'")

if __name__ == "__main__":
    main()
