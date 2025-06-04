# Предложения по улучшению производительности AI News Bot

import asyncio
from concurrent.futures import ThreadPoolExecutor
import aiohttp
from dataclasses import dataclass
from typing import List, Dict, Optional
import logging

# ===== 1. ПАРАЛЛЕЛЬНАЯ ОБРАБОТКА RSS =====
class AsyncRSSProcessor:
    """Параллельная обработка RSS источников"""
    
    def __init__(self, max_concurrent: int = 10):
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
    
    async def fetch_all_sources(self, sources: Dict[str, str]) -> List[NewsItem]:
        """Параллельная загрузка всех RSS источников"""
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            connector=aiohttp.TCPConnector(limit=self.max_concurrent)
        ) as session:
            tasks = [
                self._fetch_single_source(session, name, url) 
                for name, url in sources.items()
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Обработка результатов
            news_items = []
            for result in results:
                if isinstance(result, Exception):
                    logging.error(f"Ошибка загрузки RSS: {result}")
                else:
                    news_items.extend(result)
            
            return news_items
    
    async def _fetch_single_source(self, session: aiohttp.ClientSession, 
                                 source_name: str, url: str) -> List[NewsItem]:
        """Загрузка одного RSS источника"""
        async with self.semaphore:
            try:
                async with session.get(url) as response:
                    content = await response.text()
                    # Парсинг в отдельном потоке
                    loop = asyncio.get_event_loop()
                    with ThreadPoolExecutor() as executor:
                        return await loop.run_in_executor(
                            executor, self._parse_rss_content, content, source_name
                        )
            except Exception as e:
                logging.error(f"Ошибка загрузки {source_name}: {e}")
                return []

# ===== 2. КЕШИРОВАНИЕ =====
import time
from functools import wraps

class CacheManager:
    """Система кеширования для оптимизации"""
    
    def __init__(self):
        self.cache = {}
        self.cache_ttl = {}
    
    def cached(self, ttl: int = 3600):
        """Декоратор для кеширования результатов"""
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                cache_key = f"{func.__name__}:{hash(str(args) + str(kwargs))}"
                
                # Проверка актуальности кеша
                if (cache_key in self.cache and 
                    time.time() - self.cache_ttl.get(cache_key, 0) < ttl):
                    return self.cache[cache_key]
                
                # Выполнение функции и кеширование
                result = await func(*args, **kwargs)
                self.cache[cache_key] = result
                self.cache_ttl[cache_key] = time.time()
                
                return result
            return wrapper
        return decorator

# ===== 3. БАТЧИНГ AI ЗАПРОСОВ =====
class BatchProcessor:
    """Батчинг запросов к AI для экономии"""
    
    def __init__(self, batch_size: int = 5, batch_timeout: float = 10.0):
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self.pending_requests = []
        self.batch_timer = None
    
    async def add_request(self, news_item: NewsItem) -> str:
        """Добавление запроса в батч"""
        self.pending_requests.append(news_item)
        
        # Если батч заполнен - обрабатываем
        if len(self.pending_requests) >= self.batch_size:
            return await self._process_batch()
        
        # Иначе запускаем таймер
        if self.batch_timer is None:
            self.batch_timer = asyncio.create_task(
                self._wait_for_batch_timeout()
            )
        
        # Ждем обработки
        while news_item in self.pending_requests:
            await asyncio.sleep(0.1)
    
    async def _process_batch(self):
        """Обработка батча запросов"""
        if not self.pending_requests:
            return
        
        batch = self.pending_requests.copy()
        self.pending_requests.clear()
        
        # Объединяем все новости в один запрос
        combined_text = "\n\n---\n\n".join([
            f"НОВОСТЬ {i+1}:\n{news.title}\n{news.description}"
            for i, news in enumerate(batch)
        ])
        
        # Один запрос к AI для всего батча
        result = await self._make_ai_request(combined_text)
        
        # Парсим результат обратно
        return self._split_batch_result(result, len(batch))

# ===== 4. МОНИТОРИНГ ПРОИЗВОДИТЕЛЬНОСТИ =====
import psutil
from datetime import datetime

class PerformanceMonitor:
    """Мониторинг производительности бота"""
    
    def __init__(self):
        self.metrics = {
            "requests_per_minute": 0,
            "avg_response_time": 0,
            "memory_usage": 0,
            "cpu_usage": 0,
            "active_connections": 0
        }
    
    def collect_metrics(self):
        """Сбор метрик производительности"""
        process = psutil.Process()
        
        self.metrics.update({
            "memory_usage": process.memory_info().rss / 1024 / 1024,  # MB
            "cpu_usage": process.cpu_percent(),
            "timestamp": datetime.now().isoformat()
        })
        
        return self.metrics
    
    async def performance_alert(self, threshold_memory: int = 500):
        """Алерт при высоком потреблении ресурсов"""
        metrics = self.collect_metrics()
        
        if metrics["memory_usage"] > threshold_memory:
            return f"⚠️ Высокое потребление памяти: {metrics['memory_usage']:.1f} MB"
        
        if metrics["cpu_usage"] > 80:
            return f"⚠️ Высокая нагрузка CPU: {metrics['cpu_usage']:.1f}%"
        
        return None

# ===== 5. ОПТИМИЗАЦИЯ БАЗЫ ДАННЫХ =====
import sqlite3
from contextlib import asynccontextmanager

class OptimizedDatabase:
    """Оптимизированная работа с базой данных"""
    
    def __init__(self, db_path: str, pool_size: int = 5):
        self.db_path = db_path
        self.pool_size = pool_size
        self._setup_optimizations()
    
    def _setup_optimizations(self):
        """Настройка оптимизаций SQLite"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
            conn.execute("PRAGMA cache_size = 10000")
            conn.execute("PRAGMA temp_store = MEMORY")
            
            # Создание индексов для быстрого поиска
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_published_news_link 
                ON published_news(link)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_published_news_title_hash 
                ON published_news(title_hash)
            """)
    
    @asynccontextmanager
    async def get_connection(self):
        """Контекстный менеджер для соединений"""
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
        finally:
            conn.close()
    
    async def bulk_insert(self, news_items: List[NewsItem]):
        """Массовая вставка новостей"""
        async with self.get_connection() as conn:
            data = [
                (news.link, news.title, news.source, datetime.now())
                for news in news_items
            ]
            conn.executemany(
                "INSERT OR IGNORE INTO published_news (link, title, source, published_at) VALUES (?, ?, ?, ?)",
                data
            )
            conn.commit()

