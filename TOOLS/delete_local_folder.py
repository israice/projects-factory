"""Delete a local repository folder from MY_REPOS directory."""
import os, sys, subprocess, io, shutil
from pathlib import Path
from typing import Optional

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

def delete_repository(repo_name: str, my_repos_dir: Path) -> tuple[str, str, str]:
    """Delete a repository folder from MY_REPOS directory.
    
    Args:
        repo_name: Name of the repository folder to delete
        my_repos_dir: Path to the MY_REPOS directory
        
    Returns:
        Tuple of (repo_name, status, message)
    """
    target_path = my_repos_dir / repo_name
    
    if not target_path.exists():
        return repo_name, "not_found", f"Directory '{target_path}' does not exist."
    
    if not target_path.is_dir():
        return repo_name, "error", f"'{target_path}' is not a directory."
    
    print(f"🗑️  Deleting {target_path}...")
    try:
        # On Windows, use del /q /s for locked files, then rmdir
        if sys.platform == "win32":
            # First try to remove read-only attributes
            subprocess.run(["attrib", "-R", "-S", "-H", "/S", "/D", str(target_path)], 
                          shell=True, capture_output=True, timeout=30)
            # Use del /q /s for files and rmdir for directories
            subprocess.run(["cmd", "/c", "rmdir", "/S", "/Q", str(target_path)], 
                          check=True, capture_output=True, timeout=30)
        else:
            shutil.rmtree(target_path)
        
        if target_path.exists():
            return repo_name, "error", f"Failed to delete '{repo_name}'"
        
        print(f"✅ Repository deleted successfully!")
        return repo_name, "success", f"Deleted '{repo_name}'"
    except subprocess.TimeoutExpired:
        return repo_name, "error", "Deletion timed out"
    except Exception as e:
        print(f"❌ Error during deletion: {e}")
        return repo_name, "error", str(e)

def main(repo_names: Optional[list[str]] = None) -> list[dict]:
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    my_repos_dir = project_root / "MY_REPOS"
    
    if repo_names is None:
        print("❌ No repository names provided.")
        return []
    
    results = []
    for repo_name in repo_names:
        print("-" * 60)
        name, status, message = delete_repository(repo_name, my_repos_dir)
        results.append({"name": name, "status": status, "message": message})
        
        if status == "success":
            print(f"✅ Deletion complete for '{name}'!")
        elif status == "not_found":
            print(f"⚠️  Repository '{name}' not found. Nothing to delete.")
        else:
            print(f"❌ {message}")
    
    return results

if __name__ == "__main__":
    repo_names = sys.argv[1:] if len(sys.argv) > 1 else None
    results = main(repo_names)
    if "--json" in sys.argv:
        import json
        print(json.dumps(results))
    else:
        print("\n" + "=" * 60)
        print("DELETION SUMMARY")
        print("=" * 60)
        for result in results:
            if result["status"] == "success":
                status_icon, status_text = "✅", "deleted"
            elif result["status"] == "not_found":
                status_icon, status_text = "⚠️", "not found"
            else:
                status_icon, status_text = "❌", "error"
            print(f"{status_icon} {result['name']}: {status_text}")
            if "message" in result and result["status"] != "success":
                print(f"   {result['message']}")
