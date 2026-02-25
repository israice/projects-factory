
#!/usr/bin/env python3
import subprocess
import sys
import os
from dotenv import load_dotenv
from flask import Flask, send_from_directory

load_dotenv()

PORT = int(os.getenv('PORT'))
STATIC_FOLDER = os.getenv('STATIC_FOLDER')

static_path = os.path.abspath(STATIC_FOLDER)
app = Flask(__name__, static_folder=None)

@app.route('/')
def index():
    return send_from_directory(static_path, 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory(static_path, filename)

for script in ("core/BACKEND/A_run.py", "core/BACKEND/B_run.py"):
    code = subprocess.call([sys.executable, script])
    if code != 0:
        sys.exit(code)

if __name__ == '__main__':
    app.run(port=PORT)
