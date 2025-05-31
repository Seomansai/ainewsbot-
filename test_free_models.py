#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест бесплатных моделей OpenRouter
"""

import os
from openai import OpenAI

# Загрузка переменных окружения
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

def test_free_models():
    """Тестирование бесплатных моделей OpenRouter"""
    
    openrouter_key = os.getenv('OPENROUTER_API_KEY')
    
    if not openrouter_key:
        print("❌ OPENROUTER_API_KEY не найден в .env файле")
        return
    
    client = OpenAI(
        api_key=openrouter_key,
        base_url="https://openrouter.ai/api/v1"
    )
    
    # Тестовый текст
    test_text = "Meta's new AI model achieves state-of-the-art performance on benchmark tests while reducing computational costs by 40%"
    
    print("🆓 Тестирование бесплатных моделей OpenRouter...\n")
    
    # Доступные бесплатные модели
    free_models = [
        "meta-llama/llama-3.1-8b-instruct:free",
        "microsoft/phi-3-medium-128k-instruct:free", 
        "google/gemma-2-9b-it:free",
        "qwen/qwen-2-7b-instruct:free"
    ]
    
    for model in free_models:
        print(f"🎯 Модель: {model}")
        print("=" * 70)
        print(f"📝 Оригинал: {test_text}")
        
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system", 
                        "content": "Ты профессиональный переводчик технических текстов. Переведи текст с английского на русский язык, сохраняя все технические термины, аббревиатуры и смысл. Делай перевод естественным и читабельным для русскоязычной аудитории. Сохраняй стиль оригинала."
                    },
                    {
                        "role": "user", 
                        "content": f"Переведи этот текст на русский:\n\n{test_text}"
                    }
                ],
                temperature=0.2,
                max_tokens=1000
            )
            
            translation = response.choices[0].message.content.strip()
            print(f"✅ Перевод: {translation}")
            
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            
        print("-" * 70)
        print()

if __name__ == "__main__":
    test_free_models() 