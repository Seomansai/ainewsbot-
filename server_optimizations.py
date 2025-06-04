# Оптимизации для серверного развертывания 24/7

import os
import threading
import time
import psutil
from http.server import HTTPServer, SimpleHTTPRequestHandler
import json
from datetime import datetime

# ===== 1. KEEP-ALIVE СЕРВЕР ДЛЯ RENDER =====
def setup_keep_alive_server():
    """HTTP сервер для предотвращения засыпания на бесплатном хостинге"""
    
    class HealthHandler(SimpleHTTPRequestHandler):
        def do_GET(self):
            if self.path == '/':
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                
                html_content = """
                <!DOCTYPE html>
                <html>
                <head>
                    <title>AI News Bot</title>
                    <meta charset="utf-8">
                    <style>
                        body { font-family: Arial; text-align: center; padding: 50px; background: #f0f0f0; }
                        .container { background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
                        .status { color: #28a745; font-size: 24px; margin: 20px 0; }
                        .stats { text-align: left; margin: 20px 0; }
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h1>🤖 AI News Bot v2.0</h1>
                        <div class="status">✅ Статус: РАБОТАЕТ</div>
                        <div class="stats">
                            <h3>📊 Информация о системе:</h3>
                            <p><strong>Время работы:</strong> {uptime}</p>
                            <p><strong>Использование памяти:</strong> {memory} MB</p>
                            <p><strong>Последняя проверка:</strong> {timestamp}</p>
                            <p><strong>Версия:</strong> 2.0</p>
                        </div>
                        <p>Автоматический парсинг и публикация AI новостей</p>
                        <p><small>Powered by Claude 3.5 Sonnet & OpenRouter</small></p>
                    </div>
                </body>
                </html>
                """.format(
                    uptime=self.get_uptime(),
                    memory=self.get_memory_usage(),
                    timestamp=datetime.now().strftime('%H:%M:%S %d.%m.%Y')
                ).encode('utf-8')
                
                self.wfile.write(html_content)
                
            elif self.path == '/health':
                # Health check endpoint для мониторинга
                health_data = {
                    'status': 'healthy',
                    'timestamp': datetime.now().isoformat(),
                    'uptime_seconds': time.time() - self.server.start_time,
                    'memory_mb': self.get_memory_usage(),
                    'version': '2.0'
                }
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(health_data).encode())
                
            elif self.path == '/metrics':
                # Metrics endpoint для Prometheus/мониторинга
                metrics = f"""
# HELP bot_uptime_seconds Bot uptime in seconds
# TYPE bot_uptime_seconds counter
bot_uptime_seconds {time.time() - self.server.start_time}

# HELP bot_memory_mb Memory usage in MB
# TYPE bot_memory_mb gauge
bot_memory_mb {self.get_memory_usage()}

# HELP bot_status Bot status (1 = healthy, 0 = unhealthy)
# TYPE bot_status gauge
bot_status 1
"""
                self.send_response(200)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(metrics.encode())
                
            else:
                self.send_response(404)
                self.end_headers()
        
        def get_uptime(self):
            """Получение времени работы"""
            uptime_seconds = time.time() - self.server.start_time
            hours = int(uptime_seconds // 3600)
            minutes = int((uptime_seconds % 3600) // 60)
            return f"{hours}ч {minutes}м"
        
        def get_memory_usage(self):
            """Получение использования памяти"""
            try:
                process = psutil.Process()
                return round(process.memory_info().rss / 1024 / 1024, 1)
            except:
                return 0
        
        def log_message(self, format, *args):
            """Отключение логов HTTP запросов"""
            pass
    
    # Запуск сервера
    port = int(os.environ.get('PORT', 8080))
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    server.start_time = time.time()
    
    def run_server():
        print(f"🌐 Keep-alive сервер запущен на порту {port}")
        server.serve_forever()
    
    thread = threading.Thread(target=run_server)
    thread.daemon = True
    thread.start()
    
    return server

# ===== 2. АВТОМАТИЧЕСКИЙ ПИНГ (для Render бесплатного тарифа) =====
def setup_self_ping(bot_url: str = None):
    """Автоматический пинг для предотвращения засыпания"""
    
    if not bot_url:
        # Попытка автоопределения URL
        service_name = os.environ.get('RENDER_SERVICE_NAME', 'ai-news-bot')
        bot_url = f"https://{service_name}.onrender.com"
    
    async def ping_self():
        """Пингует сам себя каждые 14 минут"""
        import aiohttp
        
        while True:
            try:
                await asyncio.sleep(14 * 60)  # 14 минут
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{bot_url}/health", timeout=10) as response:
                        if response.status == 200:
                            print(f"🏓 Self-ping успешен: {datetime.now().strftime('%H:%M')}")
                        else:
                            print(f"⚠️ Self-ping неудачен: {response.status}")
                            
            except Exception as e:
                print(f"❌ Ошибка self-ping: {e}")
                await asyncio.sleep(60)  # Повтор через минуту при ошибке
    
    # Запуск в фоновой задаче
    import asyncio
    asyncio.create_task(ping_self())

# ===== 3. МОНИТОРИНГ РЕСУРСОВ =====
class ResourceMonitor:
    """Мониторинг ресурсов сервера"""
    
    def __init__(self, alert_callback=None):
        self.alert_callback = alert_callback
        self.start_time = time.time()
        self.memory_threshold = 400  # MB
        self.cpu_threshold = 80      # %
    
    async def start_monitoring(self):
        """Запуск мониторинга ресурсов"""
        while True:
            try:
                memory_mb = psutil.Process().memory_info().rss / 1024 / 1024
                cpu_percent = psutil.Process().cpu_percent()
                
                # Проверка превышения лимитов
                if memory_mb > self.memory_threshold:
                    await self.send_alert(f"🚨 Высокое потребление памяти: {memory_mb:.1f} MB")
                
                if cpu_percent > self.cpu_threshold:
                    await self.send_alert(f"🚨 Высокая нагрузка CPU: {cpu_percent:.1f}%")
                
                # Логирование каждый час
                uptime_hours = (time.time() - self.start_time) / 3600
                if int(uptime_hours) > 0 and int(uptime_hours) % 6 == 0:  # Каждые 6 часов
                    print(f"📊 Статус: RAM {memory_mb:.1f}MB, CPU {cpu_percent:.1f}%, Uptime {uptime_hours:.1f}h")
                
                await asyncio.sleep(300)  # Проверка каждые 5 минут
                
            except Exception as e:
                print(f"❌ Ошибка мониторинга: {e}")
                await asyncio.sleep(60)
    
    async def send_alert(self, message: str):
        """Отправка алерта"""
        if self.alert_callback:
            await self.alert_callback(message)
        print(f"⚠️ ALERT: {message}")

# ===== 4. GRACEFUL SHUTDOWN =====
import signal
import asyncio

class GracefulShutdown:
    """Корректное завершение работы бота"""
    
    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.shutdown_event = asyncio.Event()
        
        # Регистрация обработчиков сигналов
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Обработчик сигналов завершения"""
        print(f"\n🛑 Получен сигнал {signum}, начинаю корректное завершение...")
        self.shutdown_event.set()
    
    async def wait_for_shutdown(self):
        """Ожидание сигнала завершения"""
        await self.shutdown_event.wait()
        await self.cleanup()
    
    async def cleanup(self):
        """Корректное завершение работы"""
        try:
            print("🧹 Очистка ресурсов...")
            
            # Сохранение данных
            if hasattr(self.bot, 'database_connection'):
                self.bot.database_connection.close()
            
            # Уведомление админа
            if hasattr(self.bot, '_send_admin_alert'):
                await self.bot._send_admin_alert("🛑 Бот остановлен корректно")
            
            print("✅ Очистка завершена")
            
        except Exception as e:
            print(f"❌ Ошибка при завершении: {e}")

# ===== 5. ОПТИМИЗАЦИЯ ЛОГИРОВАНИЯ ДЛЯ СЕРВЕРА =====
def setup_server_logging():
    """Настройка логирования для серверной среды"""
    import logging
    import sys
    from logging.handlers import RotatingFileHandler
    
    # Создание форматтера
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Основной логгер
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Консольный хендлер (для Docker/облачных логов)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Файловый хендлер с ротацией (если есть доступ к файловой системе)
    try:
        file_handler = RotatingFileHandler(
            'bot.log', 
            maxBytes=10*1024*1024,  # 10MB
            backupCount=3
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except:
        pass  # Игнорируем ошибки файловой системы в облаке

# ===== 6. АВТОМАТИЧЕСКОЕ ВОССТАНОВЛЕНИЕ =====
class AutoRecovery:
    """Автоматическое восстановление при ошибках"""
    
    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.consecutive_errors = 0
        self.max_errors = 5
        self.recovery_delay = 300  # 5 минут
    
    async def run_with_recovery(self, coro):
        """Запуск функции с автоматическим восстановлением"""
        while True:
            try:
                await coro()
                self.consecutive_errors = 0  # Сброс счетчика при успехе
                
            except Exception as e:
                self.consecutive_errors += 1
                print(f"❌ Ошибка #{self.consecutive_errors}: {e}")
                
                if self.consecutive_errors >= self.max_errors:
                    print(f"🚨 Критическое количество ошибок, ожидание {self.recovery_delay}с")
                    await asyncio.sleep(self.recovery_delay)
                    self.consecutive_errors = 0
                else:
                    # Экспоненциальная задержка
                    delay = min(60 * (2 ** self.consecutive_errors), 300)
                    await asyncio.sleep(delay)

# ===== ИНТЕГРАЦИЯ В ОСНОВНОЙ БОТ =====
"""
Добавить в main() функцию telegram-ai-news-bot.py:

async def main():
    # Настройка для сервера
    setup_server_logging()
    
    # Создание бота
    bot = AINewsBot()
    
    # Keep-alive сервер
    keep_alive_server = setup_keep_alive_server()
    
    # Мониторинг ресурсов
    monitor = ResourceMonitor(alert_callback=bot._send_admin_alert)
    asyncio.create_task(monitor.start_monitoring())
    
    # Автоматический пинг (только для Render)
    if os.environ.get('RENDER_SERVICE_NAME'):
        setup_self_ping()
    
    # Graceful shutdown
    shutdown_handler = GracefulShutdown(bot)
    
    # Автоматическое восстановление
    recovery = AutoRecovery(bot)
    
    try:
        # Запуск бота с восстановлением
        await recovery.run_with_recovery(bot.start_bot)
    except KeyboardInterrupt:
        print("🛑 Получен Ctrl+C")
    finally:
        await shutdown_handler.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
""" 