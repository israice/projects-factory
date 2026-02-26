# GitHub Projects Fetcher

Скрипт для получения списка всех репозиториев пользователя GitHub (публичных и приватных) + веб-интерфейс для просмотра.

## Установка зависимостей

```bash
pip install -r requirements.txt
```

## Настройка

1. Создайте файл `.env` в корне проекта (уже существует шаблон)

2. Заполните данные в `.env`:
   ```
   GITHUB_USERNAME=ваш-username
   GITHUB_TOKEN=ваш-personal-access-token
   ```

## Получение GitHub токена

1. Перейдите на https://github.com/settings/tokens
2. Нажмите **Generate new token (classic)**
3. Укажите название токена
4. Выберите_scope_ **`repo`** (для доступа к приватным репозиториям)
5. Нажмите **Generate token**
6. Скопируйте токен и сохраните его в `.env`

## Использование

### 1. Получение списка репозиториев

```bash
python BACKEND/get_all_github_projects.py
```

Результат сохраняется в `BACKEND/get_all_github_projects.yaml`.

### 2. Веб-интерфейс

Запуск сервера:

```bash
python run.py
```

Откройте в браузере: **http://127.0.0.1:5000**

**Функции:**
- Просмотр всех репозиториев в виде таблицы
- Кнопка **Refresh** для обновления данных
- Авто-обновление страницы при изменении кода (live-reload)

## Структура проекта

```
├── BACKEND/
│   ├── get_all_github_projects.py  # Скрипт fetch репозиториев
│   ├── get_all_github_projects.yaml # Результат
│   ├── install_existing_repo.py    # Установка репозиториев
│   ├── delete_local_folder.py      # Удаление локальных папок
│   └── rename_github_repo.py       # Переименование репозиториев
├── FRONTEND/
│   └── index.html                   # Шаблон веб-интерфейса
├── run.py                           # Flask приложение
├── requirements.txt                 # Зависимости
└── .env                             # Конфигурация
```
