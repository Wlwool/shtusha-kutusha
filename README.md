# Shtusha-Kutusha Bot 🤖

[![Docker](https://img.shields.io/badge/Docker-Enabled-blue.svg)](https://www.docker.com/)
[![Python](https://img.shields.io/badge/Python-3.11%2B-green.svg)](https://www.python.org/)
[![Discord.py](https://img.shields.io/badge/discord.py-2.0%2B-blue.svg)](https://discordpy.readthedocs.io/)

Shtusha-Kutusha — это удобный бот для установки напоминаний. Он позволяет устанавливать напоминания на определённое время или через промежуток времени.

---

## 🚀 Основные функции

- Установка напоминаний на определённое время или через промежуток времени.
- Динамический статус бота с информацией о серверах, пользователях и пинге.
- Поддержка Docker для простого развёртывания.

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

### 3. Настройка переменных окружения
```bash
docker-compose up -d --build
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
