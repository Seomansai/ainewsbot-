# Telegram AI News Bot
# Автоматический парсинг и публикация AI новостей

import asyncio
import sqlite3
import feedparser
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import re
import os
import json
import time
import random
from dataclasses import dataclass
from threading import Thread, Lock
from http.server import HTTPServer, SimpleHTTPRequestHandler

import aiohttp
from openai import OpenAI
from telegram import Bot
from telegram.error import TelegramError, RetryAfter, TimedOut

# Загрузка переменных окружения из .env файла
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ai_news_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ===== СИСТЕМА КОНТРОЛЯ РАСХОДОВ =====
class CostTracker:
    """Отслеживание расходов на AI модели"""
    
    def __init__(self, max_monthly_budget: float = 5.0, storage_path: str = "cost_data.json"):
        self.max_monthly_budget = max_monthly_budget
        self.storage_path = storage_path
        self.costs = self._load_costs()
        self._lock = Lock()
        
    def _load_costs(self) -> Dict:
        """Загрузка данных о расходах"""
        try:
            if os.path.exists(self.storage_path):
                with open(self.storage_path, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Ошибка загрузки данных о расходах: {e}")
        
        return {
            "monthly_costs": {},
            "daily_costs": {},
            "model_usage": {}
        }
    
    def _save_costs(self):
        """Сохранение данных о расходах"""
        try:
            with open(self.storage_path, 'w') as f:
                json.dump(self.costs, f, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения данных о расходах: {e}")
    
    def get_current_month_key(self) -> str:
        return datetime.now().strftime("%Y-%m")
    
    def can_afford_request(self, estimated_cost: float) -> bool:
        """Проверка, можем ли позволить себе запрос"""
        with self._lock:
            month_key = self.get_current_month_key()
            current_monthly_cost = self.costs["monthly_costs"].get(month_key, 0.0)
            return (current_monthly_cost + estimated_cost) <= self.max_monthly_budget
    
    def estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Оценка стоимости запроса"""
        model_prices = {
            "anthropic/claude-3.5-sonnet": {"input": 3.0, "output": 15.0},
            "openai/gpt-4o": {"input": 2.5, "output": 10.0},
            "openai/gpt-3.5-turbo": {"input": 0.5, "output": 1.5},
            "meta-llama/llama-3.1-8b-instruct:free": {"input": 0.0, "output": 0.0},
            "microsoft/wizardlm-2-8x22b:free": {"input": 0.0, "output": 0.0},
        }
        
        if model not in model_prices:
            return (input_tokens * 1.0 + output_tokens * 3.0) / 1_000_000
        
        prices = model_prices[model]
        input_cost = (input_tokens * prices["input"]) / 1_000_000
        output_cost = (output_tokens * prices["output"]) / 1_000_000
        return input_cost + output_cost
    
    def record_usage(self, model: str, input_tokens: int, output_tokens: int, actual_cost: Optional[float] = None):
        """Запись использования модели"""
        if actual_cost is None:
            actual_cost = self.estimate_cost(model, input_tokens, output_tokens)
        
        with self._lock:
            month_key = self.get_current_month_key()
            day_key = datetime.now().strftime("%Y-%m-%d")
            
            # Обновляем месячные расходы
            if month_key not in self.costs["monthly_costs"]:
                self.costs["monthly_costs"][month_key] = 0.0
            self.costs["monthly_costs"][month_key] += actual_cost
            
            # Обновляем дневные расходы
            if day_key not in self.costs["daily_costs"]:
                self.costs["daily_costs"][day_key] = 0.0
            self.costs["daily_costs"][day_key] += actual_cost
            
            self._save_costs()
            
            # Проверка лимитов и возврат алертов
            new_total = self.costs["monthly_costs"][month_key]
            
        logger.info(f"💰 {model}: ${actual_cost:.4f} (месяц: ${new_total:.2f})")
        
        # Возвращаем информацию для алертов
        return {
            'cost': actual_cost,
            'monthly_total': new_total,
            'budget_percentage': (new_total / self.max_monthly_budget) * 100
        }
    
    def get_remaining_budget(self) -> float:
        """Получение остатка бюджета"""
        month_key = self.get_current_month_key()
        current_spending = self.costs["monthly_costs"].get(month_key, 0.0)
        return max(0.0, self.max_monthly_budget - current_spending)
    
    def suggest_model(self, required_quality: str = "medium") -> str:
        """Предложение модели в зависимости от бюджета"""
        remaining = self.get_remaining_budget()
        
        if remaining <= 0:
            return "meta-llama/llama-3.1-8b-instruct:free"
        
        if required_quality == "high" and remaining > 1.0:
            return "anthropic/claude-3.5-sonnet"
        elif required_quality == "medium" and remaining > 0.1:
            return "openai/gpt-3.5-turbo"
        else:
            return "meta-llama/llama-3.1-8b-instruct:free"
    
    def check_budget_alerts(self, usage_info: dict) -> Optional[str]:
        """Проверка необходимости алертов о бюджете"""
        percentage = usage_info['budget_percentage']
        monthly_total = usage_info['monthly_total']
        
        # Алерт при 75% бюджета
        if 75 <= percentage < 90:
            return f"⚠️ <b>Предупреждение о бюджете</b>\n\n" \
                   f"Использовано: ${monthly_total:.2f} из ${self.max_monthly_budget}\n" \
                   f"Процент: {percentage:.1f}%\n" \
                   f"Остаток: ${self.max_monthly_budget - monthly_total:.2f}"
        
        # Критический алерт при 90% бюджета
        elif 90 <= percentage < 100:
            return f"🚨 <b>КРИТИЧЕСКОЕ предупреждение!</b>\n\n" \
                   f"Использовано: ${monthly_total:.2f} из ${self.max_monthly_budget}\n" \
                   f"Процент: {percentage:.1f}%\n" \
                   f"Остаток: ${self.max_monthly_budget - monthly_total:.2f}\n" \
                   f"⚡ Скоро переключение на бесплатную модель!"
        
        # Алерт при превышении лимита
        elif percentage >= 100:
            return f"🛑 <b>БЮДЖЕТ ПРЕВЫШЕН!</b>\n\n" \
                   f"Использовано: ${monthly_total:.2f} из ${self.max_monthly_budget}\n" \
                   f"Превышение: ${monthly_total - self.max_monthly_budget:.2f}\n" \
                   f"🔄 Бот переключился на бесплатную модель"
        
        return None

# ===== RETRY ДЕКОРАТОР =====
def retry_with_backoff(max_attempts: int = 3, base_delay: float = 1.0):
    """Декоратор для retry с exponential backoff"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except (TelegramError, aiohttp.ClientError, Exception) as e:
                    last_exception = e
                    
                    if attempt == max_attempts - 1:
                        break
                    
                    # Экспоненциальная задержка с jitter
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    logger.warning(f"Попытка {attempt + 1} неудачна, повтор через {delay:.1f}с: {e}")
                    await asyncio.sleep(delay)
            
            logger.error(f"Все {max_attempts} попыток неудачны: {last_exception}")
            raise last_exception
        
        return wrapper
    return decorator

# Простой HTTP сервер для keep-alive
def run_server():
    """Запуск простого HTTP сервера для keep-alive"""
    port = int(os.environ.get('PORT', 8000))
    
    class KeepAliveHandler(SimpleHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b'AI News Bot is running!')
    
    server = HTTPServer(('', port), KeepAliveHandler)
    print(f"Keep-alive server running on port {port}")
    server.serve_forever()

@dataclass
class NewsItem:
    """Структура данных для новости"""
    title: str
    description: str
    link: str
    published: datetime
    source: str
    translated_title: str = ""
    translated_description: str = ""

class AINewsBot:
    """Основной класс Telegram бота для AI новостей"""
    
    def __init__(self):
        # Конфигурация из переменных окружения
        load_dotenv()
        
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.channel_id = os.getenv('TELEGRAM_CHANNEL_ID')
        self.openrouter_api_key = os.getenv('OPENROUTER_API_KEY')
        
        # Основные настройки
        self.ai_model = os.getenv('AI_MODEL', 'anthropic/claude-3.5-sonnet')
        self.max_monthly_cost = float(os.getenv('MAX_MONTHLY_COST', '5.0'))
        self.max_news_per_cycle = int(os.getenv('MAX_NEWS_PER_CYCLE', '10'))
        self.admin_telegram_id = os.getenv('ADMIN_TELEGRAM_ID')
        
        # Умный путь к базе данных
        db_path_env = os.getenv('DATABASE_PATH', 'ai_news.db')
        
        # Проверяем, работаем ли на облачном сервере
        if os.path.exists('/opt/render') or os.getenv('RENDER'):
            # На Render используем абсолютный путь
            self.db_path = '/opt/render/project/ai_news.db'
        elif os.path.exists('/app'):  # Railway/Heroku
            self.db_path = '/app/ai_news.db'
        else:
            # Локальная разработка
            self.db_path = db_path_env
        
        logger.info(f"📁 Путь к базе данных: {self.db_path}")
        
        if not self.bot_token or not self.channel_id:
            raise ValueError("Необходимо установить TELEGRAM_BOT_TOKEN и TELEGRAM_CHANNEL_ID")
        
        self.bot = Bot(token=self.bot_token)
        
        # Инициализация системы контроля расходов
        self.cost_tracker = CostTracker(self.max_monthly_cost)
        
        # Инициализация OpenRouter клиента
        self.client = None
        if self.openrouter_api_key:
            self.client = OpenAI(
                api_key=self.openrouter_api_key,
                base_url="https://openrouter.ai/api/v1"
            )
            logger.info("✅ Claude 3.5 Sonnet инициализирован для RSS обработки")
            logger.info(f"💰 Остаток бюджета: ${self.cost_tracker.get_remaining_budget():.2f}")
        else:
            logger.warning("⚠️ OPENROUTER_API_KEY не найден, используется упрощенный режим")
        
        # RSS источники AI новостей (ТОП-20 русскоязычных)
        self.rss_sources = {
            # ===== ТОП-20 РУССКОЯЗЫЧНЫХ ИСТОЧНИКОВ AI И ТЕХНОЛОГИЙ =====
            
            # 🏆 Хабр - главные AI хабы
            'Хабр AI': 'https://habr.com/ru/rss/hub/artificial_intelligence/',
            'Хабр ML': 'https://habr.com/ru/rss/hub/machine_learning/',
            'Хабр DataScience': 'https://habr.com/ru/rss/hub/data_mining/',
            'Хабр Neural Networks': 'https://habr.com/ru/rss/hub/neural_networks/',
            'Хабр Python': 'https://habr.com/ru/rss/hub/python/',
            
            # 🔥 Профильные tech-издания
            'Tproger': 'https://tproger.ru/feed/',
            'VC.ru Tech': 'https://vc.ru/feed',
            'DTF Tech': 'https://dtf.ru/rss/all',
            
            # 📰 Технологические новостные порталы
            'CNews': 'https://www.cnews.ru/inc/rss/news.xml',
            '3DNews': 'https://3dnews.ru/news/rss/',
            'Digit.ru': 'https://digit.ru/rss/',
            'Hi-Tech Mail.ru': 'https://hi-tech.mail.ru/rss/',
            
            # 🛡️ Кибербезопасность и хакерство
            'Xakep.ru': 'https://xakep.ru/feed/',
            'SecurityLab': 'https://www.securitylab.ru/rss.php',
            
            # 🎮 Игровая индустрия и технологии
            'StopGame Tech': 'https://stopgame.ru/rss/news.xml',
            'Игромания Tech': 'https://www.igromania.ru/rss/news.xml',
            
            # 💼 Стартапы и бизнес
            'RB.ru Tech': 'https://rb.ru/feeds/all/',
            'Forbes Russia Tech': 'https://www.forbes.ru/rss',
            
            # 🔬 Научно-популярные
            'N+1 Tech': 'https://nplus1.ru/rss',
            'Популярная Механика': 'https://www.popmech.ru/rss/',
        }
        
        # Строгие ключевые слова для AI (только релевантные)
        self.ai_keywords = [
            # Основные AI термины
            'artificial intelligence', 'machine learning', 'neural network', 'deep learning',
            'chatgpt', 'gpt', 'openai', 'claude', 'anthropic', 'gemini', 'bard',
            'llm', 'large language model', 'generative ai', 'transformer',
            'computer vision', 'nlp', 'natural language processing',
            'tensorflow', 'pytorch', 'hugging face', 'algorithm',
            
            # Технические AI термины  
            'robotics', 'automation', 'data science', 'big data',
            'cybersecurity ai', 'ai security', 'ai ethics',
            
            # ===== РАСШИРЕННЫЕ РУССКИЕ AI ТЕРМИНЫ =====
            # Основные
            'искусственный интеллект', 'машинное обучение', 'нейронная сеть', 'нейросеть',
            'глубокое обучение', 'чатгпт', 'gpt', 'клод', 'гемини',
            'языковая модель', 'генеративный ии', 'трансформер',
            'компьютерное зрение', 'обработка естественного языка',
            
            # Российские AI платформы
            'yandex gpt', 'яндекс гпт', 'gigachat', 'гигачат',
            'kandinsky', 'кандинский', 'rubert', 'rudalcore',
            'сбер ai', 'сберapi', 'salute ai',
            
            # Технологические
            'алгоритм', 'роботика', 'автоматизация', 'анализ данных', 'большие данные',
            'кибербезопасность ии', 'этика ии', 'python', 'tensorflow', 'pytorch',
            'машинное зрение', 'распознавание речи', 'синтез речи',
            'рекомендательная система', 'предиктивная аналитика',
            
            # Бизнес и стартапы
            'стартап ai', 'ии стартап', 'tech стартап', 'финтех',
            'edtech', 'healthtech', 'regtech', 'insurtech',
            'цифровизация', 'диджитализация', 'цифровая трансформация',
            
            # Конкретные технологии
            'блокчейн', 'криптовалюта', 'nft', 'метавселенная', 'vr', 'ar',
            'квантовые вычисления', 'edge computing', 'iot', 'интернет вещей',
            '5g', '6g', 'облачные вычисления', 'микросервисы',
            
            # Программирование и разработка
            'фронтенд', 'бэкенд', 'fullstack', 'devops', 'mlops',
            'api', 'sdk', 'framework', 'библиотека', 'opensource',
            'github', 'gitlab', 'docker', 'kubernetes'
        ]
        
        # Исключающие слова (новости с этими словами НЕ относятся к AI)
        self.exclude_keywords = [
            # Общие исключения
            'политика', 'выборы', 'война', 'санкции', 'экономика', 'нефть', 'газ',
            'спорт', 'футбол', 'хоккей', 'игры', 'кино', 'музыка', 'артист',
            'politics', 'election', 'war', 'sanctions', 'economy', 'oil', 'gas',
            'sport', 'football', 'hockey', 'movie', 'music', 'artist',
            # Технологические, но не AI
            'iphone', 'samsung', 'apple', 'microsoft office', 'windows', 'блокнот',
            'xbox', 'playstation', 'steam', 'twitch', 'discord'
        ]
        
        # Thread-safe база данных
        self._db_lock = Lock()
        
        # Инициализация базы данных
        self.init_database()
    
    def init_database(self):
        """Инициализация базы данных с улучшенной диагностикой"""
        logger.info(f"🗄️ Инициализация базы данных: {self.db_path}")
        
        # Создаем директорию если нужно
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            try:
                os.makedirs(db_dir, exist_ok=True)
                logger.info(f"📂 Создана директория: {db_dir}")
            except Exception as e:
                logger.error(f"❌ Ошибка создания директории {db_dir}: {e}")
        
        # Проверяем права на запись
        try:
            test_file = os.path.join(db_dir if db_dir else '.', 'test_write.tmp')
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            logger.info("✅ Права на запись в директорию БД подтверждены")
        except Exception as e:
            logger.warning(f"⚠️ Проблема с правами записи: {e}")
        
        with self._db_lock:
            try:
                self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
                
                # СНАЧАЛА создаем таблицу если её нет
                self.conn.execute("""
                    CREATE TABLE IF NOT EXISTS published_news (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        link TEXT UNIQUE NOT NULL,
                        title TEXT,
                        source TEXT,
                        published_date DATETIME,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        status TEXT DEFAULT 'reserved'
                    )
                """)
                
                # ПОТОМ проверяем существование колонки status и добавляем если нужно
                cursor = self.conn.execute("PRAGMA table_info(published_news)")
                columns = [col[1] for col in cursor.fetchall()]
                
                if 'status' not in columns:
                    logger.info("🔄 Миграция БД: добавляем колонку 'status'")
                    self.conn.execute("ALTER TABLE published_news ADD COLUMN status TEXT DEFAULT 'published'")
                    # Все существующие записи помечаем как опубликованные
                    self.conn.execute("UPDATE published_news SET status = 'published' WHERE status IS NULL")
                    self.conn.commit()
                    logger.info("✅ Миграция завершена")
                
                # Создание индексов для быстрого поиска
                self.conn.execute("CREATE INDEX IF NOT EXISTS idx_link ON published_news(link)")
                self.conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON published_news(status)")
                self.conn.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON published_news(created_at)")
                
                self.conn.commit()
                
                # Логирование статистики
                count = self.conn.execute("SELECT COUNT(*) FROM published_news").fetchone()[0]
                published_count = self.conn.execute("SELECT COUNT(*) FROM published_news WHERE status = 'published'").fetchone()[0]
                reserved_count = self.conn.execute("SELECT COUNT(*) FROM published_news WHERE status = 'reserved'").fetchone()[0]
                
                logger.info(f"📊 База данных готова. Всего: {count} | Опубликовано: {published_count} | Зарезервировано: {reserved_count}")
                
                # Очищаем старые зарезервированные записи (старше 1 часа)
                old_reserved = datetime.now() - timedelta(hours=1)
                deleted = self.conn.execute(
                    "DELETE FROM published_news WHERE status = 'reserved' AND created_at < ?", 
                    (old_reserved,)
                ).rowcount
                
                if deleted > 0:
                    self.conn.commit()
                    logger.info(f"🧹 Очищено {deleted} старых зарезервированных записей")
                    
            except Exception as e:
                logger.error(f"❌ Критическая ошибка инициализации БД: {e}")
                raise
    
    @retry_with_backoff(max_attempts=3, base_delay=2.0)
    async def fetch_rss_feed(self, url: str) -> List[Dict]:
        """Асинхронное получение RSS фида с retry"""
        try:
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    # Принимаем все успешные статусы 2xx (200, 201, 202, etc.)
                    if not (200 <= response.status < 300):
                        raise aiohttp.ClientError(f"HTTP {response.status}")
                    
                    content = await response.text()
                    feed = feedparser.parse(content)
                    
                    # Проверка на валидность RSS фида
                    if hasattr(feed, 'entries') and len(feed.entries) > 0:
                        logger.info(f"✅ RSS фид получен: {len(feed.entries)} записей (HTTP {response.status})")
                        return feed.entries
                    else:
                        logger.warning(f"⚠️ RSS фид пуст или невалиден: {url}")
                        return []
                        
        except Exception as e:
            logger.error(f"Ошибка при получении RSS фида {url}: {e}")
            raise
    
    def is_ai_related(self, title: str, description: str) -> bool:
        """Строгая проверка, относится ли новость к AI"""
        text = (title + " " + description).lower()
        
        # Сначала проверяем исключающие слова
        for exclude_word in self.exclude_keywords:
            if exclude_word.lower() in text:
                return False
        
        # Затем ищем AI ключевые слова
        ai_matches = 0
        for keyword in self.ai_keywords:
            if keyword.lower() in text:
                ai_matches += 1
                
        # Требуем минимум 1 совпадение для AI
        return ai_matches >= 1
    
    def is_already_published(self, link: str, title: str = "") -> bool:
        """Расширенная проверка дубликатов: по ссылке и похожему заголовку"""
        with self._db_lock:
            # Проверка 1: Точное совпадение ссылки (опубликованные или зарезервированные)
            cursor = self.conn.execute(
                "SELECT status FROM published_news WHERE link = ?", (link,)
            )
            result = cursor.fetchone()
            if result is not None:
                status = result[0]
                logger.info(f"🔄 Дубликат найден (статус: {status}): {link[:50]}...")
                return True
            
            # Проверка 2: Похожий заголовок (если указан)
            if title and len(title) > 20:
                # Упрощаем заголовок для сравнения
                clean_title = self._clean_title_for_comparison(title)
                
                cursor = self.conn.execute(
                    "SELECT title, status FROM published_news WHERE created_at > datetime('now', '-7 days')"
                )
                existing_titles = cursor.fetchall()
                
                for (existing_title, status) in existing_titles:
                    if existing_title:
                        clean_existing = self._clean_title_for_comparison(existing_title)
                        # Проверяем схожесть (>80% совпадение)
                        if self._calculate_similarity(clean_title, clean_existing) > 0.8:
                            logger.info(f"🔄 Дубликат по заголовку (статус: {status}): {title[:50]}... ≈ {existing_title[:50]}...")
                            return True
            
            logger.info(f"✅ Новая новость: {link[:50]}...")
            return False
    
    def _clean_title_for_comparison(self, title: str) -> str:
        """Очистка заголовка для сравнения"""
        import re
        # Убираем специальные символы, приводим к нижнему регистру
        cleaned = re.sub(r'[^\w\s]', '', title.lower())
        # Убираем лишние пробелы
        cleaned = ' '.join(cleaned.split())
        return cleaned
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Вычисление схожести текстов (упрощенный алгоритм)"""
        if not text1 or not text2:
            return 0.0
        
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union) if union else 0.0
    
    def mark_as_published(self, news: NewsItem):
        """Обновление статуса новости на 'published'"""
        with self._db_lock:
            try:
                # Обновляем статус с reserved на published
                cursor = self.conn.execute(
                    "UPDATE published_news SET status = 'published' WHERE link = ?",
                    (news.link,)
                )
                
                if cursor.rowcount == 0:
                    # Если записи нет, создаем новую (резервный вариант)
                    self.conn.execute(
                        "INSERT OR IGNORE INTO published_news (link, title, source, published_date, status) VALUES (?, ?, ?, ?, 'published')",
                        (news.link, news.title, news.source, news.published)
                    )
                
                self.conn.commit()
                logger.info(f"📝 Статус обновлен на 'published': {news.title[:50]}...")
            except Exception as e:
                logger.error(f"❌ Ошибка обновления статуса в БД: {e}")
    
    def reserve_news_for_processing(self, news_list: List[NewsItem]) -> List[NewsItem]:
        """Резервирование новостей для обработки (предотвращение дубликатов)"""
        reserved_news = []
        
        with self._db_lock:
            for news in news_list:
                try:
                    # Пытаемся зарезервировать новость
                    cursor = self.conn.execute(
                        "INSERT OR IGNORE INTO published_news (link, title, source, published_date, status) VALUES (?, ?, ?, ?, 'reserved')",
                        (news.link, news.title, news.source, news.published)
                    )
                    
                    # Проверяем, была ли вставка успешной
                    if cursor.rowcount > 0:
                        reserved_news.append(news)
                        logger.info(f"🔒 Зарезервировано: {news.title[:50]}...")
                    else:
                        logger.info(f"🔄 Уже существует: {news.title[:50]}...")
                        
                except Exception as e:
                    logger.error(f"❌ Ошибка резервирования новости: {e}")
            
            self.conn.commit()
        
        logger.info(f"✅ Зарезервировано {len(reserved_news)} из {len(news_list)} новостей")
        return reserved_news
    
    def detect_language(self, text: str) -> str:
        """Определение языка текста (ru или en)"""
        # Простой алгоритм на основе наличия кириллицы
        cyrillic_chars = sum(1 for char in text if 'а' <= char.lower() <= 'я')
        latin_chars = sum(1 for char in text if 'a' <= char.lower() <= 'z')
        
        if cyrillic_chars > latin_chars:
            return 'ru'
        else:
            return 'en'
    
    def is_russian_source(self, source_name: str) -> bool:
        """Проверка, является ли источник российским"""
        russian_sources = [
            # Хабр хабы
            'Хабр AI', 'Хабр ML', 'Хабр DataScience', 'Хабр Neural Networks', 'Хабр Python',
            # Tech издания
            'Tproger', 'VC.ru Tech', 'DTF Tech',
            # Новостные порталы
            'CNews', '3DNews', 'Digit.ru', 'Hi-Tech Mail.ru',
            # Кибербезопасность
            'Xakep.ru', 'SecurityLab',
            # Игры и технологии
            'StopGame Tech', 'Игромания Tech',
            # Бизнес
            'RB.ru Tech', 'Forbes Russia Tech',
            # Научпоп
            'N+1 Tech', 'Популярная Механика'
        ]
        return source_name in russian_sources
    
    async def translate_news(self, news_list: List[NewsItem]) -> List[NewsItem]:
        """Упрощенная обработка RSS с Claude - прямой перевод/пересказ"""
        for news in news_list:
            try:
                # Определяем язык и источник
                language = self.detect_language(news.title + " " + news.description)
                is_russian = self.is_russian_source(news.source)
                
                # Логирование
                lang_emoji = "🇷🇺" if language == 'ru' or is_russian else "🇺🇸"
                logger.info(f"{lang_emoji} Claude обработка: {news.title[:50]}...")
                
                # Очистка заголовка
                news.translated_title = self.clean_html(news.title)
                
                # Обработка через Claude или упрощенная очистка
                if self.client:
                    # Создаем качественный пересказ через Claude
                    full_text = f"{news.title}. {news.description}"
                    detected_lang = 'ru' if (language == 'ru' or is_russian) else 'en'
                    news.translated_description = await self.process_with_claude(full_text, detected_lang)
                else:
                    # Fallback - простая очистка HTML
                    news.translated_description = self.clean_html(news.description)
                
                # Задержка между запросами
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"Ошибка при обработке новости: {e}")
                news.translated_title = self.clean_html(news.title)
                news.translated_description = self.clean_html(news.description)
        
        return news_list
    
    async def process_with_claude(self, text: str, language: str = "en") -> str:
        """Упрощенная обработка через Claude"""
        try:
            if len(text) > 2000:
                text = text[:2000] + "..."
            
            # Умный выбор модели с проверкой бюджета
            model = self.ai_model
            estimated_input_tokens = len(text) // 4
            estimated_output_tokens = estimated_input_tokens // 3
            
            estimated_cost = self.cost_tracker.estimate_cost(
                model, estimated_input_tokens, estimated_output_tokens
            )
            
            if not self.cost_tracker.can_afford_request(estimated_cost):
                logger.warning("🚫 Превышен бюджет, используем бесплатную модель")
                model = "meta-llama/llama-3.1-8b-instruct:free"
            
            # Упрощенный промпт для RSS
            if language == 'ru':
                system_prompt = """Ты помощник для обработки RSS новостей. 

Создай краткий, читаемый пересказ русской новости об AI/технологиях:
- 2-3 предложения максимум
- Сохраняй важную информацию (компании, цифры, технологии)
- Убирай HTML теги и рекламу
- Простой понятный язык"""
                
                user_content = f"Обработай эту RSS новость:\n\n{text}"
            else:
                system_prompt = """Ты помощник для обработки RSS новостей.

Переведи английскую новость на русский и создай краткий пересказ:
- 2-3 предложения максимум  
- Сохраняй важную информацию (компании, цифры, технологии)
- Убирай HTML теги и рекламу
- Простой понятный русский язык"""
                
                user_content = f"Переведи и обработай эту RSS новость:\n\n{text}"
            
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                temperature=0.2,
                max_tokens=600
            )
            
            # Запись расходов
            if hasattr(response, 'usage') and response.usage:
                usage_info = self.cost_tracker.record_usage(
                    model, 
                    response.usage.prompt_tokens,
                    response.usage.completion_tokens
                )
                
                # Проверка алертов
                if usage_info and self.admin_telegram_id:
                    alert_message = self.cost_tracker.check_budget_alerts(usage_info)
                    if alert_message:
                        await self._send_admin_alert(alert_message)
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Ошибка Claude обработки: {e}")
            return self.clean_html(text)  # Fallback на простую очистку
    
    def clean_html(self, text: str) -> str:
        """Очистка HTML тегов и форматирование текста"""
        if not text:
            return ""
        
        import re
        import html
        
        # Декодируем HTML entities
        text = html.unescape(text)
        
        # Убираем HTML теги
        text = re.sub(r'<[^>]+>', '', text)
        
        # Убираем лишние пробелы и переносы строк
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        # Ограничиваем длину (Telegram лимит)
        if len(text) > 800:
            text = text[:800] + "..."
        
        return text
    
    def format_message(self, news: NewsItem) -> str:
        """Форматирование RSS сообщения для Telegram"""
        import html
        
        # Экранирование для HTML режима Telegram
        title = html.escape(news.translated_title) if news.translated_title else html.escape(news.title)
        description = html.escape(news.translated_description) if news.translated_description else html.escape(news.description)
        
        # Определение флага источника
        is_russian = self.is_russian_source(news.source)
        source_flag = "🇷🇺" if is_russian else "🌍"
        
        # Форматирование сообщения
        message = f"🤖 <b>AI Новости</b>\n\n"
        
        # Заголовок
        if title:
            message += f"<b>{title}</b>\n\n"
        
        # Описание (если есть)
        if description and len(description.strip()) > 0:
            message += f"{description}\n\n"
        
        # Информация об источнике
        message += f"{source_flag} <b>Источник:</b> {news.source}\n"
        message += f"🔗 <a href='{news.link}'>Читать полностью</a>"
        
        return message
    
    @retry_with_backoff(max_attempts=3, base_delay=2.0)
    async def publish_news(self, news_list: List[NewsItem]):
        """Публикация новостей в Telegram канал с retry"""
        published_count = 0
        
        for news in news_list[:self.max_news_per_cycle]:
            try:
                message = self.format_message(news)
                
                await self._send_telegram_message(message)
                
                # Отмечаем как опубликованную
                self.mark_as_published(news)
                published_count += 1
                
                logger.info(f"📢 Опубликована новость: {news.title[:50]}...")
                
                # Задержка между публикациями (Telegram rate limit)
                await asyncio.sleep(3)
                
            except Exception as e:
                logger.error(f"Ошибка при публикации новости {news.title[:50]}: {e}")
                
                # Отправляем алерт админу если настроен
                if self.admin_telegram_id:
                    await self._send_admin_alert(f"❌ Ошибка публикации: {str(e)[:100]}")
        
        return published_count
    
    @retry_with_backoff(max_attempts=5, base_delay=1.0)
    async def _send_telegram_message(self, message: str):
        """Отправка сообщения в Telegram с обработкой rate limits"""
        try:
            await self.bot.send_message(
                chat_id=self.channel_id,
                text=message,
                parse_mode='HTML',
                disable_web_page_preview=False
            )
        except RetryAfter as e:
            logger.warning(f"Rate limit, ожидание {e.retry_after} секунд")
            await asyncio.sleep(e.retry_after)
            raise  # Retry decorator повторит
        except TimedOut:
            logger.warning("Telegram timeout, повторная попытка")
            raise  # Retry decorator повторит
        except TelegramError as e:
            logger.error(f"Telegram error: {e}")
            raise
    
    async def _send_admin_alert(self, message: str):
        """Отправка алерта администратору"""
        if not self.admin_telegram_id:
            return
            
        try:
            alert_message = f"🤖 <b>AI News Bot Alert</b>\n\n{message}\n\n<i>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>"
            await self.bot.send_message(
                chat_id=self.admin_telegram_id,
                text=alert_message,
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Ошибка отправки алерта админу: {e}")
    
    def cleanup_old_records(self):
        """Умная очистка старых записей из базы данных"""
        with self._db_lock:
            # Очищаем записи старше 30 дней
            cutoff_date = datetime.now() - timedelta(days=30)
            
            # Подсчитываем количество записей до очистки
            total_before = self.conn.execute("SELECT COUNT(*) FROM published_news").fetchone()[0]
            
            # Удаляем старые записи
            cursor = self.conn.execute(
                "DELETE FROM published_news WHERE created_at < ?",
                (cutoff_date,)
            )
            deleted_count = cursor.rowcount
            
            # Оптимизируем базу данных
            self.conn.execute("VACUUM")
            self.conn.commit()
            
            total_after = self.conn.execute("SELECT COUNT(*) FROM published_news").fetchone()[0]
            
            if deleted_count > 0:
                logger.info(f"🧹 Очистка БД: удалено {deleted_count} старых записей. Осталось: {total_after}")
            else:
                logger.info(f"📊 БД актуальна: {total_after} записей, очистка не требуется")
    
    def get_duplicate_stats(self) -> dict:
        """Статистика по дубликатам за последнюю неделю"""
        with self._db_lock:
            # Подсчитываем записи за неделю
            week_ago = datetime.now() - timedelta(days=7)
            
            cursor = self.conn.execute(
                "SELECT COUNT(*) FROM published_news WHERE created_at > ?",
                (week_ago,)
            )
            week_count = cursor.fetchone()[0]
            
            # Общее количество записей
            total_count = self.conn.execute("SELECT COUNT(*) FROM published_news").fetchone()[0]
            
            return {
                'total_saved': total_count,
                'last_week': week_count,
                'estimated_duplicates_blocked': max(0, week_count * 2)  # Приблизительная оценка
            }
    
    def get_statistics(self) -> Dict:
        """Получение статистики работы бота"""
        with self._db_lock:
            cursor = self.conn.execute(
                "SELECT COUNT(*) FROM published_news WHERE status = 'published' AND created_at > ?",
                (datetime.now() - timedelta(hours=24),)
            )
            last_24h = cursor.fetchone()[0]
            
            cursor = self.conn.execute("SELECT COUNT(*) FROM published_news WHERE status = 'published'")
            total = cursor.fetchone()[0]
        
        remaining_budget = self.cost_tracker.get_remaining_budget() if hasattr(self, 'cost_tracker') else 0
        
        return {
            'total_published': total,
            'last_24h': last_24h,
            'remaining_budget': remaining_budget,
            'current_model': getattr(self, 'ai_model', 'claude-3.5-sonnet'),
            'status': 'active'
        }
    
    async def run_news_cycle(self):
        """Основной цикл парсинга и публикации новостей с улучшенной обработкой ошибок"""
        cycle_start_time = time.time()
        
        try:
            # Логирование состояния
            stats = self.get_statistics()
            logger.info(f"📊 Запуск цикла. БД: {stats['total_published']} новостей, Бюджет: ${stats['remaining_budget']:.2f}")
            
            # Парсинг новостей
            logger.info("🔍 Начинаем парсинг источников...")
            raw_news = await self.parse_news_sources()
            logger.info(f"📰 Найдено {len(raw_news)} потенциальных новостей")
            
            if not raw_news:
                logger.info("❌ Новые новости не найдены")
                return
            
            # НОВОЕ: Резервирование новостей перед обработкой
            logger.info("🔒 Резервируем новости для обработки...")
            reserved_news = self.reserve_news_for_processing(raw_news)
            
            if not reserved_news:
                logger.info("❌ Все новости уже зарезервированы или опубликованы")
                return
            
            # Обработка через Claude (упрощенная)
            logger.info(f"🤖 Claude обрабатывает {len(reserved_news)} RSS новостей...")
            translated_news = await self.translate_news(reserved_news)
            
            # Публикация
            logger.info(f"📢 Публикуем до {self.max_news_per_cycle} новостей...")
            published_count = await self.publish_news(translated_news)
            
            # Финальная статистика
            cycle_duration = time.time() - cycle_start_time
            new_stats = self.get_statistics()
            
            logger.info(f"✅ Цикл завершен за {cycle_duration:.1f}с. Опубликовано: {published_count} новостей")
            
            # Отправляем статистику админу
            if self.admin_telegram_id and published_count > 0:
                await self._send_admin_alert(
                    f"📊 Claude RSS цикл завершен\n"
                    f"• Найдено новостей: {len(raw_news)}\n"
                    f"• Зарезервировано: {len(reserved_news)}\n"
                    f"• Опубликовано: {published_count}\n"
                    f"• Время: {cycle_duration:.1f}с\n"
                    f"• Остаток бюджета: ${new_stats['remaining_budget']:.2f}"
                )
            
        except Exception as e:
            logger.error(f"❌ Критическая ошибка в цикле: {e}")
            
            # Отправляем алерт админу
            if self.admin_telegram_id:
                await self._send_admin_alert(f"🚨 КРИТИЧЕСКАЯ ОШИБКА: {str(e)}")
            
            raise
    
    def database_diagnostics(self) -> Dict:
        """Диагностика состояния базы данных"""
        with self._db_lock:
            # Проверяем существование файла БД
            db_exists = os.path.exists(self.db_path)
            db_size = os.path.getsize(self.db_path) if db_exists else 0
            
            # Статистика по статусам
            total_records = self.conn.execute("SELECT COUNT(*) FROM published_news").fetchone()[0]
            published_count = self.conn.execute("SELECT COUNT(*) FROM published_news WHERE status = 'published'").fetchone()[0]
            reserved_count = self.conn.execute("SELECT COUNT(*) FROM published_news WHERE status = 'reserved'").fetchone()[0]
            
            # Последние записи
            cursor = self.conn.execute(
                "SELECT link, title, status, created_at FROM published_news ORDER BY created_at DESC LIMIT 5"
            )
            recent_records = cursor.fetchall()
            
            # Записи за последние 24 часа
            day_ago = datetime.now() - timedelta(hours=24)
            cursor = self.conn.execute(
                "SELECT COUNT(*) FROM published_news WHERE created_at > ?", (day_ago,)
            )
            recent_count = cursor.fetchone()[0]
            
            return {
                'db_path': self.db_path,
                'db_exists': db_exists,
                'db_size_bytes': db_size,
                'total_records': total_records,
                'published_count': published_count,
                'reserved_count': reserved_count,
                'recent_24h': recent_count,
                'recent_records': recent_records
            }

    async def start_bot(self):
        """Запуск бота с периодическими проверками и мониторингом"""
        logger.info("🚀 Запуск AI News Bot...")
        
        # Диагностика базы данных при запуске
        db_diagnostics = self.database_diagnostics()
        logger.info(f"🔍 Диагностика БД:")
        logger.info(f"  • Путь: {db_diagnostics['db_path']}")
        logger.info(f"  • Размер: {db_diagnostics['db_size_bytes']} байт")
        logger.info(f"  • Всего записей: {db_diagnostics['total_records']}")
        logger.info(f"  • Опубликовано: {db_diagnostics['published_count']}")
        logger.info(f"  • Зарезервировано: {db_diagnostics['reserved_count']}")
        logger.info(f"  • За 24 часа: {db_diagnostics['recent_24h']}")
        
        # Добавляем мониторинг если файл существует
        try:
            from bot_monitoring import add_monitoring_to_bot
            add_monitoring_to_bot(self)
            logger.info("📊 Мониторинг подключен")
        except ImportError:
            logger.warning("⚠️ Модуль мониторинга не найден")
        
        # Отправляем уведомление о запуске админу с диагностикой
        if self.admin_telegram_id:
            startup_message = (
                f"🚀 AI News Bot запущен!\n\n"
                f"<b>Конфигурация:</b>\n"
                f"• Режим: Claude RSS обработка\n"
                f"• Модель: {self.ai_model}\n"
                f"• Бюджет: ${self.max_monthly_cost}\n"
                f"• Макс новостей: {self.max_news_per_cycle}\n\n"
                f"<b>База данных:</b>\n"
                f"• Путь: {db_diagnostics['db_path']}\n"
                f"• Размер: {db_diagnostics['db_size_bytes']} байт\n"
                f"• Опубликовано: {db_diagnostics['published_count']}\n"
                f"• Зарезервировано: {db_diagnostics['reserved_count']}\n"
                f"• За 24 часа: {db_diagnostics['recent_24h']}"
            )
            await self._send_admin_alert(startup_message)
        
        while True:
            try:
                await self.run_news_cycle()
                
                # Отправляем статистику админу раз в день
                if hasattr(self, 'monitor') and self.admin_telegram_id:
                    current_hour = datetime.now().hour
                    if current_hour == 12:  # В полдень
                        stats_message = self.monitor.format_summary_message()
                        await self._send_admin_alert(stats_message)
                
                # Ожидание 2 часа перед следующей проверкой
                logger.info("😴 Ожидание 2 часа до следующей проверки...")
                await asyncio.sleep(7200)  # 2 часа
                
            except KeyboardInterrupt:
                logger.info("⛔ Получен сигнал остановки")
                if self.admin_telegram_id:
                    await self._send_admin_alert("⛔ AI News Bot остановлен")
                break
            except Exception as e:
                logger.error(f"💥 Критическая ошибка: {e}")
                if self.admin_telegram_id:
                    await self._send_admin_alert(f"💥 КРИТИЧЕСКАЯ ОШИБКА: {str(e)}")
                await asyncio.sleep(300)  # Ожидание 5 минут при ошибке

    async def parse_news_sources(self) -> List[NewsItem]:
        """Парсинг всех источников новостей"""
        all_news = []
        successful_sources = 0
        failed_sources = []
        
        for source_name, rss_url in self.rss_sources.items():
            try:
                logger.info(f"🔍 Парсинг источника: {source_name}")
                entries = await self.fetch_rss_feed(rss_url)
                
                if not entries:
                    logger.warning(f"⚠️ Источник {source_name} вернул пустой результат")
                    failed_sources.append(source_name)
                    continue
                
                source_news_count = 0
                max_news_per_source = 5  # Максимум 5 новостей с одного источника
                
                for entry in entries:
                    # Останавливаемся если достигли лимита для источника
                    if source_news_count >= max_news_per_source:
                        logger.info(f"🔒 Лимит для {source_name} достигнут ({max_news_per_source} новостей)")
                        break
                        
                    try:
                        # Парсинг даты публикации
                        published = datetime.now()
                        if hasattr(entry, 'published_parsed') and entry.published_parsed:
                            published = datetime(*entry.published_parsed[:6])
                        
                        # Создание объекта новости
                        news = NewsItem(
                            title=entry.get('title', ''),
                            description=entry.get('summary', ''),
                            link=entry.get('link', ''),
                            published=published,
                            source=source_name
                        )
                        
                        # Строгая фильтрация по AI тематике
                        if self.is_ai_related(news.title, news.description):
                            # Проверка на дубликаты
                            if not self.is_already_published(news.link, news.title):
                                # Проверка актуальности (не старше 24 часов)
                                if published > datetime.now() - timedelta(hours=24):
                                    all_news.append(news)
                                    source_news_count += 1
                                    logger.info(f"✅ AI новость #{source_news_count}: {news.title[:50]}...")
                    
                    except Exception as e:
                        logger.error(f"Ошибка при обработке новости из {source_name}: {e}")
                
                if source_news_count > 0:
                    logger.info(f"✅ {source_name}: найдено {source_news_count} AI новостей")
                    successful_sources += 1
                else:
                    logger.info(f"ℹ️ {source_name}: AI новости не найдены")
                    successful_sources += 1  # Источник работает, просто нет подходящих новостей
                
            except Exception as e:
                logger.error(f"❌ Ошибка источника {source_name}: {e}")
                failed_sources.append(source_name)
        
        # Статистика парсинга
        logger.info(f"📊 Парсинг завершен: {successful_sources}/{len(self.rss_sources)} источников успешно")
        if failed_sources:
            logger.warning(f"⚠️ Недоступные источники: {', '.join(failed_sources)}")
        
        return all_news

async def main():
    """Главная функция"""
    # Запуск HTTP сервера в отдельном потоке для keep-alive
    server_thread = Thread(target=run_server, daemon=True)
    server_thread.start()
    
    try:
        bot = AINewsBot()
        await bot.start_bot()
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
    finally:
        if 'bot' in locals():
            bot.conn.close()

if __name__ == "__main__":
    asyncio.run(main())