
# RECOVERY
git log --oneline -n 5

Copy-Item .env $env:TEMP\.env.backup
git reset --hard 80f714fc
git clean -fd
Copy-Item $env:TEMP\.env.backup .env -Force
git push origin master --force
python run.py

# UPDATE
git add .
git commit -m "v0.0.8 - added create new project button"
git push
python run.py

# DEV LOG
v0.0.1 - working dashboard with projects instalattion 25.02.2026
v0.0.2 - added bottom panel
v0.0.3 - added local folder delete
v0.0.4 - added avatar
v0.0.5 - added Projects Logos
v0.0.6 - added url to links
v0.0.7 - added dark theme
v0.0.8 - added create new project button
