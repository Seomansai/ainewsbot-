# 🚀 Развертывание AI News Bot на платных серверах

## Вариант 1: Railway.app (Рекомендуемый)

### Преимущества Railway:
- ✅ Автоматический деплой из GitHub
- ✅ Простая настройка переменных окружения  
- ✅ Автоматическое масштабирование
- ✅ Встроенный мониторинг
- ✅ Работает 24/7 без сна
- ✅ Поддержка SQLite из коробки

### Пошаговая инструкция:

#### 1. Подготовка кода
```bash
# Убедимся что все файлы готовы
git add .
git commit -m "Подготовка к деплою на Railway"
git push origin main
```

#### 2. Создание аккаунта на Railway
1. Идите на https://railway.app
2. Войдите через GitHub
3. Подключите ваш репозиторий `ainewsbot-`

#### 3. Настройка переменных окружения
В Railway Dashboard добавьте переменные:
```
TELEGRAM_BOT_TOKEN=ваш_токен_бота
TELEGRAM_CHANNEL_ID=-1002299454094
OPENROUTER_API_KEY=ваш_ключ_openrouter
AI_MODEL=anthropic/claude-3.5-sonnet
MAX_MONTHLY_COST=5.0
ADMIN_TELEGRAM_ID=ваш_telegram_id
MAX_NEWS_PER_CYCLE=10
DATABASE_PATH=/app/data/ai_news.db
```

#### 4. Обновление Procfile для Railway
```
web: python telegram-ai-news-bot.py
```

#### 5. Создание requirements.txt (если нет)
```
aiohttp==3.8.5
feedparser==6.0.10
python-telegram-bot==20.5
openai==1.3.0
python-dotenv==1.0.0
deep-translator==1.11.4
```

### Ожидаемая стоимость Railway:
- **Starter Plan**: $5/месяц
- **Включает**: 500 часов работы + $5 кредитов
- **Для вашего бота**: ~$5-8/месяц

---

## Вариант 2: DigitalOcean Droplet

### Преимущества DigitalOcean:
- ✅ Фиксированная цена $4-6/месяц
- ✅ Полный контроль над сервером
- ✅ Отличная документация
- ✅ SSD диски
- ✅ Множество дата-центров

### Пошаговая инструкция:

#### 1. Создание Droplet
1. Регистрация на https://digitalocean.com
2. Создайте новый Droplet:
   - **OS**: Ubuntu 22.04 LTS
   - **Plan**: Basic $4/month (1GB RAM)
   - **Region**: Ближайший к вам

#### 2. Настройка сервера
```bash
# Подключение к серверу
ssh root@your_server_ip

# Обновление системы
apt update && apt upgrade -y

# Установка Python и pip
apt install python3 python3-pip git -y

# Установка зависимостей для SQLite
apt install sqlite3 -y

# Создание пользователя для бота
adduser botuser
usermod -aG sudo botuser
su - botuser
```

#### 3. Установка бота
```bash
# Клонирование репозитория
git clone https://github.com/Seomansai/ainewsbot-.git
cd ainewsbot-

# Установка зависимостей
pip3 install -r requirements.txt

# Создание .env файла
nano .env
```

#### 4. Настройка systemd для автозапуска
```bash
sudo nano /etc/systemd/system/aibot.service
```

Содержимое файла:
```ini
[Unit]
Description=AI News Bot
After=network.target

[Service]
Type=simple
User=botuser
WorkingDirectory=/home/botuser/ainewsbot-
ExecStart=/usr/bin/python3 telegram-ai-news-bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### 5. Запуск и автозапуск
```bash
sudo systemctl daemon-reload
sudo systemctl enable aibot.service
sudo systemctl start aibot.service

# Проверка статуса
sudo systemctl status aibot.service
```

### Ожидаемая стоимость DigitalOcean:
- **Basic Droplet**: $4/месяц (1GB RAM)
- **Premium Droplet**: $6/месяц (2GB RAM) - рекомендуется

---

## Вариант 3: Hetzner Cloud (Самый дешевый)

### Преимущества Hetzner:
- ✅ Очень низкие цены (€3.29/месяц)
- ✅ Высокое качество серверов
- ✅ Европейский провайдер
- ✅ NVMe SSD диски

### Инструкция аналогична DigitalOcean:
1. Регистрация на https://console.hetzner.cloud
2. Создание CX11 сервера (€3.29/месяц)
3. Установка Ubuntu 22.04
4. Аналогичные шаги настройки

---

## Вариант 4: Vultr

### Преимущества Vultr:
- ✅ Много локаций по всему миру
- ✅ Высокая производительность
- ✅ Простой интерфейс

### Настройка аналогична DigitalOcean:
- **Regular Performance**: $5/месяц
- **High Performance**: $6/месяц (NVMe SSD)

---

## 🎯 Рекомендации по выбору:

### Для новичков: **Railway.app**
- Простейшая настройка
- Автоматический деплой
- Встроенный мониторинг
- ~$5-8/месяц

### Для опытных: **DigitalOcean**
- Полный контроль
- Фиксированная цена $4-6/месяц
- Отличная документация

### Для экономных: **Hetzner Cloud**
- Лучшая цена €3.29/месяц
- Высокое качество
- Европейские дата-центры

---

## 📊 Сравнение стоимости в месяц:

| Провайдер | Цена | Преимущества | Сложность |
|-----------|------|--------------|-----------|
| Railway | $5-8 | Автодеплой | ⭐ Очень легко |
| Hetzner | €3.29 | Дешево | ⭐⭐ Средне |
| DigitalOcean | $4-6 | Надежность | ⭐⭐ Средне |
| Vultr | $5-6 | Производительность | ⭐⭐ Средне |

---

## 🛠️ Что делать после выбора:

1. **Перенос данных**: Экспорт базы данных с текущего сервера
2. **Настройка мониторинга**: Уведомления об ошибках
3. **Бэкапы**: Автоматическое резервное копирование
4. **Оптимизация**: Настройка логирования и метрик

Какой вариант вас больше интересует? Могу помочь с детальной настройкой любого из них! 