# 🚀 Деплой AI News Bot на сервер

## Вариант 1: Render.com (БЕСПЛАТНО)

### Шаг 1: Подготовка
1. Создайте аккаунт на [render.com](https://render.com)
2. Подключите свой GitHub аккаунт

### Шаг 2: Загрузка кода на GitHub
1. Создайте новый репозиторий на GitHub
2. Загрузите все файлы проекта:
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/ваш-username/ai-news-bot.git
   git push -u origin main
   ```

### Шаг 3: Деплой на Render
1. Зайдите в [Render Dashboard](https://dashboard.render.com/)
2. Нажмите "New" → "Web Service"
3. Подключите ваш GitHub репозиторий
4. Настройте:
   - **Name:** ai-news-bot
   - **Environment:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python telegram-ai-news-bot.py`

### Шаг 4: Настройка переменных окружения
В разделе "Environment" добавьте:
- `TELEGRAM_BOT_TOKEN` = ваш_токен
- `TELEGRAM_CHANNEL_ID` = ваш_ID_канала  
- `OPENROUTER_API_KEY` = ваш_ключ
- `DATABASE_PATH` = /opt/render/project/data/ai_news.db

### Шаг 5: Деплой
Нажмите "Create Web Service" - бот автоматически развернется!

---

## Вариант 2: DigitalOcean VPS ($4/месяц)

### Шаг 1: Создание сервера
1. Создайте Droplet на [DigitalOcean](https://digitalocean.com)
2. Выберите Ubuntu 22.04, базовый план $4/месяц

### Шаг 2: Подключение к серверу
```bash
ssh root@ваш_ip_адрес
```

### Шаг 3: Установка зависимостей
```bash
apt update
apt install python3 python3-pip git -y
```

### Шаг 4: Клонирование и запуск
```bash
git clone https://github.com/ваш-username/ai-news-bot.git
cd ai-news-bot
pip3 install -r requirements.txt

# Создание .env файла
nano .env
# Добавьте ваши переменные окружения

# Запуск в screen
apt install screen -y
screen -S bot
python3 telegram-ai-news-bot.py
# Ctrl+A, D для выхода из screen
```

---

## Вариант 3: Railway.app

1. Зайдите на [railway.app](https://railway.app)
2. Подключите GitHub репозиторий
3. Добавьте переменные окружения
4. Деплой произойдет автоматически

---

## ⚠️ Важные моменты

1. **Файл .env НЕ загружайте на GitHub** - добавьте его в .gitignore
2. **Переменные окружения** настраивайте в панели управления платформы
3. **Бесплатные тарифы** могут засыпать, но это нормально для новостного бота
4. **Логи** смотрите в панели управления платформы

---

## 🔧 Мониторинг

Бот будет доступен по адресу, который даст платформа.
Посещение этого адреса покажет "AI News Bot is running!"

## Переменные окружения на Render

В разделе **Environment Variables** добавьте:

```
TELEGRAM_BOT_TOKEN=ваш_токен_бота
TELEGRAM_CHANNEL_ID=ваш_id_канала
OPENROUTER_API_KEY=ваш_ключ_openrouter
DATABASE_PATH=/opt/render/project/data/ai_news.db
AI_MODEL=meta-llama/llama-3.1-8b-instruct:free
MAX_MONTHLY_COST=5.0
MAX_NEWS_PER_CYCLE=10
ADMIN_TELEGRAM_ID=ваш_telegram_id
```

### 🤖 **Выбор AI модели:**

**Бесплатные модели (рекомендуется для начала):**
- `meta-llama/llama-3.1-8b-instruct:free` - базовое качество, $0
- `microsoft/wizardlm-2-8x22b:free` - хорошее качество, $0

**Платные модели (лучшее качество):**
- `openai/gpt-3.5-turbo` - хорошее качество, ~$0.50/1M токенов
- `anthropic/claude-3.5-sonnet` - отличное качество, ~$3/1M токенов

### 💰 **Контроль расходов:**
- `MAX_MONTHLY_COST=5.0` - максимальный бюджет в месяц ($5)
- Бот автоматически переключается на бесплатную модель при превышении
- Админ получает уведомления о расходах

### 📊 **Мониторинг:**
- Статистика отправляется админу ежедневно в 12:00
- Алерты при ошибках и аномалиях
- Отчеты о расходах и производительности

**⚠️ ВАЖНО для предотвращения дубликатов:**
- `DATABASE_PATH=/opt/render/project/data/ai_news.db` - обеспечивает постоянное хранение базы данных между деплоями
- Без этой переменной база данных будет сбрасываться при каждом обновлении кода 

## 🎯 **Новые возможности v2.0:**

✅ **Контроль расходов** - защита от превышения бюджета  
✅ **Умный выбор модели** - автоматическое переключение на бесплатные  
✅ **Retry механизмы** - автоматические повторы при ошибках  
✅ **Thread-safe БД** - безопасная работа с базой данных  
✅ **Админские алерты** - уведомления о проблемах  
✅ **Статистика и мониторинг** - детальная аналитика  
✅ **Rate limiting** - защита от блокировок API  

## 📱 **Получение ADMIN_TELEGRAM_ID:**

1. Найдите бота @userinfobot в Telegram
2. Отправьте ему любое сообщение
3. Скопируйте ваш числовой ID
4. Добавьте его в переменную `ADMIN_TELEGRAM_ID` 