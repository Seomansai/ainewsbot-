# Telegram AI News Bot
# Автоматический парсинг и публикация AI новостей

import asyncio
import sqlite3
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
        self.newsapi_key = os.getenv('NEWSAPI_KEY')
        
        # Основные настройки
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
        
        # Проверка NewsAPI ключа
        if not self.newsapi_key:
            raise ValueError("Необходимо установить NEWSAPI_KEY для получения новостей")
        
        logger.info("🆓 БЕСПЛАТНЫЙ NewsAPI режим активирован!")
        logger.info("💰 Экономия: $5/месяц (без Claude)")
        logger.info("📈 Прямая обработка NewsAPI данных")
        
        # ===== NEWS API КОНФИГУРАЦИЯ =====
        
        # Расширенные ключевые слова для поиска AI новостей
        self.ai_keywords = [
            # Основные AI термины
            "искусственный интеллект",
            "машинное обучение", 
            "нейронная сеть",
            "нейросеть",
            "глубокое обучение",
            "ИИ технологии",
            "AI разработка",
            "компьютерное зрение",
            "обработка языка",
            
            # Популярные AI продукты
            "ChatGPT",
            "GPT-4",
            "Yandex GPT",
            "GigaChat",
            "Claude",
            "Gemini",
            "Kandinsky",
            "Midjourney",
            "DALL-E",
            
            # Российские AI
            "Сбер AI",
            "Яндекс ИИ",
            "МТС AI",
            "Тинькофф AI",
            "VK AI",
            "Huawei AI",
            
            # Бизнес и стартапы
            "AI стартап",
            "ИИ стартап",
            "AI компания",
            "технологии будущего",
            "цифровая трансформация",
            "автоматизация процессов",
            
            # Технические направления
            "робототехника",
            "беспилотники",
            "умные технологии",
            "интернет вещей",
            "большие данные",
            "алгоритмы",
            "data science",
            
            # Применение AI
            "медицинский ИИ",
            "финтех ИИ",
            "образовательный ИИ",
            "умный город",
            "автопилот",
            "голосовые помощники"
        ]
        
        # Группы ключевых слов для ротации
        self.keyword_groups = [
            # Группа 1: Основные AI термины
            ["искусственный интеллект", "машинное обучение", "нейронная сеть"],
            # Группа 2: Популярные продукты
            ["ChatGPT", "Yandex GPT", "GigaChat"],
            # Группа 3: Российские компании
            ["Сбер AI", "Яндекс ИИ", "VK AI"],
            # Группа 4: Применение
            ["робототехника", "автопилот", "умные технологии"],
            # Группа 5: Стартапы и бизнес
            ["AI стартап", "цифровая трансформация", "технологии будущего"]
        ]
        
        # Русские источники для NewsAPI
        self.russian_sources = [
            "rbc.ru",
            "lenta.ru", 
            "ria.ru",
            "tass.ru",
            "rt.com",
            "gazeta.ru",
            "kommersant.ru",
            "vedomosti.ru",
            "forbes.ru",
            "cnews.ru"
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
    async def fetch_news_from_api(self, keyword: str, page_size: int = 20) -> List[Dict]:
        """Получение новостей через NewsAPI.org"""
        try:
            url = "https://newsapi.org/v2/everything"
            
            # Параметры запроса
            params = {
                'apiKey': self.newsapi_key,
                'q': keyword,
                'language': 'ru',  # Только русские новости
                'sortBy': 'publishedAt',  # Сортировка по дате
                'pageSize': page_size,
                'from': (datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%d'),  # За последние 24 часа
                'domains': ','.join(self.russian_sources)  # Только русские источники
            }
            
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        articles = data.get('articles', [])
                        logger.info(f"✅ NewsAPI: найдено {len(articles)} новостей по '{keyword}'")
                        return articles
                    elif response.status == 429:
                        logger.warning("⚠️ NewsAPI rate limit превышен")
                        return []
                    else:
                        logger.error(f"❌ NewsAPI ошибка: HTTP {response.status}")
                        return []
                        
        except Exception as e:
            logger.error(f"Ошибка при получении новостей через API: {e}")
            raise
    
    async def parse_news_sources(self) -> List[NewsItem]:
        """Умный парсинг новостей через NewsAPI с ротацией ключевых слов"""
        all_news = []
        
        # Умная ротация: берем одну группу ключевых слов по очереди
        import time
        current_hour = datetime.now().hour
        group_index = current_hour % len(self.keyword_groups)  # Меняем группу каждый час
        
        active_group = self.keyword_groups[group_index]
        logger.info(f"🎯 Активная группа ключевых слов #{group_index + 1}: {active_group}")
        
        # Также добавляем несколько основных ключевых слов
        priority_keywords = ["искусственный интеллект", "ChatGPT", "нейросеть"]
        all_active_keywords = list(set(active_group + priority_keywords))  # Убираем дубликаты
        
        for keyword in all_active_keywords:
            try:
                logger.info(f"🔍 Поиск новостей по '{keyword}' через NewsAPI...")
                articles = await self.fetch_news_from_api(keyword, page_size=15)  # Увеличиваем размер
                
                if not articles:
                    logger.info(f"❌ Нет новостей по '{keyword}'")
                    continue
                
                logger.info(f"📰 Найдено {len(articles)} статей по '{keyword}'")
                
                for article in articles:
                    try:
                        # Парсинг даты публикации
                        published_str = article.get('publishedAt', '')
                        if published_str:
                            # Парсинг ISO формата: 2024-01-15T10:30:00Z
                            published = datetime.fromisoformat(published_str.replace('Z', '+00:00')).replace(tzinfo=None)
                        else:
                            published = datetime.now()
                        
                        # Определение источника
                        source_name = article.get('source', {}).get('name', 'Неизвестный источник')
                        
                        # Создание объекта новости
                        news = NewsItem(
                            title=article.get('title', ''),
                            description=article.get('description', ''),
                            link=article.get('url', ''),
                            published=published,
                            source=source_name
                        )
                        
                        # Проверка на дубликаты
                        if not self.is_already_published(news.link, news.title):
                            # Проверка актуальности (не старше 24 часов)
                            if published > datetime.now() - timedelta(hours=24):
                                all_news.append(news)
                                logger.info(f"✅ AI новость: {news.title[:50]}...")
                    
                    except Exception as e:
                        logger.error(f"Ошибка при обработке статьи: {e}")
                        continue
                
                # Задержка между запросами (NewsAPI лимиты)
                await asyncio.sleep(1)  # Уменьшаем задержку для быстрой работы
                
            except Exception as e:
                logger.error(f"Ошибка при обработке ключевого слова '{keyword}': {e}")
        
        # Улучшенная дедупликация
        unique_news = self.deduplicate_news(all_news)
        
        logger.info(f"📊 NewsAPI парсинг завершен: {len(unique_news)} уникальных новостей из {len(all_news)}")
        logger.info(f"🎯 Использованы ключевые слова: {', '.join(all_active_keywords)}")
        return unique_news
    
    def deduplicate_news(self, news_list: List[NewsItem]) -> List[NewsItem]:
        """Умная дедупликация новостей"""
        seen_links = set()
        seen_titles = set()
        unique_news = []
        
        for news in news_list:
            # Проверка по ссылке
            if news.link in seen_links:
                continue
            
            # Проверка по заголовку (первые 60 символов)
            title_key = news.title.lower()[:60].strip()
            if title_key in seen_titles:
                continue
            
            seen_links.add(news.link)
            seen_titles.add(title_key)
            unique_news.append(news)
        
        return unique_news
    
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
    
    async def process_news(self, news_list: List[NewsItem]) -> List[NewsItem]:
        """Простая обработка новостей из NewsAPI (без AI)"""
        for news in news_list:
            try:
                logger.info(f"🇷🇺 Обработка новости: {news.title[:50]}...")
                
                # Очистка заголовка
                news.translated_title = self.clean_html(news.title)
                
                # Создаем краткий пересказ из title + description
                title_clean = self.clean_html(news.title)
                desc_clean = self.clean_html(news.description) if news.description else ""
                
                # Формируем итоговый текст
                if desc_clean and len(desc_clean) > 10:
                    # Берем описание если оно есть и информативное
                    news.translated_description = desc_clean[:200] + ("..." if len(desc_clean) > 200 else "")
                else:
                    # Иначе используем заголовок
                    news.translated_description = title_clean
                
                # Небольшая задержка
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Ошибка при обработке новости: {e}")
                news.translated_title = self.clean_html(news.title)
                news.translated_description = self.clean_html(news.description) if news.description else self.clean_html(news.title)
        
        return news_list
    
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
        """Форматирование сообщения для Telegram в новом стиле"""
        import html
        
        # Используем пересказ от Claude или очищенное описание
        content = news.translated_description if news.translated_description else news.description
        content = html.escape(content.strip())
        
        # Флаг России для всех русскоязычных источников
        source_flag = "🇷🇺"
        
        # Простой формат: пересказ + источник
        message = f"{content}\n\n{source_flag} <b>Источник:</b> {news.source}"
        
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
        
        return {
            'total_published': total,
            'last_24h': last_24h,
            'mode': 'free_newsapi',
            'status': 'active'
        }
    
    async def run_news_cycle(self):
        """Основной цикл парсинга и публикации новостей с улучшенной обработкой ошибок"""
        cycle_start_time = time.time()
        
        try:
            # Логирование состояния
            stats = self.get_statistics()
            current_hour = datetime.now().hour
            group_index = current_hour % len(self.keyword_groups)
            active_group = self.keyword_groups[group_index]
            
            logger.info(f"📊 Запуск БЕСПЛАТНОГО цикла. БД: {stats['total_published']} новостей")
            logger.info(f"🎯 Активная группа ключевых слов: {', '.join(active_group)}")
            
            # Парсинг новостей через News API
            logger.info("🔍 Умный поиск AI новостей через NewsAPI.org...")
            raw_news = await self.parse_news_sources()
            logger.info(f"📰 Найдено {len(raw_news)} новостей через умный поиск")
            
            if not raw_news:
                logger.info("❌ Новые AI новости не найдены")
                return
            
            # НОВОЕ: Резервирование новостей перед обработкой
            logger.info("🔒 Резервируем новости для обработки...")
            reserved_news = self.reserve_news_for_processing(raw_news)
            
            if not reserved_news:
                logger.info("❌ Все новости уже зарезервированы или опубликованы")
                return
            
            # Простая обработка NewsAPI данных
            logger.info(f"⚡ Обрабатываем {len(reserved_news)} NewsAPI новостей...")
            processed_news = await self.process_news(reserved_news)
            
            # Публикация
            logger.info(f"📢 Публикуем до {self.max_news_per_cycle} новостей...")
            published_count = await self.publish_news(processed_news)
            
            # Финальная статистика
            cycle_duration = time.time() - cycle_start_time
            new_stats = self.get_statistics()
            
            logger.info(f"✅ БЕСПЛАТНЫЙ цикл завершен за {cycle_duration:.1f}с. Опубликовано: {published_count} новостей")
            
            # Отправляем статистику админу
            if self.admin_telegram_id and published_count > 0:
                await self._send_admin_alert(
                    f"📊 БЕСПЛАТНЫЙ NewsAPI цикл завершен\n"
                    f"• Найдено новостей: {len(raw_news)}\n"
                    f"• Зарезервировано: {len(reserved_news)}\n"
                    f"• Опубликовано: {published_count}\n"
                    f"• Время: {cycle_duration:.1f}с\n"
                    f"💰 Экономия: $5/месяц"
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
                f"• Режим: БЕСПЛАТНЫЙ NewsAPI.org\n"
                f"• Обработка: Простая очистка данных\n"
                f"• Экономия: $5/месяц (без Claude)\n"
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