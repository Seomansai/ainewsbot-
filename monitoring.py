# Система мониторинга для AI News Bot
import json
import time
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import logging

class AlertLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

@dataclass
class Metric:
    name: str
    value: float
    timestamp: datetime
    tags: Dict[str, str] = None

@dataclass
class Alert:
    level: AlertLevel
    message: str
    timestamp: datetime
    metric_name: Optional[str] = None
    metric_value: Optional[float] = None

class MetricsCollector:
    """Сборщик метрик для мониторинга бота"""
    
    def __init__(self, storage_path: str = "metrics.json"):
        self.storage_path = storage_path
        self.metrics: Dict[str, List[Metric]] = {}
        self.alerts: List[Alert] = []
        self.alert_handlers: List[Callable] = []
        self.thresholds = self._default_thresholds()
        
    def _default_thresholds(self) -> Dict[str, Dict]:
        """Пороги для алертов по умолчанию"""
        return {
            "error_rate": {"warning": 0.1, "critical": 0.3},  # 10% warning, 30% critical
            "processing_time": {"warning": 300, "critical": 600},  # 5 min warning, 10 min critical
            "api_cost": {"warning": 3.0, "critical": 4.5},  # $3 warning, $4.50 critical
            "memory_usage": {"warning": 80, "critical": 95},  # 80% warning, 95% critical
            "failed_news_ratio": {"warning": 0.2, "critical": 0.5}  # 20% warning, 50% critical
        }
    
    def counter(self, name: str, value: float = 1.0, tags: Dict[str, str] = None):
        """Счетчик событий"""
        metric = Metric(name, value, datetime.now(), tags)
        if name not in self.metrics:
            self.metrics[name] = []
        self.metrics[name].append(metric)
        self._check_thresholds(name, value)
    
    def gauge(self, name: str, value: float, tags: Dict[str, str] = None):
        """Измерение текущего значения"""
        metric = Metric(name, value, datetime.now(), tags)
        if name not in self.metrics:
            self.metrics[name] = []
        self.metrics[name].append(metric)
        self._check_thresholds(name, value)
    
    def timer(self, name: str):
        """Контекстный менеджер для измерения времени"""
        return TimerContext(self, name)
    
    def _check_thresholds(self, metric_name: str, value: float):
        """Проверка порогов и генерация алертов"""
        if metric_name not in self.thresholds:
            return
            
        thresholds = self.thresholds[metric_name]
        
        if value >= thresholds.get("critical", float('inf')):
            self._create_alert(AlertLevel.CRITICAL, f"{metric_name} достиг критического уровня: {value}", metric_name, value)
        elif value >= thresholds.get("warning", float('inf')):
            self._create_alert(AlertLevel.WARNING, f"{metric_name} превысил предупреждающий уровень: {value}", metric_name, value)
    
    def _create_alert(self, level: AlertLevel, message: str, metric_name: str = None, metric_value: float = None):
        """Создание алерта"""
        alert = Alert(level, message, datetime.now(), metric_name, metric_value)
        self.alerts.append(alert)
        
        # Вызов обработчиков алертов
        for handler in self.alert_handlers:
            try:
                handler(alert)
            except Exception as e:
                logging.error(f"Ошибка в обработчике алертов: {e}")
    
    def add_alert_handler(self, handler: Callable[[Alert], None]):
        """Добавление обработчика алертов"""
        self.alert_handlers.append(handler)
    
    def get_metrics_summary(self, hours: int = 24) -> Dict:
        """Получение сводки метрик за период"""
        cutoff = datetime.now() - timedelta(hours=hours)
        summary = {}
        
        for metric_name, metrics in self.metrics.items():
            recent_metrics = [m for m in metrics if m.timestamp >= cutoff]
            if recent_metrics:
                values = [m.value for m in recent_metrics]
                summary[metric_name] = {
                    "count": len(values),
                    "sum": sum(values),
                    "avg": sum(values) / len(values),
                    "min": min(values),
                    "max": max(values),
                    "latest": values[-1]
                }
        
        return summary
    
    def get_health_score(self) -> float:
        """Получение общей оценки здоровья системы (0-100)"""
        summary = self.get_metrics_summary(1)  # За последний час
        score = 100.0
        
        # Штрафы за различные проблемы
        if "error_rate" in summary and summary["error_rate"]["avg"] > 0:
            score -= min(50, summary["error_rate"]["avg"] * 100)
        
        if "failed_requests" in summary:
            score -= min(20, summary["failed_requests"]["count"] * 2)
        
        if "processing_time" in summary and summary["processing_time"]["avg"] > 60:
            score -= min(30, (summary["processing_time"]["avg"] - 60) / 10)
        
        return max(0.0, score)
    
    def cleanup_old_data(self, hours: int = 168):  # 7 дней
        """Очистка старых метрик"""
        cutoff = datetime.now() - timedelta(hours=hours)
        for metric_name in self.metrics:
            self.metrics[metric_name] = [
                m for m in self.metrics[metric_name] 
                if m.timestamp >= cutoff
            ]
    
    def export_prometheus(self) -> str:
        """Экспорт метрик в формате Prometheus"""
        lines = []
        summary = self.get_metrics_summary(1)
        
        for metric_name, stats in summary.items():
            # Counter metrics
            if metric_name.endswith(("_total", "_count")):
                lines.append(f'# TYPE {metric_name} counter')
                lines.append(f'{metric_name} {stats["sum"]}')
            # Gauge metrics
            else:
                lines.append(f'# TYPE {metric_name} gauge')
                lines.append(f'{metric_name} {stats["latest"]}')
        
        return '\n'.join(lines)

