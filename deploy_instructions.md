# 🚀 Полное руководство по развертыванию AI News Bot 24/7

## 🏆 **РЕКОМЕНДУЕМЫЕ ВАРИАНТЫ 2024**

### 1. 🆓 **Render.com - БЕСПЛАТНО** (Рекомендуется)

**Особенности:**
- ✅ 750 часов/месяц (достаточно для 24/7)
- ✅ Автоматический деплой через GitHub
- ✅ SSL сертификаты
- ⚠️ "Засыпает" через 15 мин бездействия (но пробуждается за 30 сек)

#### Быстрый деплой на Render:

1. **Загрузите код на GitHub** (если ещё не сделали)
2. **Зайдите на render.com** → "Create Web Service"
3. **Подключите ваш репозиторий**
4. **Настройки:**
   ```
   Name: ai-news-bot
   Environment: Python 3
   Build Command: pip install -r requirements.txt
   Start Command: python telegram-ai-news-bot.py
   ```

5. **Переменные окружения:**
   ```
   TELEGRAM_BOT_TOKEN=ваш_токен_бота
   TELEGRAM_CHANNEL_ID=ваш_id_канала
   OPENROUTER_API_KEY=ваш_ключ_api
   AI_MODEL=meta-llama/llama-3.1-8b-instruct:free
   MAX_MONTHLY_COST=5.0
   ADMIN_TELEGRAM_ID=ваш_telegram_id
   DATABASE_PATH=/opt/render/project/src/ai_news.db
   ```

### 2. 💰 **Railway.app - $5/месяц** (Отличное соотношение цена/качество)

**Особенности:**
- ✅ НЕ засыпает
- ✅ Простой деплой
- ✅ Автоматическое масштабирование
- ✅ $5 кредита бесплатно каждый месяц

#### Деплой на Railway:

1. **Зайдите на railway.app**
2. **"Deploy from GitHub"**
3. **Выберите ваш репозиторий**
4. **Добавьте переменные окружения**
5. **Деплой автоматический!**

### 3. 🔧 **DigitalOcean VPS - $4/месяц** (Максимальный контроль)

**Особенности:**
- ✅ Полный контроль над сервером
- ✅ Никогда не засыпает
- ✅ Можно запускать несколько ботов
- ⚠️ Требует базовых знаний Linux

#### Настройка VPS:

```bash
# 1. Подключение к серверу
ssh root@your_server_ip

# 2. Установка зависимостей
apt update && apt upgrade -y
apt install python3 python3-pip git screen htop -y

# 3. Клонирование проекта
git clone https://github.com/ваш-username/ainewsbot-.git
cd ainewsbot-

# 4. Установка зависимостей Python
pip3 install -r requirements.txt

# 5. Создание .env файла
nano .env
```

**.env файл для VPS:**
```env
TELEGRAM_BOT_TOKEN=ваш_токен
TELEGRAM_CHANNEL_ID=ваш_канал
OPENROUTER_API_KEY=ваш_ключ
AI_MODEL=meta-llama/llama-3.1-8b-instruct:free
MAX_MONTHLY_COST=5.0
ADMIN_TELEGRAM_ID=ваш_id
DATABASE_PATH=./ai_news.db
```

```bash
# 6. Запуск в фоновом режиме
screen -S aibot
python3 telegram-ai-news-bot.py

# Ctrl+A, затем D для выхода
# Для возврата: screen -r aibot
```

### 4. 🚀 **Fly.io - от $0** (Современный вариант)

**Особенности:**
- ✅ Щедрый бесплатный тариф
- ✅ Современная архитектура
- ✅ Глобальное распределение

```bash
# Установка flyctl
curl -L https://fly.io/install.sh | sh

# Деплой
fly deploy
```

---

## 🔥 **БЫСТРОЕ РЕШЕНИЕ ДЛЯ НЕМЕДЛЕННОГО ЗАПУСКА**

Если нужно запустить **ПРЯМО СЕЙЧАС**, рекомендую **Render.com**:

### Шаги за 5 минут:

1. **Загрузите на GitHub** (если не сделали)
2. **render.com** → "New Web Service"  
3. **Подключите репозиторий**
4. **Добавьте переменные окружения**
5. **Deploy!**

### ⚡ Обход "засыпания" Render (бесплатный тариф):

Добавьте этот код в ваш `telegram-ai-news-bot.py`:

```python
# ДОБАВИТЬ В КОНЕЦ ФАЙЛА
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler

def keep_alive():
    """Простой HTTP сервер для поддержания активности"""
    class Handler(SimpleHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b'AI News Bot is running! 🤖')
    
    server = HTTPServer(('0.0.0.0', int(os.environ.get('PORT', 8080))), Handler)
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()

# В функции main() добавить:
keep_alive()
```

---

## 📊 **СРАВНЕНИЕ ПЛАТФОРМ**

| Платформа | Цена | Засыпает? | Сложность | Рекомендация |
|-----------|------|-----------|-----------|---------------|
| **Render.com** | Бесплатно | Да (15 мин) | ⭐ | 🥇 **Для начала** |
| **Railway.app** | $5/мес | Нет | ⭐ | 🥈 **Лучший баланс** |
| **DigitalOcean** | $4/мес | Нет | ⭐⭐⭐ | 🥉 **Максимальный контроль** |
| **Fly.io** | $0-$5/мес | Нет | ⭐⭐ | 🏅 **Современный** |

---

## 🛡️ **БЕЗОПАСНОСТЬ И МОНИТОРИНГ**

### Обязательные настройки:

1. **Никогда не загружайте .env на GitHub!**
2. **Используйте переменные окружения платформы**
3. **Настройте ADMIN_TELEGRAM_ID для алертов**

### Получение Telegram ID:
1. Найдите бота `@userinfobot`
2. Отправьте `/start`
3. Скопируйте ваш ID число

---

## 🔄 **АВТОМАТИЧЕСКИЕ ОБНОВЛЕНИЯ**

Все платформы поддерживают автоматический деплой при push в GitHub:

1. **Изменили код** → git push
2. **Платформа автоматически деплоит**
3. **Бот обновляется без простоя**

---

## 🆘 **TROUBLESHOOTING**

### Частые проблемы:

**❌ "Database locked"**
```python
# В .env добавить:
DATABASE_PATH=/opt/render/project/src/ai_news.db  # Render
DATABASE_PATH=./ai_news.db  # VPS
```

**❌ "Module not found"**
```bash
# Проверить requirements.txt:
pip freeze > requirements.txt
```

**❌ "Bot не отвечает"**
- Проверьте логи в панели платформы
- Убедитесь, что все переменные окружения установлены
- Проверьте TELEGRAM_BOT_TOKEN

---

## 📈 **МОНИТОРИНГ ПОСЛЕ ЗАПУСКА**

После деплоя бот будет:
- ✅ Отправлять админу уведомления о запуске
- ✅ Присылать ежедневную статистику в 12:00
- ✅ Сигнализировать о проблемах
- ✅ Автоматически переключаться на бесплатные модели при превышении бюджета

**Ваш бот готов к работе 24/7! 🚀** 