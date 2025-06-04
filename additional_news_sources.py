# Дополнительные источники новостей и улучшенный парсинг

from typing import Dict, List, Optional
import aiohttp
import asyncio
from datetime import datetime
import feedparser
import json
import re
from bs4 import BeautifulSoup

# ===== РАСШИРЕННЫЙ СПИСОК ИСТОЧНИКОВ =====
class ExtendedNewsSources:
    """Расширенный список источников новостей об AI"""
    
    def __init__(self):
        self.sources = {
            # ===== МЕЖДУНАРОДНЫЕ ИСТОЧНИКИ =====
            "🌍 Основные": {
                "MIT Technology Review AI": "https://www.technologyreview.com/feed/",
                "TechCrunch AI": "https://techcrunch.com/category/artificial-intelligence/feed/",
                "VentureBeat AI": "https://venturebeat.com/ai/feed/",
                "AI News": "https://artificialintelligence-news.com/feed/",
                "The Verge AI": "https://www.theverge.com/ai-artificial-intelligence/rss/index.xml",
                "Ars Technica AI": "https://feeds.arstechnica.com/arstechnica/technology-lab",
                "WIRED AI": "https://www.wired.com/feed/tag/ai/latest/rss",
                "IEEE Spectrum AI": "https://spectrum.ieee.org/rss/topic/artificial-intelligence"
            },
            
            "🏢 Корпоративные блоги": {
                "OpenAI Blog": "https://openai.com/blog/rss.xml",
                "DeepMind Blog": "https://deepmind.com/blog/feed/basic/",
                "Google AI Blog": "https://ai.googleblog.com/feeds/posts/default",
                "Meta AI Blog": "https://ai.facebook.com/blog/feed/",
                "Microsoft AI Blog": "https://blogs.microsoft.com/ai/feed/",
                "NVIDIA AI Blog": "https://blogs.nvidia.com/blog/category/artificial-intelligence/feed/",
                "Anthropic News": "https://www.anthropic.com/news/rss",
                "Hugging Face Blog": "https://huggingface.co/blog/feed.xml"
            },
            
            "📚 Академические": {
                "AI Research": "https://airesearch.com/feed/",
                "Machine Learning Mastery": "https://machinelearningmastery.com/feed/",
                "Towards Data Science": "https://towardsdatascience.com/feed",
                "AI Papers": "https://aipapers.co/feed",
                "Papers with Code": "https://paperswithcode.com/newsletter/rss"
            },
            
            "💼 Бизнес и инновации": {
                "CB Insights AI": "https://www.cbinsights.com/research/artificial-intelligence/rss",
                "McKinsey AI": "https://www.mckinsey.com/~/media/McKinsey/Featured%20Insights/Artificial%20Intelligence/rss.ashx",
                "Forbes AI": "https://www.forbes.com/ai/feed/",
                "Harvard Business Review AI": "https://hbr.org/topic/artificial-intelligence.rss"
            },
            
            # ===== РОССИЙСКИЕ ИСТОЧНИКИ =====
            "🇷🇺 Российские": {
                "Хабр AI": "https://habr.com/ru/rss/hub/artificial_intelligence/",
                "Хабр ML": "https://habr.com/ru/rss/hub/machine_learning/",
                "Хабр Data Science": "https://habr.com/ru/rss/hub/data_science/",
                "CNews AI": "https://www.cnews.ru/inc/rss/news_ai.xml",
                "3DNews AI": "https://3dnews.ru/news/ai/rss/",
                "Tproger AI": "https://tproger.ru/tag/ai/feed/",
                "VC.ru AI": "https://vc.ru/tag/ai/rss",
                "Skillfactory Blog": "https://blog.skillfactory.ru/tag/iskusstvennyj-intellekt/feed/"
            },
            
            "🎓 Образовательные": {
                "AI Education": "https://ai-education.ru/feed/",
                "Machine Learning Russia": "https://mlrussia.ru/feed/",
                "Data Science Russia": "https://datasciencerussia.ru/feed/"
            }
        }
    
    def get_all_sources(self) -> Dict[str, str]:
        """Получение всех источников в плоском виде"""
        all_sources = {}
        for category, sources in self.sources.items():
            all_sources.update(sources)
        return all_sources
    
    def get_sources_by_category(self, category: str) -> Dict[str, str]:
        """Получение источников по категории"""
        return self.sources.get(category, {})

