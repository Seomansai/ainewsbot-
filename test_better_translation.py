#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест улучшенного перевода
"""

import os
from openai import OpenAI

# Загрузка переменных окружения
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

def test_better_translation():
    """Тестирование улучшенного перевода"""
    
    openrouter_key = os.getenv('OPENROUTER_API_KEY')
    
    if not openrouter_key:
        print("❌ OPENROUTER_API_KEY не найден в .env файле")
        return
    
    client = OpenAI(
        api_key=openrouter_key,
        base_url="https://openrouter.ai/api/v1"
    )
    
    # Проблемный текст из примера
    test_text = """Reinforcing seamless AI at scale

From large language models (LLMs) to reasoning agents, modern AI tools demand unprecedented computational resources. Trillion-parameter models running on-device and swarms of agents collaborating to complete tasks require a new approach to computing to become truly seamless and ubiquitous. First, technical progress in hardware and silicon design is critical for pushing the boundaries..."""
    
    print("🔧 Тестирование улучшенного перевода...\n")
    
    # Улучшенный промпт
    improved_prompt = """Ты опытный переводчик технических текстов из сферы IT и искусственного интеллекта. 

ПРАВИЛА ПЕРЕВОДА:
1. Переводи ЕСТЕСТВЕННО для русского языка
2. Адаптируй англицизмы под русскую речь
3. Сохраняй технические термины (AI, API, GPU, ML, LLM)
4. Избегай калек и буквального перевода
5. Используй краткие, понятные конструкции
6. Проверяй грамматику и орфографию

ПРИМЕРЫ:
- "state-of-the-art" → "передовой/современный/лучший"
- "seamless AI" → "бесшовный ИИ" → "интегрированный ИИ"
- "computational costs" → "вычислительные затраты"
- "trillion-parameter models" → "модели с триллионом параметров"
- "swarms of agents" → "множество агентов"
- "ubiquitous" → "повсеместный/универсальный"

Переводи как для читателей технических новостей."""

    # Модели для тестирования
    models = [
        ("meta-llama/llama-3.1-8b-instruct:free", "Llama 3.1 (бесплатно)"),
        ("openai/gpt-3.5-turbo", "GPT-3.5 Turbo (платно)"),
        ("anthropic/claude-3-haiku", "Claude 3 Haiku (платно)")
    ]
    
    for model, name in models:
        print(f"🎯 {name}")
        print("=" * 60)
        
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": improved_prompt},
                    {"role": "user", "content": f"Переведи этот текст:\n\n{test_text}"}
                ],
                temperature=0.1,
                max_tokens=2000
            )
            
            translation = response.choices[0].message.content.strip()
            print(f"✅ Перевод:\n{translation}")
            
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            
        print("-" * 60)
        print()

if __name__ == "__main__":
    test_better_translation() 