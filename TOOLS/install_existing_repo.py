"""Install an existing GitHub repository into MY_REPOS folder."""
import os, sys, subprocess, io
from pathlib import Path
from typing import Optional

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

def clone_repository(repo_url: str, target_path: Path) -> None:
    if target_path.exists():
        print(f"⚠️  Directory '{target_path}' already exists. Skipping...")
        return
    print(f"📥 Cloning {repo_url} into {target_path}...")
    subprocess.run(["git", "clone", repo_url, str(target_path)], check=True)
    print(f"✅ Repository cloned successfully!")

def install_repo(repo_url: str, my_repos_dir: Path) -> tuple[Path, str]:
    repo_name = repo_url.rstrip("/").rstrip(".git").split("/")[-1]
    target_path = my_repos_dir / repo_name
    if target_path.exists():
        return target_path, "skipped"
    clone_repository(repo_url, target_path)
    return target_path, "installed"

def main(repo_urls: Optional[list[str]] = None) -> list[dict]:
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    my_repos_dir = project_root / "MY_REPOS"
    my_repos_dir.mkdir(exist_ok=True)
    if repo_urls is None:
        repo_urls = ["https://github.com/israice/Create-Project-Folder.git"]
    results = []
    for repo_url in repo_urls:
        print("-" * 60)
        try:
            target_path, status = install_repo(repo_url, my_repos_dir)
            repo_name = target_path.name
            if status == "skipped":
                print(f"⚠️  Repository '{repo_name}' already exists. Skipping.")
                results.append({"name": repo_name, "url": repo_url, "path": str(target_path), "status": "skipped"})
            else:
                print(f"✅ Installation complete for '{repo_name}'!")
                print(f"📁 Repository location: {target_path}")
                results.append({"name": repo_name, "url": repo_url, "path": str(target_path), "status": "success"})
        except subprocess.CalledProcessError as e:
            print(f"❌ Error during installation: {e}")
            results.append({"name": repo_url, "url": repo_url, "path": "", "status": "error", "error": str(e)})
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            results.append({"name": repo_url, "url": repo_url, "path": "", "status": "error", "error": str(e)})
    return results

if __name__ == "__main__":
    repo_urls = sys.argv[1:] if len(sys.argv) > 1 else None
    results = main(repo_urls)
    if "--json" in sys.argv:
        import json
        print(json.dumps(results))
    else:
        print("\n" + "=" * 60)
        print("INSTALLATION SUMMARY")
        print("=" * 60)
        for result in results:
            if result["status"] == "success":
                status_icon, status_text = "✅", "installed"
            elif result["status"] == "skipped":
                status_icon, status_text = "⚠️", "skipped (already exists)"
            else:
                status_icon, status_text = "❌", "error"
            print(f"{status_icon} {result['name']}: {status_text}")
            if result["status"] in ["success", "skipped"]:
                print(f"   Location: {result['path']}")
            elif "error" in result:
                print(f"   Error: {result['error']}")
