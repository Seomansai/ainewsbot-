#!/usr/bin/env python3
"""
Скрипт для проверки состояния базы данных AI News Bot
Используется для диагностики проблем с дубликатами
"""

import os
import sqlite3
from datetime import datetime, timedelta
import json

def check_database():
    """Проверка состояния базы данных"""
    
    # Определяем путь к БД (так же как в основном боте)
    if os.path.exists('/opt/render') or os.getenv('RENDER'):
        db_path = '/opt/render/project/ai_news.db'
    elif os.path.exists('/app'):  # Heroku
        db_path = '/app/ai_news.db'
    else:
        db_path = os.getenv('DATABASE_PATH', 'ai_news.db')
    
    print(f"🔍 Проверка базы данных: {db_path}")
    
    if not os.path.exists(db_path):
        print("❌ База данных не найдена!")
        return
    
    db_size = os.path.getsize(db_path)
    print(f"📁 Размер файла: {db_size} байт")
    
    try:
        conn = sqlite3.connect(db_path)
        
        # Проверяем структуру таблицы
        cursor = conn.execute("PRAGMA table_info(published_news)")
        columns = cursor.fetchall()
        print(f"\n📋 Структура таблицы:")
        for col in columns:
            print(f"  • {col[1]} ({col[2]})")
        
        # Общая статистика
        total = conn.execute("SELECT COUNT(*) FROM published_news").fetchone()[0]
        print(f"\n📊 Общая статистика:")
        print(f"  • Всего записей: {total}")
        
        # Проверяем наличие колонки status
        status_column_exists = any(col[1] == 'status' for col in columns)
        
        if status_column_exists:
            published = conn.execute("SELECT COUNT(*) FROM published_news WHERE status = 'published'").fetchone()[0]
            reserved = conn.execute("SELECT COUNT(*) FROM published_news WHERE status = 'reserved'").fetchone()[0]
            print(f"  • Опубликованных: {published}")
            print(f"  • Зарезервированных: {reserved}")
        else:
            print("  ⚠️ Колонка 'status' не найдена (старая версия БД)")
        
        # Записи за последние дни
        day_ago = datetime.now() - timedelta(hours=24)
        week_ago = datetime.now() - timedelta(days=7)
        
        recent_day = conn.execute("SELECT COUNT(*) FROM published_news WHERE created_at > ?", (day_ago,)).fetchone()[0]
        recent_week = conn.execute("SELECT COUNT(*) FROM published_news WHERE created_at > ?", (week_ago,)).fetchone()[0]
        
        print(f"  • За последние 24 часа: {recent_day}")
        print(f"  • За последнюю неделю: {recent_week}")
        
        # Последние 5 записей
        print(f"\n📝 Последние 5 записей:")
        if status_column_exists:
            cursor = conn.execute(
                "SELECT title, status, created_at FROM published_news ORDER BY created_at DESC LIMIT 5"
            )
        else:
            cursor = conn.execute(
                "SELECT title, created_at FROM published_news ORDER BY created_at DESC LIMIT 5"
            )
        
        records = cursor.fetchall()
        for i, record in enumerate(records, 1):
            if status_column_exists:
                title, status, created_at = record
                print(f"  {i}. [{status}] {title[:50]}... ({created_at})")
            else:
                title, created_at = record
                print(f"  {i}. {title[:50]}... ({created_at})")
        
        # Поиск потенциальных дубликатов
        print(f"\n🔍 Поиск потенциальных дубликатов:")
        cursor = conn.execute("""
            SELECT link, COUNT(*) as count 
            FROM published_news 
            GROUP BY link 
            HAVING count > 1
        """)
        duplicates = cursor.fetchall()
        
        if duplicates:
            print(f"  ❌ Найдено {len(duplicates)} дубликатов по ссылкам:")
            for link, count in duplicates[:5]:  # Показываем первые 5
                print(f"    • {link[:50]}... (повторений: {count})")
        else:
            print(f"  ✅ Дубликатов по ссылкам не найдено")
        
        conn.close()
        print(f"\n✅ Проверка завершена")
        
    except Exception as e:
        print(f"❌ Ошибка при проверке БД: {e}")

if __name__ == "__main__":
    check_database() 