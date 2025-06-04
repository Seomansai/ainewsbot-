# Быстрые улучшения для немедленного внедрения

# ===== 1. ДОБАВИТЬ В telegram-ai-news-bot.py =====

# В блок RSS_SOURCES добавить новые источники:
ADDITIONAL_RSS_SOURCES = {
    # Корпоративные блоги
    "OpenAI Blog": "https://openai.com/blog/rss.xml",
    "Google AI Blog": "https://ai.googleblog.com/feeds/posts/default", 
    "Meta AI": "https://ai.facebook.com/blog/feed/",
    "NVIDIA AI": "https://blogs.nvidia.com/blog/category/artificial-intelligence/feed/",
    "Microsoft AI": "https://blogs.microsoft.com/ai/feed/",
    
    # Дополнительные русские
    "VC.ru AI": "https://vc.ru/tag/ai/rss",
    "Хабр Neural Networks": "https://habr.com/ru/rss/hub/neural_networks/",
    
    # Академические
    "Towards Data Science": "https://towardsdatascience.com/feed",
    "Machine Learning Mastery": "https://machinelearningmastery.com/feed/"
}

# ===== 2. УЛУЧШИТЬ ФУНКЦИЮ is_ai_related =====
def improved_is_ai_related(self, title: str, description: str) -> bool:
    """Улучшенная проверка релевантности к AI"""
    text = f"{title} {description}".lower()
    
    # Высокоприоритетные слова (вес 3)
    high_priority = [
        'artificial intelligence', 'machine learning', 'deep learning', 'neural network',
        'chatgpt', 'gpt-4', 'claude', 'llm', 'large language model', 'transformer',
        'искусственный интеллект', 'машинное обучение', 'нейросеть', 'нейронная сеть'
    ]
    
    # Среднеприоритетные слова (вес 2)  
    medium_priority = [
        'computer vision', 'natural language processing', 'nlp', 'automation',
        'algorithm', 'data science', 'predictive', 'classification',
        'компьютерное зрение', 'обработка языка', 'автоматизация', 'алгоритм'
    ]
    
    # Исключающие слова (штраф -5)
    exclude_words = [
        'cryptocurrency', 'bitcoin', 'blockchain', 'nft', 'web3', 'gaming',
        'криптовалюта', 'биткоин', 'блокчейн', 'игры'
    ]
    
    score = 0
    
    for word in high_priority:
        if word in text:
            score += 3
    
    for word in medium_priority:
        if word in text:
            score += 2
    
    for word in exclude_words:
        if word in text:
            score -= 5
    
    return score >= 3  # Повышенный порог для качества

# ===== 3. ДОБАВИТЬ МЕТРИКИ В АДМИНСКИЕ СООБЩЕНИЯ =====
def enhanced_daily_stats_message(self) -> str:
    """Улучшенная статистика с дополнительными метриками"""
    stats = self.get_statistics()
    cost_stats = self.cost_tracker.get_monthly_spending()
    
    # Расчет эффективности
    processed = stats.get('news_processed_today', 0)
    published = stats.get('news_published_today', 0)
    efficiency = (published / processed * 100) if processed > 0 else 0
    
    # Средняя стоимость за новость
    avg_cost = cost_stats / published if published > 0 else 0
    
    message = f"""📊 <b>Ежедневная статистика AI News Bot</b>
🗓 {datetime.now().strftime('%d.%m.%Y')}

📈 <b>Производительность:</b>
• Обработано новостей: {processed}
• Опубликовано: {published}
• Эффективность: {efficiency:.1f}%
• Дублей отфильтровано: {processed - published}

💰 <b>Расходы:</b>
• За сегодня: ${stats.get('cost_today', 0):.3f}
• За месяц: ${cost_stats:.2f}
• Средняя стоимость/новость: ${avg_cost:.3f}
• Остаток бюджета: ${self.cost_tracker.get_remaining_budget():.2f}

🔧 <b>Техническая информация:</b>
• Время последнего цикла: {stats.get('last_cycle_duration', 'N/A')}s
• Источников активных: {len([s for s in stats.get('source_stats', {}).values() if s > 0])}
• Ошибок за день: {stats.get('errors_today', 0)}

🌍 <b>Топ источники:</b>"""
    
    # Добавляем топ-3 источника
    source_stats = stats.get('source_stats', {})
    top_sources = sorted(source_stats.items(), key=lambda x: x[1], reverse=True)[:3]
    
    for i, (source, count) in enumerate(top_sources, 1):
        message += f"\n{i}. {source}: {count} новостей"
    
    return message

# ===== 4. ДОБАВИТЬ WEBHOOK ДЛЯ HEALTHCHECK =====
def add_health_endpoint(self):
    """Добавить endpoint для мониторинга здоровья"""
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import json
    import threading
    
    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == '/health':
                health_data = {
                    'status': 'healthy',
                    'timestamp': datetime.now().isoformat(),
                    'last_successful_cycle': self.server.bot.get_statistics().get('last_successful_cycle'),
                    'memory_usage_mb': psutil.Process().memory_info().rss / 1024 / 1024,
                    'version': '2.0'
                }
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(health_data).encode())
            else:
                self.send_response(404)
                self.end_headers()
    
    # Запуск сервера в отдельном потоке
    server = HTTPServer(('0.0.0.0', 8080), HealthHandler)
    server.bot = self  # Передаем ссылку на бота
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()

# ===== 5. ОПТИМИЗАЦИЯ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ =====
# Добавить в .env новые параметры:
"""
# Производительность
MAX_CONCURRENT_RSS=10
CACHE_TTL_HOURS=2
BATCH_SIZE=5

# Качество
MIN_RELEVANCE_SCORE=3
MAX_NEWS_PER_SOURCE=5
ENABLE_IMAGE_EXTRACTION=true

# Мониторинг  
HEALTH_CHECK_PORT=8080
ALERT_RATE_LIMIT_MINUTES=30
MEMORY_ALERT_THRESHOLD_MB=500

# Дополнительные источники
ENABLE_NEWSAPI=false
NEWSAPI_KEY=your_key_here
ENABLE_SOCIAL_MEDIA=false
"""

# ===== 6. ПРОСТАЯ КОМАНДА ДЛЯ АДМИНИСТРАТОРА =====
async def handle_admin_commands(self, message_text: str) -> str:
    """Обработка команд администратора"""
    if not message_text.startswith('/'):
        return None
    
    command = message_text.lower().strip()
    
    if command == '/stats':
        return self.enhanced_daily_stats_message()
    
    elif command == '/health':
        issues = await self.check_system_health()
        if issues:
            return f"⚠️ Обнаружены проблемы:\n" + '\n'.join(issues)
        else:
            return "✅ Система работает нормально"
    
    elif command == '/sources':
        stats = self.get_statistics().get('source_stats', {})
        active = len([s for s in stats.values() if s > 0])
        total = len(stats)
        return f"📡 Источников: {active}/{total} активных"
    
    elif command == '/cost':
        monthly = self.cost_tracker.get_monthly_spending()
        remaining = self.cost_tracker.get_remaining_budget()
        return f"💰 Расходы: ${monthly:.2f} | Остаток: ${remaining:.2f}"
    
    elif command == '/help':
        return """🤖 <b>Команды администратора:</b>
        
/stats - Подробная статистика
/health - Проверка здоровья системы  
/sources - Статус источников
/cost - Информация о расходах
/help - Эта справка"""
    
    return None 