#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Быстрый тест перевода
"""

import os
from openai import OpenAI

# Загрузка переменных окружения
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

def quick_test():
    """Быстрый тест улучшенного перевода"""
    
    openrouter_key = os.getenv('OPENROUTER_API_KEY')
    
    if not openrouter_key:
        print("❌ OPENROUTER_API_KEY не найден в .env файле")
        return
    
    client = OpenAI(
        api_key=openrouter_key,
        base_url="https://openrouter.ai/api/v1"
    )
    
    # Короткий проблемный текст
    test_text = """Reinforcing seamless AI at scale. Modern AI tools demand unprecedented computational resources."""
    
    print("🚀 Быстрый тест улучшенного перевода...\n")
    print(f"📝 Оригинал: {test_text}")
    
    # Улучшенный промпт
    improved_prompt = """Ты опытный переводчик IT-текстов. 

ПРАВИЛА:
- Переводи естественно для русского языка
- "seamless" = "интегрированный/бесшовный"  
- "at scale" = "в масштабе/массово"
- "unprecedented" = "беспрецедентный/невиданный"

Переводи кратко и понятно."""

    try:
        response = client.chat.completions.create(
            model="meta-llama/llama-3.1-8b-instruct:free",
            messages=[
                {"role": "system", "content": improved_prompt},
                {"role": "user", "content": f"Переведи: {test_text}"}
            ],
            temperature=0.1,
            max_tokens=500
        )
        
        translation = response.choices[0].message.content.strip()
        print(f"✅ Новый перевод: {translation}")
        print()
        print("Сравни с предыдущим:")
        print("❌ Старый: 'Подкрепление бесшовной ИИ на масштабе'")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    quick_test() 