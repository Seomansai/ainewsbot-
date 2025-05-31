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