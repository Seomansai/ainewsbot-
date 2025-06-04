#!/usr/bin/env python3
# Скрипт быстрого деплоя AI News Bot

import os
import subprocess
import sys
import json

def print_banner():
    """Красивый баннер"""
    print("""
🚀 AI News Bot v2.0 - Быстрый деплой

   ╔══════════════════════════════════════╗
   ║     Автоматический деплой бота       ║
   ║       на облачные платформы          ║
   ╚══════════════════════════════════════╝
    """)

def check_requirements():
    """Проверка требований"""
    print("🔍 Проверка требований...")
    
    # Проверка git
    try:
        subprocess.run(['git', '--version'], capture_output=True, check=True)
        print("✅ Git установлен")
    except:
        print("❌ Git не найден. Установите Git для продолжения.")
        return False
    
    # Проверка Python
    if sys.version_info < (3, 8):
        print("❌ Требуется Python 3.8+")
        return False
    else:
        print(f"✅ Python {sys.version}")
    
    return True

def setup_git_repo():
    """Настройка Git репозитория"""
    print("\n📦 Настройка Git репозитория...")
    
    # Инициализация git если нужно
    if not os.path.exists('.git'):
        subprocess.run(['git', 'init'])
        print("✅ Git репозиторий инициализирован")
    
    # Проверка .gitignore
    gitignore_content = """
# Секретные файлы
.env
secrets.json
*.key

# Данные
*.db
*.sqlite
cost_data.json
bot_metrics.json

# Логи
*.log
logs/

# Python
__pycache__/
*.pyc
*.pyo
*.egg-info/
dist/
build/

# OS
.DS_Store
Thumbs.db

# IDE
.vscode/
.idea/
*.swp
*.swo
"""
    
    with open('.gitignore', 'w') as f:
        f.write(gitignore_content.strip())
    print("✅ .gitignore создан")
    
    # Добавление файлов
    subprocess.run(['git', 'add', '.'])
    
    try:
        subprocess.run(['git', 'commit', '-m', 'Initial commit for deployment'], check=True)
        print("✅ Коммит создан")
    except subprocess.CalledProcessError:
        print("ℹ️ Нет новых изменений для коммита")

def create_env_template():
    """Создание шаблона .env"""
    env_template = """
# ===== ОБЯЗАТЕЛЬНЫЕ НАСТРОЙКИ =====
TELEGRAM_BOT_TOKEN=ваш_токен_бота_от_BotFather
TELEGRAM_CHANNEL_ID=@ваш_канал_или_chat_id
OPENROUTER_API_KEY=ваш_ключ_openrouter

# ===== AI МОДЕЛЬ И БЮДЖЕТ =====
AI_MODEL=meta-llama/llama-3.1-8b-instruct:free
MAX_MONTHLY_COST=5.0

# ===== АДМИНИСТРИРОВАНИЕ =====
ADMIN_TELEGRAM_ID=ваш_telegram_id

# ===== БАЗА ДАННЫХ =====
DATABASE_PATH=./ai_news.db

# ===== ДОПОЛНИТЕЛЬНЫЕ =====
MAX_NEWS_PER_CYCLE=10
CHECK_INTERVAL_HOURS=2
""".strip()
    
    if not os.path.exists('.env'):
        with open('.env', 'w') as f:
            f.write(env_template)
        print("✅ Шаблон .env создан")
        print("📝 Отредактируйте файл .env с вашими настройками")
    else:
        print("ℹ️ Файл .env уже существует")

def check_env_file():
    """Проверка заполнения .env"""
    if not os.path.exists('.env'):
        print("❌ Файл .env не найден")
        return False
    
    with open('.env', 'r') as f:
        content = f.read()
    
    required_vars = [
        'TELEGRAM_BOT_TOKEN',
        'TELEGRAM_CHANNEL_ID', 
        'OPENROUTER_API_KEY',
        'ADMIN_TELEGRAM_ID'
    ]
    
    missing_vars = []
    for var in required_vars:
        if f'{var}=ваш_' in content or f'{var}=' not in content:
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Не заполнены переменные: {', '.join(missing_vars)}")
        print("📝 Отредактируйте .env файл перед деплоем")
        return False
    
    print("✅ Файл .env заполнен")
    return True

