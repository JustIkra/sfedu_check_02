#!/usr/bin/env python3
"""
Скрипт миграции для добавления поля ai_check_enabled в таблицу rooms.
Запустите этот скрипт один раз для обновления базы данных.
"""

import sqlite3
import sys
from pathlib import Path


def migrate_database(db_path: str):
    """Добавляет поле ai_check_enabled в таблицу rooms."""
    
    print(f"Начало миграции базы данных: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Проверяем, существует ли уже колонка
        cursor.execute("PRAGMA table_info(rooms)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'ai_check_enabled' in columns:
            print("✓ Поле ai_check_enabled уже существует в таблице rooms.")
            return
        
        # Добавляем новую колонку со значением по умолчанию True
        print("Добавление поля ai_check_enabled...")
        cursor.execute("""
            ALTER TABLE rooms 
            ADD COLUMN ai_check_enabled BOOLEAN NOT NULL DEFAULT 1
        """)
        
        conn.commit()
        print("✓ Поле ai_check_enabled успешно добавлено в таблицу rooms.")
        print("✓ Для всех существующих комнат установлено значение True (проверка включена).")
        
    except sqlite3.Error as e:
        print(f"✗ Ошибка при миграции: {e}", file=sys.stderr)
        conn.rollback()
        raise
    finally:
        conn.close()


def main():
    """Основная функция для запуска миграции."""
    
    # Путь к базе данных по умолчанию
    default_db_path = Path(__file__).parent / "instance" / "auto_checker.db"
    
    # Можно передать путь к БД как аргумент командной строки
    db_path = sys.argv[1] if len(sys.argv) > 1 else str(default_db_path)
    
    if not Path(db_path).exists():
        print(f"✗ База данных не найдена: {db_path}", file=sys.stderr)
        print("Создайте базу данных или укажите правильный путь.")
        sys.exit(1)
    
    try:
        migrate_database(db_path)
        print("\n✓ Миграция завершена успешно!")
    except Exception as e:
        print(f"\n✗ Миграция завершилась с ошибкой: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()


