import warnings, os
warnings.filterwarnings("ignore")
from flask import Flask, render_template, redirect, url_for, request, jsonify
import yaml, subprocess
from dotenv import load_dotenv
from flask_livereload import LiveReload

app = Flask(__name__, template_folder="FRONTEND", static_folder="FRONTEND")
app.debug = True
LiveReload(app)

@app.route('/favicon.ico')
def favicon(): return '', 204

def get_installed_repo_urls(my_repos_dir):
    """Get set of GitHub repo URLs from installed repositories by checking git remote."""
    installed_urls = set()
    if not os.path.exists(my_repos_dir):
        return installed_urls
    for folder in os.listdir(my_repos_dir):
        folder_path = os.path.join(my_repos_dir, folder)
        if not os.path.isdir(folder_path):
            continue
        git_dir = os.path.join(folder_path, ".git")
        if not os.path.exists(git_dir):
            continue
        try:
            result = subprocess.run(
                ["git", "-C", folder_path, "remote", "get-url", "origin"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                remote_url = result.stdout.strip()
                # Normalize URL: remove .git suffix (if present) and trailing slashes
                if remote_url.endswith(".git"):
                    remote_url = remote_url[:-4]
                normalized = remote_url.rstrip("/")
                installed_urls.add(normalized)
        except (subprocess.TimeoutExpired, Exception):
            pass
    return installed_urls

@app.route("/")
def index():
    load_dotenv()
    username = os.getenv("GITHUB_USERNAME", "Unknown")
    with open("TOOLS/get_all_github_projects.yaml", "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    repos = sorted(data.get("repositories", []), key=lambda r: (r["name"] != username, r["name"].lower()))
    my_repos_dir = os.path.join(os.path.dirname(__file__), "MY_REPOS")
    installed_urls = get_installed_repo_urls(my_repos_dir)
    return render_template("index.html", repos=repos, username=username, count=len(repos), installed_count=len(installed_urls), installed_repos=installed_urls)

@app.route("/refresh")
def refresh():
    subprocess.run(["python", "TOOLS/get_all_github_projects.py"], check=True)
    return redirect(url_for("index"))

@app.route("/install", methods=["POST"])
def install():
    data = request.get_json()
    repo_urls = data.get("repos", [])
    if not repo_urls:
        return jsonify({"error": "No repositories selected"}), 400
    try:
        timeout = 300 * len(repo_urls)
        result = subprocess.run(["python", "TOOLS/install_existing_repo.py"] + repo_urls, capture_output=True, text=True, check=False, timeout=timeout, encoding="utf-8")
        my_repos_dir = os.path.join(os.path.dirname(__file__), "MY_REPOS")
        installed_count = len([d for d in os.listdir(my_repos_dir) if os.path.isdir(os.path.join(my_repos_dir, d))]) if os.path.exists(my_repos_dir) else 0
        return jsonify({"success": True, "output": result.stdout, "error": result.stderr if result.returncode != 0 else None, "installed_count": installed_count})
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Installation timed out. Try installing fewer repositories at once."}), 504
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(port=5000, use_reloader=False)
