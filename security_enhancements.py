# Улучшения безопасности и мониторинга для AI News Bot

import os
import hmac
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
import asyncio
from dataclasses import dataclass
import json

# ===== 1. БЕЗОПАСНОСТЬ API =====
class SecureAPIClient:
    """Безопасный клиент для API с ротацией ключей"""
    
    def __init__(self, api_keys: List[str], rate_limit_per_minute: int = 60):
        self.api_keys = api_keys
        self.current_key_index = 0
        self.rate_limit = rate_limit_per_minute
        self.request_counts = {}
        self.key_blacklist = set()
    
    def get_active_key(self) -> str:
        """Получение активного API ключа"""
        # Поиск рабочего ключа
        for i in range(len(self.api_keys)):
            key_index = (self.current_key_index + i) % len(self.api_keys)
            if key_index not in self.key_blacklist:
                current_minute = datetime.now().strftime("%Y-%m-%d-%H-%M")
                key_requests = self.request_counts.get(f"{key_index}_{current_minute}", 0)
                
                if key_requests < self.rate_limit:
                    self.current_key_index = key_index
                    return self.api_keys[key_index]
        
        raise Exception("Все API ключи исчерпаны или заблокированы")
    
    def record_request(self):
        """Запись использования ключа"""
        current_minute = datetime.now().strftime("%Y-%m-%d-%H-%M")
        key = f"{self.current_key_index}_{current_minute}"
        self.request_counts[key] = self.request_counts.get(key, 0) + 1
    
    def blacklist_current_key(self, duration_minutes: int = 60):
        """Временная блокировка текущего ключа"""
        self.key_blacklist.add(self.current_key_index)
        
        # Автоматическое разблокирование через время
        async def unblock():
            await asyncio.sleep(duration_minutes * 60)
            self.key_blacklist.discard(self.current_key_index)
        
        asyncio.create_task(unblock())

# ===== 2. СИСТЕМА АЛЕРТОВ =====
@dataclass
class Alert:
    level: str  # INFO, WARNING, ERROR, CRITICAL
    message: str
    timestamp: datetime
    source: str
    metadata: Dict

class AlertManager:
    """Система управления алертами"""
    
    def __init__(self, telegram_bot, admin_chat_id: str):
        self.bot = telegram_bot
        self.admin_chat_id = admin_chat_id
        self.alert_history = []
        self.rate_limiter = {}
    
    async def send_alert(self, level: str, message: str, source: str = "bot", 
                        metadata: Dict = None, rate_limit_minutes: int = 30):
        """Отправка алерта с rate limiting"""
        alert = Alert(level, message, datetime.now(), source, metadata or {})
        
        # Rate limiting для одинаковых алертов
        alert_key = f"{level}_{source}_{hash(message)}"
        last_sent = self.rate_limiter.get(alert_key)
        
        if last_sent and (datetime.now() - last_sent).seconds < rate_limit_minutes * 60:
            return  # Не отправляем дубликат
        
        self.rate_limiter[alert_key] = datetime.now()
        self.alert_history.append(alert)
        
        # Форматирование сообщения
        emoji_map = {
            "INFO": "ℹ️",
            "WARNING": "⚠️", 
            "ERROR": "❌",
            "CRITICAL": "🚨"
        }
        
        formatted_message = (
            f"{emoji_map.get(level, '📢')} <b>{level}</b>\n"
            f"🕐 {alert.timestamp.strftime('%H:%M:%S')}\n"
            f"📍 {source}\n\n"
            f"{message}"
        )
        
        if metadata:
            formatted_message += f"\n\n<pre>{json.dumps(metadata, indent=2, ensure_ascii=False)}</pre>"
        
        try:
            await self.bot.send_message(
                chat_id=self.admin_chat_id,
                text=formatted_message,
                parse_mode='HTML'
            )
        except Exception as e:
            logging.error(f"Не удалось отправить алерт: {e}")

# ===== 3. МОНИТОРИНГ ЗДОРОВЬЯ СИСТЕМЫ =====
class HealthMonitor:
    """Мониторинг здоровья системы"""
    
    def __init__(self, alert_manager: AlertManager):
        self.alert_manager = alert_manager
        self.metrics = {
            "last_successful_cycle": None,
            "consecutive_failures": 0,
            "memory_usage_history": [],
            "api_response_times": [],
            "database_health": True
        }
    
    async def check_system_health(self):
        """Комплексная проверка здоровья системы"""
        issues = []
        
        # 1. Проверка времени последнего успешного цикла
        if self.metrics["last_successful_cycle"]:
            time_since_success = datetime.now() - self.metrics["last_successful_cycle"]
            if time_since_success > timedelta(hours=4):
                issues.append(f"Нет успешных циклов уже {time_since_success}")
        
        # 2. Проверка количества ошибок подряд
        if self.metrics["consecutive_failures"] > 5:
            issues.append(f"Много ошибок подряд: {self.metrics['consecutive_failures']}")
        
        # 3. Проверка памяти
        import psutil
        memory_mb = psutil.Process().memory_info().rss / 1024 / 1024
        if memory_mb > 500:  # Больше 500MB
            issues.append(f"Высокое потребление памяти: {memory_mb:.1f} MB")
        
        # 4. Проверка скорости API
        if self.metrics["api_response_times"]:
            avg_response = sum(self.metrics["api_response_times"][-10:]) / min(10, len(self.metrics["api_response_times"]))
            if avg_response > 30:  # Медленнее 30 сек
                issues.append(f"Медленные API ответы: {avg_response:.1f}s")
        
        # 5. Проверка базы данных
        if not self.metrics["database_health"]:
            issues.append("Проблемы с базой данных")
        
        # Отправка алертов
        if issues:
            await self.alert_manager.send_alert(
                "WARNING",
                "Обнаружены проблемы в работе системы:\n\n" + "\n".join(f"• {issue}" for issue in issues),
                "health_monitor",
                {"issues_count": len(issues)}
            )
    
    def record_successful_cycle(self):
        """Запись успешного цикла"""
        self.metrics["last_successful_cycle"] = datetime.now()
        self.metrics["consecutive_failures"] = 0
    
    def record_failed_cycle(self, error: str):
        """Запись неудачного цикла"""
        self.metrics["consecutive_failures"] += 1
        
        # Критический алерт после многих ошибок
        if self.metrics["consecutive_failures"] == 10:
            asyncio.create_task(
                self.alert_manager.send_alert(
                    "CRITICAL",
                    f"Критическая ситуация: 10 ошибок подряд!\nПоследняя ошибка: {error}",
                    "health_monitor"
                )
            )

