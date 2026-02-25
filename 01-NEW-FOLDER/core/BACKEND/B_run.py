
#!/usr/bin/env python3
import subprocess, sys

for script in (
    "core/BACKEND/test.py",
    ):
    if subprocess.call([sys.executable, script]) != 0:
        sys.exit(1)
