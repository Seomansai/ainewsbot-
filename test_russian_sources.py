# Тест российских источников AI News Bot
import asyncio
import feedparser
import aiohttp
from datetime import datetime

# Российские источники для тестирования
RUSSIAN_SOURCES = {
    'Хабр AI': 'https://habr.com/ru/rss/hub/artificial_intelligence/',
    'Хабр ML': 'https://habr.com/ru/rss/hub/machine_learning/',
    'VC.ru Технологии': 'https://vc.ru/rss/tech',
    'РБК Технологии': 'https://rssexport.rbc.ru/rbcnews/news/20/full.rss',
    'CNews': 'https://www.cnews.ru/inc/rss/news.xml',
    '3DNews': 'https://3dnews.ru/news/rss/',
}

# Ключевые слова для ИИ на русском
AI_KEYWORDS_RU = [
    'ии', 'искусственный интеллект', 'машинное обучение', 'нейронная сеть',
    'нейросеть', 'чатгпт', 'автоматизация', 'алгоритм', 'нлп', 
    'компьютерное зрение', 'языковая модель', 'генеративный ии',
    'openai', 'нейронка', 'ml', 'dl', 'data science', 'датасайенс',
    'yandex gpt', 'яндекс гпт', 'сбер', 'gigachat', 'гигачат'
]

def detect_language(text):
    """Определение языка текста"""
    cyrillic_chars = sum(1 for char in text if 'а' <= char.lower() <= 'я')
    latin_chars = sum(1 for char in text if 'a' <= char.lower() <= 'z')
    return 'ru' if cyrillic_chars > latin_chars else 'en'

def is_ai_related_ru(title, description):
    """Проверка релевантности к ИИ для русского текста"""
    text = (title + " " + description).lower()
    return any(keyword in text for keyword in AI_KEYWORDS_RU)

async def fetch_rss_feed(url):
    """Получение RSS фида"""
    try:
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:
                if response.status == 200:
                    content = await response.text()
                    feed = feedparser.parse(content)
                    return feed.entries
                else:
                    print(f"❌ HTTP {response.status} для {url}")
                    return []
    except Exception as e:
        print(f"❌ Ошибка при получении {url}: {e}")
        return []

async def test_russian_sources():
    """Тестирование российских источников"""
    print("🇷🇺 Тестирование российских источников AI новостей\n")
    
    total_news = 0
    ai_news = 0
    
    for source_name, rss_url in RUSSIAN_SOURCES.items():
        print(f"📡 Тестирование: {source_name}")
        print(f"   URL: {rss_url}")
        
        entries = await fetch_rss_feed(rss_url)
        
        if not entries:
            print(f"   ❌ Нет данных\n")
            continue
            
        print(f"   📰 Найдено новостей: {len(entries)}")
        
        relevant_entries = []
        for entry in entries[:10]:  # Проверяем первые 10 новостей
            title = entry.get('title', '')
            description = entry.get('summary', '')
            
            # Определяем язык
            language = detect_language(title + " " + description)
            
            # Проверяем релевантность к ИИ
            if is_ai_related_ru(title, description):
                relevant_entries.append({
                    'title': title,
                    'description': description[:100] + "...",
                    'language': language,
                    'link': entry.get('link', '')
                })
        
        total_news += len(entries)
        ai_news += len(relevant_entries)
        
        print(f"   🤖 AI новостей: {len(relevant_entries)}")
        
        # Показываем примеры
        for i, news in enumerate(relevant_entries[:2], 1):
            print(f"   {i}. {news['language'].upper()}: {news['title'][:60]}...")
        
        print()
    
    print(f"📊 Итого:")
    print(f"   Всего новостей: {total_news}")
    print(f"   AI новостей: {ai_news}")
    print(f"   Процент релевантности: {(ai_news/max(1,total_news)*100):.1f}%")

if __name__ == "__main__":
    asyncio.run(test_russian_sources()) 