# ===== 4. ЗАЩИТА ОТ СПАМА И ЗЛОУПОТРЕБЛЕНИЙ =====
class SpamProtection:
    """Защита от спама и злоупотреблений"""
    
    def __init__(self, max_requests_per_hour: int = 100):
        self.max_requests = max_requests_per_hour
        self.request_log = {}
        self.blocked_sources = set()
    
    def is_request_allowed(self, source: str) -> bool:
        """Проверка, разрешен ли запрос"""
        if source in self.blocked_sources:
            return False
        
        current_hour = datetime.now().strftime("%Y-%m-%d-%H")
        key = f"{source}_{current_hour}"
        
        requests_count = self.request_log.get(key, 0)
        return requests_count < self.max_requests
    
    def record_request(self, source: str):
        """Запись запроса"""
        current_hour = datetime.now().strftime("%Y-%m-%d-%H")
        key = f"{source}_{current_hour}"
        self.request_log[key] = self.request_log.get(key, 0) + 1
    
    def block_source(self, source: str, duration_hours: int = 24):
        """Блокировка источника"""
        self.blocked_sources.add(source)
        
        # Автоматическая разблокировка
        async def unblock():
            await asyncio.sleep(duration_hours * 3600)
            self.blocked_sources.discard(source)
        
        asyncio.create_task(unblock())

# ===== 5. БЕЗОПАСНОЕ ХРАНЕНИЕ КОНФИГУРАЦИИ =====
class SecureConfig:
    """Безопасное хранение конфигурации с шифрованием"""
    
    def __init__(self, master_key: str = None):
        self.master_key = master_key or os.environ.get('MASTER_KEY') or self._generate_key()
    
    def _generate_key(self) -> str:
        """Генерация мастер-ключа"""
        return secrets.token_urlsafe(32)
    
    def encrypt_value(self, value: str) -> str:
        """Шифрование значения"""
        # Простое XOR шифрование (для production используйте cryptography)
        key_bytes = self.master_key.encode()
        value_bytes = value.encode()
        
        encrypted = bytearray()
        for i, byte in enumerate(value_bytes):
            encrypted.append(byte ^ key_bytes[i % len(key_bytes)])
        
        return encrypted.hex()
    
    def decrypt_value(self, encrypted_value: str) -> str:
        """Расшифровка значения"""
        encrypted_bytes = bytes.fromhex(encrypted_value)
        key_bytes = self.master_key.encode()
        
        decrypted = bytearray()
        for i, byte in enumerate(encrypted_bytes):
            decrypted.append(byte ^ key_bytes[i % len(key_bytes)])
        
        return decrypted.decode()
    
    def store_secret(self, key: str, value: str, file_path: str = "secrets.json"):
        """Безопасное сохранение секрета"""
        encrypted_value = self.encrypt_value(value)
        
        # Загрузка существующих секретов
        secrets_data = {}
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                secrets_data = json.load(f)
        
        secrets_data[key] = encrypted_value
        
        # Сохранение с правильными правами доступа
        with open(file_path, 'w') as f:
            json.dump(secrets_data, f)
        
        os.chmod(file_path, 0o600)  # Только владелец может читать/писать

# ===== 6. ЛОГИРОВАНИЕ БЕЗОПАСНОСТИ =====
class SecurityLogger:
    """Специальное логирование для безопасности"""
    
    def __init__(self, log_file: str = "security.log"):
        self.log_file = log_file
        self.security_logger = logging.getLogger("security")
        
        # Настройка отдельного файла для логов безопасности
        handler = logging.FileHandler(log_file)
        formatter = logging.Formatter(
            '%(asctime)s - SECURITY - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        self.security_logger.addHandler(handler)
        self.security_logger.setLevel(logging.INFO)
    
    def log_suspicious_activity(self, activity: str, source: str, metadata: Dict = None):
        """Логирование подозрительной активности"""
        self.security_logger.warning(
            f"Suspicious activity: {activity} from {source}. Metadata: {metadata}"
        )
    
    def log_security_event(self, event: str, level: str = "INFO"):
        """Логирование событий безопасности"""
        log_func = getattr(self.security_logger, level.lower())
        log_func(f"Security event: {event}")

# ===== 7. WEBHOOK БЕЗОПАСНОСТЬ =====
class WebhookSecurity:
    """Безопасность для webhook endpoints"""
    
    def __init__(self, secret_token: str):
        self.secret_token = secret_token
    
    def verify_signature(self, payload: bytes, signature: str) -> bool:
        """Проверка подписи webhook"""
        expected_signature = hmac.new(
            self.secret_token.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(f"sha256={expected_signature}", signature)
    
    def generate_signature(self, payload: bytes) -> str:
        """Генерация подписи для исходящих webhook"""
        signature = hmac.new(
            self.secret_token.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return f"sha256={signature}" 