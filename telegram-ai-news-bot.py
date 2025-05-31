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
            
        logger.info(f"💰 {model}: ${actual_cost:.4f} (месяц: ${self.costs['monthly_costs'][month_key]:.2f})")
    
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
        
        # Новые настройки
        self.ai_model = os.getenv('AI_MODEL', 'meta-llama/llama-3.1-8b-instruct:free')
        self.max_monthly_cost = float(os.getenv('MAX_MONTHLY_COST', '5.0'))
        self.max_news_per_cycle = int(os.getenv('MAX_NEWS_PER_CYCLE', '10'))
        self.admin_telegram_id = os.getenv('ADMIN_TELEGRAM_ID')
        
        # Путь к базе данных (для постоянного хранения на сервере)
        self.db_path = os.getenv('DATABASE_PATH', 'ai_news.db')
        
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
            logger.info("✅ OpenRouter клиент инициализирован")
            logger.info(f"💰 Остаток бюджета: ${self.cost_tracker.get_remaining_budget():.2f}")
        else:
            logger.warning("⚠️ OPENROUTER_API_KEY не найден, используется Google Translator")
        
        # RSS источники AI новостей
        self.rss_sources = {
            'AI News': 'https://www.artificialintelligence-news.com/feed/',
            'MIT Technology Review': 'https://www.technologyreview.com/feed/',
            'The Verge AI': 'https://www.theverge.com/ai-artificial-intelligence/rss/index.xml',
            'TechCrunch AI': 'https://techcrunch.com/category/artificial-intelligence/feed/',
            'VentureBeat AI': 'https://venturebeat.com/ai/feed/',
            'Ars Technica': 'https://feeds.arstechnica.com/arstechnica/technology-lab',
            'AI Magazine': 'https://magazine.aaai.org/index.php/aimagazine/gateway/plugin/WebFeedGatewayPlugin/atom'
        }
        
        # Ключевые слова для фильтрации AI новостей
        self.ai_keywords = [
            'ai', 'artificial intelligence', 'machine learning', 'neural network',
            'deep learning', 'chatgpt', 'openai', 'automation', 'robotics',
            'algorithm', 'nlp', 'computer vision', 'tensorflow', 'pytorch',
            'gpt', 'llm', 'large language model', 'generative ai', 'anthropic',
            'claude', 'gemini', 'bard', 'hugging face', 'transformer'
        ]
        
        # Thread-safe база данных
        self._db_lock = Lock()
        
        # Инициализация базы данных
        self.init_database()
    
    def init_database(self):
        """Инициализация базы данных"""
        logger.info(f"🗄️ Инициализация базы данных: {self.db_path}")
        
        # Создаем директорию если нужно
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
        
        with self._db_lock:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            
            # Создание таблицы
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS published_news (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    link TEXT UNIQUE NOT NULL,
                    title TEXT,
                    source TEXT,
                    published_date DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Создание индекса для быстрого поиска
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_link ON published_news(link)")
            self.conn.commit()
            
            # Логирование статистики
            count = self.conn.execute("SELECT COUNT(*) FROM published_news").fetchone()[0]
            logger.info(f"📊 База данных готова. Уже сохранено {count} новостей")
    
    @retry_with_backoff(max_attempts=3, base_delay=2.0)
    async def fetch_rss_feed(self, url: str) -> List[Dict]:
        """Асинхронное получение RSS фида с retry"""
        try:
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        raise aiohttp.ClientError(f"HTTP {response.status}")
                    content = await response.text()
                    feed = feedparser.parse(content)
                    return feed.entries
        except Exception as e:
            logger.error(f"Ошибка при получении RSS фида {url}: {e}")
            raise
    
    def is_ai_related(self, title: str, description: str) -> bool:
        """Проверка, относится ли новость к AI"""
        text = (title + " " + description).lower()
        return any(keyword in text for keyword in self.ai_keywords)
    
    def is_already_published(self, link: str) -> bool:
        """Thread-safe проверка, была ли новость уже опубликована"""
        with self._db_lock:
            cursor = self.conn.execute(
                "SELECT 1 FROM published_news WHERE link = ?", (link,)
            )
            result = cursor.fetchone() is not None
            if result:
                logger.info(f"🔄 Дубликат найден, пропускаем: {link[:50]}...")
            else:
                logger.info(f"✅ Новая новость: {link[:50]}...")
            return result
    
    def mark_as_published(self, news: NewsItem):
        """Thread-safe отметка новости как опубликованной"""
        with self._db_lock:
            try:
                self.conn.execute(
                    "INSERT OR IGNORE INTO published_news (link, title, source, published_date) VALUES (?, ?, ?, ?)",
                    (news.link, news.title, news.source, news.published)
                )
                self.conn.commit()
                logger.info(f"💾 Сохранено в БД: {news.title[:50]}...")
            except Exception as e:
                logger.error(f"Ошибка сохранения в БД: {e}")
    
    async def translate_text(self, text: str, quality: str = "medium") -> str:
        """Создание краткого пересказа с контролем расходов"""
        try:
            if len(text) > 3000:
                text = text[:3000] + "..."
            
            if self.client:
                # Оценка токенов
                estimated_input_tokens = len(text) // 4
                estimated_output_tokens = estimated_input_tokens // 2
                
                # Умный выбор модели
                model = self.cost_tracker.suggest_model(quality)
                
                # Переопределяем модель если указана в переменных окружения
                if hasattr(self, 'ai_model') and self.ai_model:
                    model = self.ai_model
                
                # Проверка бюджета
                estimated_cost = self.cost_tracker.estimate_cost(
                    model, estimated_input_tokens, estimated_output_tokens
                )
                
                if not self.cost_tracker.can_afford_request(estimated_cost):
                    logger.warning("🚫 Превышен месячный бюджет, используем бесплатную модель")
                    model = "meta-llama/llama-3.1-8b-instruct:free"
                
                # API запрос с retry
                response = await self._make_api_request(model, text)
                
                # Запись расходов
                if hasattr(response, 'usage') and response.usage:
                    self.cost_tracker.record_usage(
                        model, 
                        response.usage.prompt_tokens,
                        response.usage.completion_tokens
                    )
                
                return response.choices[0].message.content.strip()
            else:
                # Fallback на Google Translator
                from deep_translator import GoogleTranslator
                translator = GoogleTranslator(source='en', target='ru')
                return translator.translate(text)
                
        except Exception as e:
            logger.error(f"Ошибка создания пересказа: {e}")
            # Fallback на Google Translator при ошибке
            try:
                from deep_translator import GoogleTranslator
                translator = GoogleTranslator(source='en', target='ru')
                return translator.translate(text)
            except Exception as fallback_error:
                logger.error(f"Ошибка fallback перевода: {fallback_error}")
                return text  # Возвращаем оригинальный текст при ошибке
    
    @retry_with_backoff(max_attempts=3, base_delay=1.0)
    async def _make_api_request(self, model: str, text: str):
        """API запрос с retry и rate limiting"""
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system", 
                        "content": """Ты опытный технический журналист, специализирующийся на новостях об искусственном интеллекте.

ЗАДАЧА: Создай краткий, информативный пересказ новости на русском языке.

ПРАВИЛА:
1. Пиши простым, понятным языком
2. Выдели главную суть новости в 1-2 предложениях
3. Добавь важные детали (цифры, компании, технологии)
4. Сохраняй технические термины: AI, ML, API, GPU, LLM
5. Объем: 2-4 предложения максимум
6. Стиль: как краткая новостная сводка

ПРИМЕР:
Оригинал: "OpenAI releases GPT-4 Turbo with improved reasoning..."
Пересказ: "Компания OpenAI представила обновленную версию GPT-4 Turbo с улучшенными возможностями логического мышления. Новая модель демонстрирует значительно лучшую производительность в задачах, требующих многоступенчатого анализа."

Создавай пересказ для русскоязычной аудитории."""
                    },
                    {
                        "role": "user", 
                        "content": f"Создай краткий пересказ этой новости:\n\nЗаголовок: {text.split('.')[0] if '.' in text else text[:100]}\nТекст: {text}"
                    }
                ],
                temperature=0.3,
                max_tokens=800
            )
            
            # Rate limiting
            await asyncio.sleep(0.5)
            return response
            
        except Exception as e:
            logger.error(f"Ошибка API запроса к модели {model}: {e}")
            raise
    
    async def parse_news_sources(self) -> List[NewsItem]:
        """Парсинг всех источников новостей"""
        all_news = []
        
        for source_name, rss_url in self.rss_sources.items():
            logger.info(f"Парсинг источника: {source_name}")
            entries = await self.fetch_rss_feed(rss_url)
            
            for entry in entries:
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
                    
                    # Фильтрация по AI тематике
                    if self.is_ai_related(news.title, news.description):
                        # Проверка на дубликаты
                        if not self.is_already_published(news.link):
                            # Проверка актуальности (не старше 24 часов)
                            if published > datetime.now() - timedelta(hours=24):
                                all_news.append(news)
                
                except Exception as e:
                    logger.error(f"Ошибка при обработке новости из {source_name}: {e}")
        
        return all_news
    
    async def translate_news(self, news_list: List[NewsItem]) -> List[NewsItem]:
        """Создание пересказов новостей на русском языке"""
        for news in news_list:
            try:
                logger.info(f"Создаем пересказ новости: {news.title[:50]}...")
                
                # Создание пересказа заголовка (используем исходный заголовок)
                news.translated_title = news.title
                
                # Создание пересказа описания
                full_text = f"{news.title}. {news.description}"
                news.translated_description = await self.translate_text(full_text)
                
                # Небольшая задержка между запросами
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"Ошибка при создании пересказа новости: {e}")
                news.translated_title = news.title
                news.translated_description = news.description
        
        return news_list
    
    def format_message(self, news: NewsItem) -> str:
        """Форматирование сообщения для Telegram"""
        # Очистка HTML тегов из описания
        import html
        
        # Экранирование HTML символов
        title = html.escape(news.translated_title)
        summary = html.escape(news.translated_description)
        
        # Удаление HTML тегов
        import re
        summary = re.sub(r'<[^>]+>', '', summary)
        title = re.sub(r'<[^>]+>', '', title)
        
        # Форматирование сообщения
        message = f"🤖 <b>AI Новости</b>\n\n"
        
        if summary:
            # Основной пересказ
            message += f"{summary}\n\n"
        
        # Информация об источнике
        message += f"📰 <b>Источник:</b> {news.source}\n"
        message += f"🔗 <b><a href='{news.link}'>Читать оригинал статьи</a></b>"
        
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
        """Очистка старых записей из базы данных"""
        with self._db_lock:
            cutoff_date = datetime.now() - timedelta(days=7)
            self.conn.execute(
                "DELETE FROM published_news WHERE created_at < ?",
                (cutoff_date,)
            )
            self.conn.commit()
            logger.info("Очистка старых записей завершена")
    
    def get_statistics(self) -> Dict:
        """Получение статистики работы бота"""
        with self._db_lock:
            cursor = self.conn.execute(
                "SELECT COUNT(*) FROM published_news WHERE created_at > ?",
                (datetime.now() - timedelta(hours=24),)
            )
            last_24h = cursor.fetchone()[0]
            
            cursor = self.conn.execute("SELECT COUNT(*) FROM published_news")
            total = cursor.fetchone()[0]
        
        remaining_budget = self.cost_tracker.get_remaining_budget()
        
        return {
            'total_published': total,
            'last_24h': last_24h,
            'remaining_budget': remaining_budget,
            'current_model': getattr(self, 'ai_model', 'not_set'),
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
            
            # Создание пересказов
            logger.info("🤖 Создаем пересказы новостей...")
            translated_news = await self.translate_news(raw_news)
            
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
                    f"📊 Цикл завершен\n"
                    f"• Опубликовано: {published_count} новостей\n"
                    f"• Время: {cycle_duration:.1f}с\n"
                    f"• Остаток бюджета: ${new_stats['remaining_budget']:.2f}"
                )
            
        except Exception as e:
            logger.error(f"❌ Критическая ошибка в цикле: {e}")
            
            # Отправляем алерт админу
            if self.admin_telegram_id:
                await self._send_admin_alert(f"🚨 КРИТИЧЕСКАЯ ОШИБКА: {str(e)}")
            
            raise
    
    async def start_bot(self):
        """Запуск бота с периодическими проверками и мониторингом"""
        logger.info("🚀 Запуск AI News Bot...")
        
        # Добавляем мониторинг если файл существует
        try:
            from bot_monitoring import add_monitoring_to_bot
            add_monitoring_to_bot(self)
            logger.info("📊 Мониторинг подключен")
        except ImportError:
            logger.warning("⚠️ Модуль мониторинга не найден")
        
        # Отправляем уведомление о запуске админу
        if self.admin_telegram_id:
            await self._send_admin_alert(
                f"🚀 AI News Bot запущен!\n"
                f"• Модель: {self.ai_model}\n"
                f"• Бюджет: ${self.max_monthly_cost}\n"
                f"• Макс новостей: {self.max_news_per_cycle}"
            )
        
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