# ===== 6. УМНАЯ ОЧЕРЕДЬ ЗАДАЧ =====
from enum import Enum
import heapq

class TaskPriority(Enum):
    HIGH = 1
    MEDIUM = 2
    LOW = 3

@dataclass
class Task:
    priority: TaskPriority
    created_at: datetime
    func: callable
    args: tuple
    kwargs: dict
    
    def __lt__(self, other):
        return self.priority.value < other.priority.value

class SmartTaskQueue:
    """Умная очередь задач с приоритетами"""
    
    def __init__(self, max_workers: int = 3):
        self.queue = []
        self.max_workers = max_workers
        self.active_workers = 0
        self.is_running = False
    
    async def add_task(self, func: callable, priority: TaskPriority = TaskPriority.MEDIUM, 
                      *args, **kwargs):
        """Добавление задачи в очередь"""
        task = Task(priority, datetime.now(), func, args, kwargs)
        heapq.heappush(self.queue, task)
        
        if not self.is_running:
            await self.start_processing()
    
    async def start_processing(self):
        """Запуск обработки очереди"""
        self.is_running = True
        
        while self.queue and self.active_workers < self.max_workers:
            if self.queue:
                task = heapq.heappop(self.queue)
                self.active_workers += 1
                asyncio.create_task(self._execute_task(task))
    
    async def _execute_task(self, task: Task):
        """Выполнение задачи"""
        try:
            if asyncio.iscoroutinefunction(task.func):
                await task.func(*task.args, **task.kwargs)
            else:
                task.func(*task.args, **task.kwargs)
        except Exception as e:
            logging.error(f"Ошибка выполнения задачи: {e}")
        finally:
            self.active_workers -= 1
            
            # Проверяем, есть ли еще задачи
            if self.queue:
                await self.start_processing()
            elif self.active_workers == 0:
                self.is_running = False 