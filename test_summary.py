#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест пересказа новостей
"""

import os
from openai import OpenAI

# Загрузка переменных окружения
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

def test_news_summary():
    """Тестирование пересказа новостей"""
    
    openrouter_key = os.getenv('OPENROUTER_API_KEY')
    
    if not openrouter_key:
        print("❌ OPENROUTER_API_KEY не найден в .env файле")
        return
    
    client = OpenAI(
        api_key=openrouter_key,
        base_url="https://openrouter.ai/api/v1"
    )
    
    # Пример реальной новости
    test_title = "OpenAI releases GPT-4 Turbo with improved reasoning capabilities"
    test_description = "The latest version of OpenAI's flagship model demonstrates significant improvements in multi-step reasoning, mathematical problem-solving, and code generation. The enhanced model shows 40% better performance on complex reasoning benchmarks while maintaining the same API compatibility. OpenAI also announced reduced pricing for the new model, making it more accessible for developers and enterprises."
    
    print("📰 Тест создания пересказа новости...\n")
    print(f"🇺🇸 Оригинал:")
    print(f"Заголовок: {test_title}")
    print(f"Описание: {test_description}")
    print("-" * 80)
    
    # Промпт для пересказа
    summary_prompt = """Ты опытный технический журналист, специализирующийся на новостях об искусственном интеллекте.

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

    try:
        response = client.chat.completions.create(
            model="meta-llama/llama-3.1-8b-instruct:free",
            messages=[
                {"role": "system", "content": summary_prompt},
                {"role": "user", "content": f"Создай краткий пересказ этой новости:\n\nЗаголовок: {test_title}\nТекст: {test_description}"}
            ],
            temperature=0.3,
            max_tokens=800
        )
        
        summary = response.choices[0].message.content.strip()
        print(f"🇷🇺 Пересказ:\n{summary}")
        print("-" * 80)
        
        # Пример форматирования в Telegram
        print("📱 Как будет выглядеть в Telegram:")
        print()
        print("🤖 AI Новости")
        print()
        print(summary)
        print()
        print("📰 Источник: OpenAI Blog")
        print("🔗 Читать оригинал статьи")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    test_news_summary() 