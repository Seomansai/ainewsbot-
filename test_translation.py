#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест переводчика OpenRouter
"""

import os
from openai import OpenAI

# Загрузка переменных окружения
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

def test_translation():
    """Тестирование перевода с помощью OpenRouter"""
    
    openrouter_key = os.getenv('OPENROUTER_API_KEY')
    
    if not openrouter_key:
        print("❌ OPENROUTER_API_KEY не найден в .env файле")
        return
    
    client = OpenAI(
        api_key=openrouter_key,
        base_url="https://openrouter.ai/api/v1"
    )
    
    # Тестовые тексты (реальные примеры AI новостей)
    test_texts = [
        "OpenAI releases GPT-4 Turbo with improved reasoning capabilities",
        "Meta's new AI model achieves state-of-the-art performance on benchmark tests while reducing computational costs by 40%",
        "Researchers develop neural network architecture that can process multimodal data with unprecedented accuracy"
    ]
    
    print("🤖 Тестирование OpenRouter переводчика...\n")
    
    # Доступные модели для тестирования
    models = [
        "openai/gpt-3.5-turbo",
        "anthropic/claude-3-haiku",
        "meta-llama/llama-3.1-8b-instruct"
    ]
    
    for model in models:
        print(f"🎯 Тестируем модель: {model}")
        print("=" * 60)
        
        for i, text in enumerate(test_texts[:1], 1):  # Тестируем только первый текст для экономии
            print(f"📝 Тест {i}:")
            print(f"Оригинал: {text}")
            
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
                            "content": f"Переведи этот текст на русский:\n\n{text}"
                        }
                    ],
                    temperature=0.2,
                    max_tokens=1500
                )
                
                translation = response.choices[0].message.content.strip()
                print(f"Перевод: {translation}")
                print("-" * 60)
                
            except Exception as e:
                print(f"❌ Ошибка при переводе: {e}")
                print("-" * 60)
        
        print()

if __name__ == "__main__":
    test_translation() 