def deploy_to_render():
    """Инструкции для деплоя на Render"""
    print("""
🎯 ДЕПЛОЙ НА RENDER.COM (БЕСПЛАТНО)

1. Зайдите на https://render.com и зарегистрируйтесь
2. Подключите ваш GitHub аккаунт  
3. Создайте новый Web Service
4. Выберите этот репозиторий
5. Настройки:
   - Name: ai-news-bot
   - Environment: Python 3
   - Build Command: pip install -r requirements.txt
   - Start Command: python telegram-ai-news-bot.py

6. В разделе Environment Variables добавьте:""")
    
    # Показать переменные из .env
    if os.path.exists('.env'):
        with open('.env', 'r') as f:
            lines = f.readlines()
        
        print("\n   Переменные из вашего .env:")
        for line in lines:
            if '=' in line and not line.startswith('#'):
                key, value = line.strip().split('=', 1)
                if 'ваш_' not in value and value:
                    print(f"   {key} = {value[:20]}...")
                else:
                    print(f"   {key} = НУЖНО_ЗАПОЛНИТЬ")
    
    print("""
7. Нажмите "Create Web Service"
8. Дождитесь завершения деплоя
9. Бот автоматически запустится!

🔗 После деплоя ваш бот будет доступен по URL:
   https://your-service-name.onrender.com
""")

def deploy_to_railway():
    """Инструкции для деплоя на Railway"""
    print("""
🚆 ДЕПЛОЙ НА RAILWAY.APP ($5/месяц)

1. Зайдите на https://railway.app
2. Войдите через GitHub
3. Нажмите "Deploy from GitHub"
4. Выберите этот репозиторий
5. Railway автоматически определит Python проект
6. Добавьте переменные окружения из .env
7. Деплой произойдет автоматически!

💰 Плюсы Railway:
- НЕ засыпает (в отличие от Render бесплатного)
- Автоматическое масштабирование
- $5 кредита каждый месяц бесплатно
""")

def deploy_to_vps():
    """Инструкции для деплоя на VPS"""
    print("""
🖥️ ДЕПЛОЙ НА VPS (DigitalOcean/Vultr)

1. Создайте сервер Ubuntu 22.04
2. Подключитесь по SSH:
   ssh root@your_server_ip

3. Выполните команды:
   apt update && apt upgrade -y
   apt install python3 python3-pip git screen -y
   
   git clone https://github.com/ваш-username/ainewsbot-.git
   cd ainewsbot-
   pip3 install -r requirements.txt
   
   # Скопируйте .env файл на сервер
   nano .env
   
   # Запуск в фоновом режиме
   screen -S aibot
   python3 telegram-ai-news-bot.py
   
   # Ctrl+A, затем D для выхода
   # screen -r aibot для возврата

💡 Совет: Используйте systemd для автозапуска при перезагрузке
""")

def create_systemd_service():
    """Создание systemd сервиса для VPS"""
    service_content = f"""[Unit]
Description=AI News Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory={os.getcwd()}
ExecStart=/usr/bin/python3 {os.getcwd()}/telegram-ai-news-bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"""
    
    with open('ai-news-bot.service', 'w') as f:
        f.write(service_content)
    
    print("""
✅ Systemd сервис создан: ai-news-bot.service

Для установки на VPS:
sudo cp ai-news-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable ai-news-bot
sudo systemctl start ai-news-bot
sudo systemctl status ai-news-bot
""")

def main():
    """Главная функция"""
    print_banner()
    
    if not check_requirements():
        return
    
    create_env_template()
    
    print("\n🎛️ Выберите действие:")
    print("1. Подготовить проект к деплою")
    print("2. Инструкции для Render.com (бесплатно)")
    print("3. Инструкции для Railway.app ($5/мес)")
    print("4. Инструкции для VPS")
    print("5. Создать systemd сервис для VPS")
    print("0. Выход")
    
    choice = input("\nВаш выбор (0-5): ").strip()
    
    if choice == '1':
        setup_git_repo()
        if check_env_file():
            print("\n✅ Проект готов к деплою!")
            print("💡 Теперь загрузите код на GitHub и выберите платформу")
        else:
            print("\n❌ Заполните .env файл перед деплоем")
            
    elif choice == '2':
        deploy_to_render()
        
    elif choice == '3':
        deploy_to_railway()
        
    elif choice == '4':
        deploy_to_vps()
        
    elif choice == '5':
        create_systemd_service()
        
    elif choice == '0':
        print("👋 До свидания!")
        
    else:
        print("❌ Неверный выбор")

if __name__ == "__main__":
    main() 