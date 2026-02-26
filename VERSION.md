
Если хотите убедиться что всё работает:

# 1. Запустите сервер
python run.py

# 2. В другом терминале проверьте порты
netstat -ano | findstr 5999
netstat -ano | findstr 35729
# (должны показать LISTENING)
 
# 3. Вернитесь в первый терминал, нажмите Ctrl+C
 
# 4. Снова проверьте
netstat -ano | findstr 5999
netstat -ano | findstr 35729
    
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
git commit -m "v0.0.16 - added confirm module"
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
v0.0.9 - added delete yellow project button
v0.0.10 - added rename local project button
v0.0.11 - added avatar based menu
v0.0.12 - code to fast api
v0.0.13 - added search
v0.0.14 - added Next button
v0.0.15 - added Delete project from github
v0.0.16 - added confirm module