pip install -r requirements.txt

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
git commit -m "v0.0.18 - fixed HOT PAGE RELOAD"
git push
python run.py

# DEV LOG
v0.0.24 - updated action buttons; updated backend logic; added Push button in project row panel
v0.0.25 - fixed auto version message generation
v0.0.26 - added API request handling
v0.0.27 - added configuration loading
v0.0.28 - fixed HOT PAGE RELOAD
v0.0.29 - added TASKS.md
v0.0.30 - added more tasks
v0.0.31 - and more tasks
v0.0.32 - improved API request handling
