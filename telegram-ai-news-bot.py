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
from dataclasses import dataclass
from threading import Thread
from http.server import HTTPServer, SimpleHTTPRequestHandler

import aiohttp
from openai import OpenAI
from telegram import Bot
from telegram.error import TelegramError

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
        
        # Путь к базе данных (для постоянного хранения на сервере)
        self.db_path = os.getenv('DATABASE_PATH', 'ai_news.db')
        
        if not self.bot_token or not self.channel_id:
            raise ValueError("Необходимо установить TELEGRAM_BOT_TOKEN и TELEGRAM_CHANNEL_ID")
        
        self.bot = Bot(token=self.bot_token)
        
        # Инициализация OpenRouter клиента
        self.client = None
        if self.openrouter_api_key:
            self.client = OpenAI(
                api_key=self.openrouter_api_key,
                base_url="https://openrouter.ai/api/v1"
            )
            logger.info("✅ OpenRouter клиент инициализирован для создания пересказов")
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
        
        # Инициализация базы данных
        self.init_database()
    
    def init_database(self):
        """Инициализация базы данных"""
        logger.info(f"🗄️ Инициализация базы данных: {self.db_path}")
        
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
    
    async def fetch_rss_feed(self, url: str) -> List[Dict]:
        """Асинхронное получение RSS фида"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=30) as response:
                    content = await response.text()
                    feed = feedparser.parse(content)
                    return feed.entries
        except Exception as e:
            logger.error(f"Ошибка при получении RSS фида {url}: {e}")
            return []
    
    def is_ai_related(self, title: str, description: str) -> bool:
        """Проверка, относится ли новость к AI"""
        text = (title + " " + description).lower()
        return any(keyword in text for keyword in self.ai_keywords)
    
    def is_already_published(self, link: str) -> bool:
        """Проверка, была ли новость уже опубликована"""
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
        """Отметить новость как опубликованную"""
        self.conn.execute(
            "INSERT OR IGNORE INTO published_news (link, title, source, published_date) VALUES (?, ?, ?, ?)",
            (news.link, news.title, news.source, news.published)
        )
        self.conn.commit()
        logger.info(f"💾 Сохранено в БД: {news.title[:50]}...")
    
    def translate_text(self, text: str) -> str:
        """Создание краткого пересказа новости на русском языке"""
        try:
            if len(text) > 3000:
                text = text[:3000] + "..."
            
            if self.client:
                # Используем OpenRouter для создания пересказа
                response = self.client.chat.completions.create(
                    model="anthropic/claude-3.5-sonnet",  # Лучшая модель для качественного пересказа
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
                return response.choices[0].message.content.strip()
            else:
                # Fallback на Google Translator
                from deep_translator import GoogleTranslator
                translator = GoogleTranslator(source='en', target='ru')
                return translator.translate(text)
                
        except Exception as e:
            logger.error(f"Ошибка создания пересказа через OpenRouter: {e}")
            # Fallback на Google Translator при ошибке
            try:
                from deep_translator import GoogleTranslator
                translator = GoogleTranslator(source='en', target='ru')
                return translator.translate(text)
            except:
                return text  # Возвращаем оригинальный текст при ошибке
    
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
                news.translated_description = self.translate_text(full_text)
                
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
    
    async def publish_news(self, news_list: List[NewsItem]):
        """Публикация новостей в Telegram канал"""
        for news in news_list:
            try:
                message = self.format_message(news)
                
                await self.bot.send_message(
                    chat_id=self.channel_id,
                    text=message,
                    parse_mode='HTML',
                    disable_web_page_preview=False
                )
                
                # Отмечаем как опубликованную
                self.mark_as_published(news)
                
                logger.info(f"Опубликована новость: {news.title[:50]}...")
                
                # Задержка между публикациями
                await asyncio.sleep(3)
                
            except TelegramError as e:
                logger.error(f"Ошибка при публикации в Telegram: {e}")
            except Exception as e:
                logger.error(f"Общая ошибка при публикации: {e}")
    
    def cleanup_old_records(self):
        """Очистка старых записей из базы данных"""
        cutoff_date = datetime.now() - timedelta(days=7)
        self.conn.execute(
            "DELETE FROM published_news WHERE created_at < ?",
            (cutoff_date,)
        )
        self.conn.commit()
        logger.info("Очистка старых записей завершена")
    
    def get_statistics(self) -> Dict:
        """Получение статистики работы бота"""
        cursor = self.conn.execute(
            "SELECT COUNT(*) FROM published_news WHERE created_at > ?",
            (datetime.now() - timedelta(hours=24),)
        )
        last_24h = cursor.fetchone()[0]
        
        cursor = self.conn.execute("SELECT COUNT(*) FROM published_news")
        total = cursor.fetchone()[0]
        
        return {
            'total_published': total,
            'last_24h': last_24h,
            'status': 'active'
        }
    
    async def run_news_cycle(self):
        """Основной цикл парсинга и публикации новостей"""
        try:
            # Логирование состояния базы данных
            total_count = self.get_statistics()['total_published']
            logger.info(f"📊 Запуск цикла парсинга. В БД уже {total_count} новостей")
            
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
            logger.info(f"📢 Публикуем {len(translated_news)} новостей...")
            await self.publish_news(translated_news)
            
            # Финальная статистика
            new_total = self.get_statistics()['total_published']
            published_count = new_total - total_count
            logger.info(f"✅ Цикл завершен. Опубликовано: {published_count} новых новостей")
            
        except Exception as e:
            logger.error(f"❌ Ошибка в основном цикле: {e}")
    
    async def start_bot(self):
        """Запуск бота с периодическими проверками"""
        logger.info("Запуск AI News Bot...")
        
        while True:
            try:
                await self.run_news_cycle()
                
                # Ожидание 2 часа перед следующей проверкой
                logger.info("Ожидание 2 часа до следующей проверки...")
                await asyncio.sleep(7200)  # 2 часа
                
            except KeyboardInterrupt:
                logger.info("Получен сигнал остановки")
                break
            except Exception as e:
                logger.error(f"Критическая ошибка: {e}")
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