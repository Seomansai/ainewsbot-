# Упрощенная система мониторинга для AI News Bot
import os
import time
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class AlertLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

@dataclass
class BotMetrics:
    """Метрики работы бота"""
    cycles_completed: int = 0
    news_processed: int = 0
    news_published: int = 0
    errors_count: int = 0
    api_requests: int = 0
    api_costs: float = 0.0
    last_cycle_duration: float = 0.0
    uptime_start: datetime = None
    
    def __post_init__(self):
        if self.uptime_start is None:
            self.uptime_start = datetime.now()

class SimpleMonitor:
    """Упрощенная система мониторинга"""
    
    def __init__(self, storage_path: str = "bot_metrics.json"):
        self.storage_path = storage_path
        self.metrics = BotMetrics()
        self.alerts: List[str] = []
        self.start_time = time.time()
        self._load_metrics()
    
    def _load_metrics(self):
        """Загрузка метрик из файла"""
        try:
            if os.path.exists(self.storage_path):
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)
                    # Восстанавливаем метрики
                    for key, value in data.items():
                        if hasattr(self.metrics, key):
                            if key == 'uptime_start':
                                setattr(self.metrics, key, datetime.fromisoformat(value))
                            else:
                                setattr(self.metrics, key, value)
        except Exception as e:
            logger.error(f"Ошибка загрузки метрик: {e}")
    
    def _save_metrics(self):
        """Сохранение метрик в файл"""
        try:
            data = {}
            for key, value in self.metrics.__dict__.items():
                if isinstance(value, datetime):
                    data[key] = value.isoformat()
                else:
                    data[key] = value
            
            with open(self.storage_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения метрик: {e}")
    
    def record_cycle_start(self):
        """Запись начала цикла"""
        self.cycle_start_time = time.time()
    
    def record_cycle_end(self, published_count: int = 0, error_count: int = 0):
        """Запись окончания цикла"""
        if hasattr(self, 'cycle_start_time'):
            duration = time.time() - self.cycle_start_time
            self.metrics.last_cycle_duration = duration
        
        self.metrics.cycles_completed += 1
        self.metrics.news_published += published_count
        self.metrics.errors_count += error_count
        
        self._save_metrics()
        
        # Проверка на аномалии
        if error_count > 3:
            self._add_alert(AlertLevel.WARNING, f"Много ошибок в цикле: {error_count}")
        
        if duration > 600:  # 10 минут
            self._add_alert(AlertLevel.WARNING, f"Долгий цикл: {duration:.1f} секунд")
    
    def record_api_usage(self, cost: float):
        """Запись использования API"""
        self.metrics.api_requests += 1
        self.metrics.api_costs += cost
        self._save_metrics()
    
    def record_news_processed(self, count: int):
        """Запись обработанных новостей"""
        self.metrics.news_processed += count
        self._save_metrics()
    
    def _add_alert(self, level: AlertLevel, message: str):
        """Добавление алерта"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        alert = f"[{timestamp}] {level.value.upper()}: {message}"
        self.alerts.append(alert)
        logger.warning(alert)
        
        # Оставляем только последние 100 алертов
        if len(self.alerts) > 100:
            self.alerts = self.alerts[-100:]
    
    def get_summary(self) -> Dict:
        """Получение сводки работы бота"""
        uptime = datetime.now() - self.metrics.uptime_start
        
        return {
            "uptime_hours": uptime.total_seconds() / 3600,
            "cycles_completed": self.metrics.cycles_completed,
            "news_published": self.metrics.news_published,
            "news_processed": self.metrics.news_processed,
            "errors_count": self.metrics.errors_count,
            "api_requests": self.metrics.api_requests,
            "api_costs": self.metrics.api_costs,
            "last_cycle_duration": self.metrics.last_cycle_duration,
            "avg_news_per_cycle": self.metrics.news_published / max(1, self.metrics.cycles_completed),
            "error_rate": self.metrics.errors_count / max(1, self.metrics.cycles_completed),
            "recent_alerts": self.alerts[-5:] if self.alerts else []
        }
    
    def format_summary_message(self) -> str:
        """Форматирование сводки для отправки в Telegram"""
        summary = self.get_summary()
        
        message = f"""📊 <b>Статистика AI News Bot</b>

⏱ <b>Работает:</b> {summary['uptime_hours']:.1f} часов
🔄 <b>Циклов завершено:</b> {summary['cycles_completed']}
📰 <b>Новостей опубликовано:</b> {summary['news_published']}
🔍 <b>Новостей обработано:</b> {summary['news_processed']}
❌ <b>Ошибок:</b> {summary['errors_count']}

💰 <b>API запросов:</b> {summary['api_requests']}
💵 <b>Потрачено:</b> ${summary['api_costs']:.4f}

📈 <b>Среднее:</b>
• {summary['avg_news_per_cycle']:.1f} новостей/цикл
• {summary['error_rate']:.1f} ошибок/цикл
• {summary['last_cycle_duration']:.1f}с последний цикл"""

        if summary['recent_alerts']:
            message += f"\n\n⚠️ <b>Последние алерты:</b>\n"
            for alert in summary['recent_alerts']:
                message += f"• <code>{alert}</code>\n"
        
        return message

# Интеграция с основным ботом
def add_monitoring_to_bot(bot_instance):
    """Добавление мониторинга к экземпляру бота"""
    bot_instance.monitor = SimpleMonitor()
    
    # Обертка для run_news_cycle
    original_cycle = bot_instance.run_news_cycle
    
    async def monitored_cycle():
        bot_instance.monitor.record_cycle_start()
        error_count = 0
        published_count = 0
        
        try:
            result = await original_cycle()
            published_count = getattr(result, 'published_count', 0)
        except Exception as e:
            error_count = 1
            raise
        finally:
            bot_instance.monitor.record_cycle_end(published_count, error_count)
    
    bot_instance.run_news_cycle = monitored_cycle
    
    # Добавляем команду для получения статистики
    async def get_bot_stats():
        return bot_instance.monitor.format_summary_message()
    
    bot_instance.get_bot_stats = get_bot_stats 