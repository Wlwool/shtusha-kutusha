# Shtusha-Kutusha Bot 🤖

[![Docker](https://img.shields.io/badge/Docker-Enabled-blue.svg)](https://www.docker.com/)
[![Python](https://img.shields.io/badge/Python-3.13-green.svg)](https://www.python.org/)
[![Discord.py](https://img.shields.io/badge/discord.py-2.7.1-blue.svg)](https://discordpy.readthedocs.io/)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)

Shtusha-Kutusha — это удобный бот для установки напоминаний. Он позволяет устанавливать напоминания на определённое время или через промежуток времени.

---

## 🚀 Основные функции

- Установка напоминаний на определённое время или через промежуток времени.
- Динамический статус бота с информацией о серверах, пользователях и пинге.

- Использование aiosqlite для асинхронной работы с SQLite
- APScheduler для управления задачами напоминаний
- Автоматическое восстановление напоминаний при перезапуске
- Логирование всех изменений
- Docker compose для перезапуска контейнера с ботом

---

## 🛠️ Установка и запуск

### 1. Клонируйте репозиторий

```bash
git clone https://github.com/Wlwool/shtusha-kutusha.git
cd shtusha-kutusha
```

### 2. Настройка переменных окружения
```
DISCORD_TOKEN=ваш_токен
ADMIN_ID=ваш_id
```

### 3. Запуск через Docker
```bash
docker-compose up -d --build
```

### Локальная разработка (через uv)

```bash
# Установка зависимостей
uv sync --dev

# Запуск бота
uv run python bot/main.py

# Запуск тестов
uv run pytest tests/ -v
```

-------------------------------

### Остановить бота и контейнер
```commandline
docker-compose down
```

### Остановка с удалением томов
```commandline
docker-compose down -v
```

--------------------------------

## 🐳 Управление контейнерами

### Просмотр логов

Чтобы просмотреть логи работы бота, выполните команду:

```bash
docker-compose logs -f bot
```
### Перезапуск контейнера
```bash
docker-compose restart bot
```
### Удаление контейнеров и томов
Чтобы полностью удалить контейнеры и тома (включая базу данных)
```bash
docker-compose down -v
```

--------------------------------

Сборка образа: 
```bash
docker-compose build
```
Запуск:

```bash
docker-compose up -d
```

## 🔄 Обновление бота

```bash
git pull
docker-compose down
docker-compose up -d --build
```

### Возможные добавления
- Добавить команды для управления напоминаниями(изменение, удаление)