# ===== УМНЫЙ ПАРСЕР С МАШИННЫМ ОБУЧЕНИЕМ =====
class SmartNewsParser:
    """Умный парсер новостей с использованием ML"""
    
    def __init__(self):
        self.ai_keywords = {
            # Высокий приоритет
            "high": [
                "artificial intelligence", "machine learning", "deep learning",
                "neural network", "transformer", "gpt", "llm", "ai model",
                "искусственный интеллект", "машинное обучение", "нейросеть",
                "chatgpt", "claude", "gemini", "copilot"
            ],
            # Средний приоритет  
            "medium": [
                "automation", "computer vision", "nlp", "natural language",
                "робот", "автоматизация", "алгоритм", "данные", "аналитика",
                "prediction", "classification", "regression", "clustering"
            ],
            # Низкий приоритет
            "low": [
                "technology", "innovation", "digital", "smart", "intelligent",
                "технология", "инновация", "цифровой", "умный"
            ]
        }
        
        # Исключающие слова (не AI новости)
        self.exclude_keywords = [
            "crypto", "bitcoin", "blockchain", "web3", "nft",
            "crypto", "биткоин", "блокчейн", "криптовалюта",
            "game", "gaming", "mobile", "phone", "smartphone"
        ]
    
    def calculate_ai_relevance_score(self, title: str, description: str) -> float:
        """Вычисление релевантности новости к AI"""
        text = f"{title} {description}".lower()
        score = 0.0
        
        # Положительные баллы за AI ключевые слова
        for keyword in self.ai_keywords["high"]:
            if keyword in text:
                score += 3.0
        
        for keyword in self.ai_keywords["medium"]:
            if keyword in text:
                score += 1.5
        
        for keyword in self.ai_keywords["low"]:
            if keyword in text:
                score += 0.5
        
        # Штрафы за исключающие слова
        for keyword in self.exclude_keywords:
            if keyword in text:
                score -= 2.0
        
        return max(0.0, score)
    
    def is_high_quality_news(self, news_item: dict) -> bool:
        """Проверка качества новости"""
        title = news_item.get('title', '')
        description = news_item.get('description', '')
        
        # Минимальная длина
        if len(title) < 10 or len(description) < 50:
            return False
        
        # Проверка на спам
        spam_indicators = ['click here', 'buy now', 'limited time', 'URGENT']
        text = f"{title} {description}".lower()
        
        for indicator in spam_indicators:
            if indicator.lower() in text:
                return False
        
        # AI релевантность
        relevance_score = self.calculate_ai_relevance_score(title, description)
        return relevance_score >= 2.0
    
    async def enhanced_rss_parsing(self, url: str, source_name: str) -> List[dict]:
        """Улучшенный парсинг RSS с дополнительной обработкой"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=30) as response:
                    content = await response.text()
                    
            feed = feedparser.parse(content)
            news_items = []
            
            for entry in feed.entries[:20]:  # Ограничиваем количество
                try:
                    # Основная информация
                    news_item = {
                        'title': entry.get('title', ''),
                        'description': self._clean_description(entry.get('summary', '')),
                        'link': entry.get('link', ''),
                        'published': self._parse_date(entry.get('published')),
                        'source': source_name,
                        'author': entry.get('author', ''),
                        'tags': self._extract_tags(entry)
                    }
                    
                    # Проверка качества
                    if self.is_high_quality_news(news_item):
                        # Дополнительная информация
                        news_item['relevance_score'] = self.calculate_ai_relevance_score(
                            news_item['title'], 
                            news_item['description']
                        )
                        
                        # Извлечение изображений
                        news_item['image_url'] = self._extract_image_url(entry)
                        
                        news_items.append(news_item)
                        
                except Exception as e:
                    continue
            
            return news_items
            
        except Exception as e:
            print(f"Ошибка парсинга {source_name}: {e}")
            return []
    
    def _clean_description(self, description: str) -> str:
        """Очистка описания от HTML и лишних символов"""
        if not description:
            return ""
        
        # Удаляем HTML теги
        soup = BeautifulSoup(description, 'html.parser')
        text = soup.get_text()
        
        # Удаляем лишние пробелы и переносы
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Ограничиваем длину
        if len(text) > 500:
            text = text[:500] + "..."
        
        return text
    
    def _parse_date(self, date_str: str) -> datetime:
        """Парсинг даты из различных форматов"""
        if not date_str:
            return datetime.now()
        
        try:
            # Пробуем несколько форматов
            formats = [
                '%a, %d %b %Y %H:%M:%S %z',
                '%a, %d %b %Y %H:%M:%S GMT',
                '%Y-%m-%dT%H:%M:%S%z',
                '%Y-%m-%d %H:%M:%S'
            ]
            
            for fmt in formats:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
            
            return datetime.now()
        except:
            return datetime.now()
    
    def _extract_tags(self, entry) -> List[str]:
        """Извлечение тегов из записи"""
        tags = []
        
        if hasattr(entry, 'tags'):
            for tag in entry.tags:
                if hasattr(tag, 'term'):
                    tags.append(tag.term.lower())
        
        return tags[:5]  # Ограничиваем количество тегов
    
    def _extract_image_url(self, entry) -> Optional[str]:
        """Извлечение URL изображения"""
        try:
            # Проверяем различные поля
            if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
                return entry.media_thumbnail[0]['url']
            
            if hasattr(entry, 'media_content') and entry.media_content:
                return entry.media_content[0]['url']
            
            # Ищем в description
            if hasattr(entry, 'summary'):
                soup = BeautifulSoup(entry.summary, 'html.parser')
                img_tag = soup.find('img')
                if img_tag and img_tag.get('src'):
                    return img_tag['src']
            
            return None
        except:
            return None

# ===== СОЦИАЛЬНЫЕ СЕТИ И ДОПОЛНИТЕЛЬНЫЕ ИСТОЧНИКИ =====
class SocialMediaParser:
    """Парсер социальных сетей для AI новостей"""
    
    def __init__(self):
        self.twitter_accounts = [
            "OpenAI", "DeepMind", "AnthropicAI", "huggingface",
            "GoogleAI", "MetaAI", "nvidia", "Microsoft"
        ]
        
        self.reddit_subreddits = [
            "MachineLearning", "artificial", "deeplearning",
            "ChatGPT", "LocalLLaMA", "singularity"
        ]
    
    async def parse_twitter_rss(self, account: str) -> List[dict]:
        """Парсинг Twitter RSS (если доступен)"""
        # Здесь можно использовать сторонние сервисы для получения RSS из Twitter
        # Например: https://rss.app или https://twitrss.me
        rss_url = f"https://twitrss.me/twitter_user_to_rss/?user={account}"
        
        parser = SmartNewsParser()
        return await parser.enhanced_rss_parsing(rss_url, f"Twitter @{account}")
    
    async def parse_reddit_rss(self, subreddit: str) -> List[dict]:
        """Парсинг Reddit RSS"""
        rss_url = f"https://www.reddit.com/r/{subreddit}/hot/.rss"
        
        parser = SmartNewsParser()
        return await parser.enhanced_rss_parsing(rss_url, f"Reddit r/{subreddit}")

# ===== ИНТЕГРАЦИЯ С ВНЕШНИМИ API =====
class NewsAggregator:
    """Агрегатор новостей из различных API"""
    
    def __init__(self, newsapi_key: Optional[str] = None):
        self.newsapi_key = newsapi_key
        self.sources = ExtendedNewsSources()
        self.parser = SmartNewsParser()
    
    async def fetch_from_newsapi(self, query: str = "artificial intelligence") -> List[dict]:
        """Получение новостей через News API"""
        if not self.newsapi_key:
            return []
        
        url = "https://newsapi.org/v2/everything"
        params = {
            'q': query,
            'apiKey': self.newsapi_key,
            'language': 'en',
            'sortBy': 'publishedAt',
            'pageSize': 20
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    data = await response.json()
                    
                    news_items = []
                    for article in data.get('articles', []):
                        news_item = {
                            'title': article.get('title', ''),
                            'description': article.get('description', ''),
                            'link': article.get('url', ''),
                            'published': datetime.fromisoformat(
                                article.get('publishedAt', '').replace('Z', '+00:00')
                            ),
                            'source': article.get('source', {}).get('name', 'News API'),
                            'image_url': article.get('urlToImage'),
                            'relevance_score': self.parser.calculate_ai_relevance_score(
                                article.get('title', ''),
                                article.get('description', '')
                            )
                        }
                        
                        if self.parser.is_high_quality_news(news_item):
                            news_items.append(news_item)
                    
                    return news_items
        except Exception as e:
            print(f"Ошибка News API: {e}")
            return []
    
    async def get_all_news(self) -> List[dict]:
        """Получение новостей из всех источников"""
        all_sources = self.sources.get_all_sources()
        tasks = []
        
        # RSS источники
        for source_name, url in all_sources.items():
            task = self.parser.enhanced_rss_parsing(url, source_name)
            tasks.append(task)
        
        # News API (если доступен)
        if self.newsapi_key:
            tasks.append(self.fetch_from_newsapi())
        
        # Выполняем все задачи параллельно
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Объединяем результаты
        all_news = []
        for result in results:
            if isinstance(result, list):
                all_news.extend(result)
        
        # Сортируем по релевантности и дате
        all_news.sort(key=lambda x: (x.get('relevance_score', 0), x.get('published', datetime.min)), reverse=True)
        
        return all_news[:50]  # Возвращаем топ-50 новостей 