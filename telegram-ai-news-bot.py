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
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.channel_id = os.getenv('TELEGRAM_CHANNEL_ID')
        self.openrouter_key = os.getenv('OPENROUTER_API_KEY')
        
        if not self.bot_token or not self.channel_id:
            raise ValueError("Необходимо установить TELEGRAM_BOT_TOKEN и TELEGRAM_CHANNEL_ID")
        
        self.bot = Bot(token=self.bot_token)
        
        # Инициализация OpenRouter API
        if self.openrouter_key:
            self.client = OpenAI(
                api_key=self.openrouter_key,
                base_url="https://openrouter.ai/api/v1"
            )
        else:
            logger.warning("OPENROUTER_API_KEY не установлен, используется fallback переводчик")
            self.client = None
        
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
        """Инициализация SQLite базы данных"""
        self.conn = sqlite3.connect('ai_news.db', check_same_thread=False)
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS published_news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                link TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                source TEXT NOT NULL,
                published_date DATETIME NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.conn.commit()
    
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
        return cursor.fetchone() is not None
    
    def mark_as_published(self, news: NewsItem):
        """Отметить новость как опубликованную"""
        self.conn.execute(
            "INSERT OR IGNORE INTO published_news (link, title, source, published_date) VALUES (?, ?, ?, ?)",
            (news.link, news.title, news.source, news.published)
        )
        self.conn.commit()
    
    def translate_text(self, text: str) -> str:
        """Перевод текста на русский язык с помощью OpenRouter"""
        try:
            if len(text) > 3000:
                text = text[:3000] + "..."
            
            if self.client:
                # Используем OpenRouter для перевода (можно выбрать разные модели)
                response = self.client.chat.completions.create(
                    model="meta-llama/llama-3.1-8b-instruct:free",  # Бесплатная версия для экономии
                    messages=[
                        {
                            "role": "system", 
                            "content": "Ты профессиональный переводчик технических текстов. Переведи текст с английского на русский язык, сохраняя все технические термины, аббревиатуры и смысл. Делай перевод естественным и читабельным для русскоязычной аудитории. Сохраняй стиль оригинала."
                        },
                        {
                            "role": "user", 
                            "content": f"Переведи этот текст на русский:\n\n{text}"
                        }
                    ],
                    temperature=0.2,
                    max_tokens=1500
                )
                return response.choices[0].message.content.strip()
            else:
                # Fallback на Google Translator
                from deep_translator import GoogleTranslator
                translator = GoogleTranslator(source='en', target='ru')
                return translator.translate(text)
                
        except Exception as e:
            logger.error(f"Ошибка перевода через OpenRouter: {e}")
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
        """Перевод новостей на русский язык"""
        for news in news_list:
            try:
                logger.info(f"Переводим новость: {news.title[:50]}...")
                
                # Перевод заголовка
                news.translated_title = self.translate_text(news.title)
                
                # Перевод описания
                news.translated_description = self.translate_text(news.description)
                
                # Небольшая задержка между переводами
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Ошибка при переводе новости: {e}")
                news.translated_title = news.title
                news.translated_description = news.description
        
        return news_list
    
    def format_message(self, news: NewsItem) -> str:
        """Форматирование сообщения для Telegram"""
        # Очистка HTML тегов из описания
        import html
        
        # Экранирование HTML символов
        title = html.escape(news.translated_title)
        description = html.escape(news.translated_description)
        
        # Удаление HTML тегов
        import re
        description = re.sub(r'<[^>]+>', '', description)
        title = re.sub(r'<[^>]+>', '', title)
        
        message = f"🤖 <b>{title}</b>\n\n"
        
        if description:
            # Ограничиваем описание до 800 символов
            if len(description) > 800:
                description = description[:800] + "..."
            message += f"{description}\n\n"
        
        message += f"📱 Источник: {news.source}\n"
        message += f"🔗 <a href='{news.link}'>Читать полностью</a>"
        
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
        """Основной цикл обработки новостей"""
        try:
            logger.info("Начинаем цикл обработки новостей...")
            
            # 1. Парсинг новостей
            news_list = await self.parse_news_sources()
            logger.info(f"Найдено {len(news_list)} новых AI новостей")
            
            if not news_list:
                logger.info("Новых новостей не найдено")
                return
            
            # 2. Перевод новостей
            translated_news = await self.translate_news(news_list)
            
            # 3. Публикация новостей
            await self.publish_news(translated_news)
            
            # 4. Очистка старых записей
            self.cleanup_old_records()
            
            logger.info(f"Цикл завершен. Опубликовано {len(translated_news)} новостей")
            
        except Exception as e:
            logger.error(f"Ошибка в основном цикле: {e}")
    
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