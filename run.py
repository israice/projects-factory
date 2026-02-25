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
    token = os.getenv("GITHUB_TOKEN", "")
    message = request.args.get("message", "")
    # Fetch user avatar from GitHub API
    avatar_url = ""
    try:
        import requests
        headers = {"Authorization": f"token {token}"} if token else {}
        resp = requests.get(f"https://api.github.com/users/{username}", headers=headers, timeout=5)
        if resp.status_code == 200:
            avatar_url = resp.json().get("avatar_url", "")
    except Exception:
        pass
    with open("TOOLS/get_all_github_projects.yaml", "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    repos = sorted(data.get("repositories", []), key=lambda r: (r["name"] != username, r["name"].lower()))
    my_repos_dir = os.path.join(os.path.dirname(__file__), "MY_REPOS")
    installed_urls = get_installed_repo_urls(my_repos_dir)
    return render_template("index.html", repos=repos, username=username, count=len(repos), installed_count=len(installed_urls), installed_repos=installed_urls, avatar_url=avatar_url, message=message)

@app.route("/refresh")
def refresh():
    subprocess.run(["python", "TOOLS/get_all_github_projects.py"], check=True)
    return redirect(url_for("index"))

@app.route("/create-new")
def create_new():
    result = subprocess.run(["python", "MY_REPOS/Create-Project-Folder/create_new_project.py"],
                           capture_output=True, text=True, check=True)
    # Extract project name from output
    output = result.stdout.strip()
    # Parse "Project "folder_name" created successfully" to get folder_name
    folder_name = ""
    if 'Project "' in output and '" created' in output:
        start = output.find('Project "') + len('Project "')
        end = output.find('" created')
        folder_name = output[start:end]
    message = f'Project "{folder_name}" created successfully' if folder_name else "Project created successfully"
    return redirect(url_for("index", message=message))

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

@app.route("/delete", methods=["POST"])
def delete():
    data = request.get_json()
    repo_names = data.get("repos", [])
    if not repo_names:
        return jsonify({"error": "No repositories selected"}), 400
    try:
        timeout = 60 * len(repo_names)
        result = subprocess.run(["python", "TOOLS/delete_local_folder.py"] + repo_names, capture_output=True, text=True, check=False, timeout=timeout, encoding="utf-8")
        my_repos_dir = os.path.join(os.path.dirname(__file__), "MY_REPOS")
        installed_count = len([d for d in os.listdir(my_repos_dir) if os.path.isdir(os.path.join(my_repos_dir, d))]) if os.path.exists(my_repos_dir) else 0
        return jsonify({"success": True, "output": result.stdout, "error": result.stderr if result.returncode != 0 else None, "installed_count": installed_count})
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Deletion timed out."}), 504
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(port=5000, use_reloader=False)