class TimerContext:
    """Контекстный менеджер для измерения времени"""
    
    def __init__(self, collector: MetricsCollector, name: str):
        self.collector = collector
        self.name = name
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        self.collector.gauge(f"{self.name}_duration", duration)

class TelegramAlertHandler:
    """Отправка алертов в Telegram"""
    
    def __init__(self, bot_token: str, admin_chat_id: str):
        self.bot = Bot(token=bot_token)
        self.admin_chat_id = admin_chat_id
    
    async def handle_alert(self, alert: Alert):
        """Обработка алерта"""
        emoji_map = {
            AlertLevel.INFO: "ℹ️",
            AlertLevel.WARNING: "⚠️",
            AlertLevel.ERROR: "❌",
            AlertLevel.CRITICAL: "🚨"
        }
        
        emoji = emoji_map.get(alert.level, "❓")
        message = f"{emoji} <b>{alert.level.value.upper()}</b>\n\n{alert.message}\n\n<i>{alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</i>"
        
        try:
            await self.bot.send_message(
                chat_id=self.admin_chat_id,
                text=message,
                parse_mode='HTML'
            )
        except Exception as e:
            logging.error(f"Ошибка отправки алерта в Telegram: {e}")

class HealthChecker:
    """Проверка здоровья различных компонентов системы"""
    
    def __init__(self, metrics: MetricsCollector):
        self.metrics = metrics
    
    async def check_database_health(self, db_connection) -> bool:
        """Проверка здоровья базы данных"""
        try:
            cursor = db_connection.execute("SELECT 1")
            result = cursor.fetchone()
            self.metrics.gauge("database_health", 1.0 if result else 0.0)
            return result is not None
        except Exception as e:
            logging.error(f"Проблема с базой данных: {e}")
            self.metrics.gauge("database_health", 0.0)
            return False
    
    async def check_api_health(self, client, test_model: str = "meta-llama/llama-3.1-8b-instruct:free") -> bool:
        """Проверка здоровья API"""
        try:
            response = client.chat.completions.create(
                model=test_model,
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=5
            )
            self.metrics.gauge("api_health", 1.0)
            return True
        except Exception as e:
            logging.error(f"Проблема с API: {e}")
            self.metrics.gauge("api_health", 0.0)
            return False
    
    async def check_telegram_health(self, bot) -> bool:
        """Проверка здоровья Telegram бота"""
        try:
            me = await bot.get_me()
            self.metrics.gauge("telegram_health", 1.0 if me else 0.0)
            return me is not None
        except Exception as e:
            logging.error(f"Проблема с Telegram: {e}")
            self.metrics.gauge("telegram_health", 0.0)
            return False

# Интеграция с основным ботом
class MonitoredAINewsBot:
    """AI News Bot с интегрированным мониторингом"""
    
    def __init__(self, config, metrics: MetricsCollector = None):
        self.config = config
        self.metrics = metrics or MetricsCollector()
        self.health_checker = HealthChecker(self.metrics)
        
        # Настройка алертов
        if config.admin_telegram_id:
            alert_handler = TelegramAlertHandler(config.telegram_token, config.admin_telegram_id)
            self.metrics.add_alert_handler(lambda alert: asyncio.create_task(alert_handler.handle_alert(alert)))
    
    async def run_cycle_with_monitoring(self):
        """Цикл с мониторингом"""
        start_time = time.time()
        
        try:
            with self.metrics.timer("news_cycle"):
                # Проверка здоровья компонентов
                await self._health_checks()
                
                # Основная логика
                success_count = 0
                error_count = 0
                
                # ... логика обработки новостей ...
                
                # Записываем метрики
                self.metrics.counter("news_processed", success_count)
                self.metrics.counter("news_failed", error_count)
                
                if success_count + error_count > 0:
                    error_rate = error_count / (success_count + error_count)
                    self.metrics.gauge("error_rate", error_rate)
                
                duration = time.time() - start_time
                self.metrics.gauge("cycle_duration", duration)
                
                # Оценка здоровья
                health_score = self.metrics.get_health_score()
                self.metrics.gauge("health_score", health_score)
                
                logging.info(f"📊 Цикл завершен. Здоровье: {health_score:.1f}/100")
                
        except Exception as e:
            self.metrics.counter("cycle_errors")
            self.metrics._create_alert(AlertLevel.ERROR, f"Ошибка в цикле: {str(e)}")
            raise
    
    async def _health_checks(self):
        """Проверки здоровья системы"""
        # Проверка БД, API, Telegram и т.д.
        pass 