#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест премиум моделей для пересказа
"""

import os
from openai import OpenAI

# Загрузка переменных окружения
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

def test_premium_models():
    """Сравнение премиум моделей для пересказа новостей"""
    
    openrouter_key = os.getenv('OPENROUTER_API_KEY')
    
    if not openrouter_key:
        print("❌ OPENROUTER_API_KEY не найден в .env файле")
        return
    
    client = OpenAI(
        api_key=openrouter_key,
        base_url="https://openrouter.ai/api/v1"
    )
    
    # Сложная техническая новость для тестирования
    test_title = "Meta's new AI model achieves state-of-the-art performance"
    test_description = """Meta announced its latest large language model, Llama 3.1, which demonstrates unprecedented capabilities in reasoning, mathematics, and multilingual understanding. The model, trained on over 15 trillion tokens, achieves state-of-the-art performance on multiple benchmarks including MMLU, GSM8K, and HumanEval coding tasks. Meta claims the model outperforms GPT-4 on several key metrics while being more efficient in computational resources. The company is releasing the model under an open-source license, making it freely available for commercial use. This release marks a significant milestone in democratizing advanced AI capabilities."""
    
    print("🏆 Тест премиум моделей для пересказа новостей...\n")
    print(f"📝 Тестовая новость:")
    print(f"Заголовок: {test_title}")
    print(f"Описание: {test_description[:200]}...")
    print("=" * 80)
    
    # Премиум модели для тестирования
    premium_models = [
        ("anthropic/claude-3.5-sonnet", "Claude 3.5 Sonnet (ТОП)", "~$3/1M токенов"),
        ("openai/gpt-4o", "GPT-4o (OpenAI)", "~$5/1M токенов"),
        ("anthropic/claude-3-haiku", "Claude 3 Haiku (быстрая)", "~$0.25/1M токенов"),
        ("openai/gpt-3.5-turbo", "GPT-3.5 Turbo (экономная)", "~$1.5/1M токенов")
    ]
    
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

Создавай пересказ для русскоязычной аудитории."""
    
    for model, name, cost in premium_models:
        print(f"\n🎯 {name} ({cost})")
        print("-" * 60)
        
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": summary_prompt},
                    {"role": "user", "content": f"Создай краткий пересказ этой новости:\n\nЗаголовок: {test_title}\nТекст: {test_description}"}
                ],
                temperature=0.2,
                max_tokens=1000
            )
            
            summary = response.choices[0].message.content.strip()
            print(f"✅ Пересказ:\n{summary}")
            
        except Exception as e:
            print(f"❌ Ошибка: {e}")
        
        print()

if __name__ == "__main__":
    test_premium_models() 