#!/usr/bin/env python3
"""
Онлайн тестирование проверки с реальным Gemini API.
Проверяет:
1. Обработку PDF файлов
2. Множественную проверку документов
3. Агрегацию результатов
"""

import asyncio
import os
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent))

from auto_checker import run_auto_checker_async


async def main():
    print("=" * 80)
    print("🧪 ОНЛАЙН ТЕСТИРОВАНИЕ: Множественная проверка + PDF")
    print("=" * 80)
    print()

    # Настройка путей
    root_dir = "/Users/maksim/git_projects/sfedu_check_02/test_run/ИИ_в_образовании_и_науке_Задание_№2_Исследование_применения_технологий (3)"
    template_path = "/Users/maksim/git_projects/sfedu_check_02/Шаблон.docx"

    print(f"📁 Директория: {root_dir}")
    print(f"📄 Шаблон: {template_path}")
    print()
    print("🔍 Ключевые тестовые случаи:")
    print("  • Денисенко Максим - 2 DOCX файла (тест агрегации)")
    print("  • Буи А Боя Бертран - 2 PDF файла (тест PDF + агрегация)")
    print("  • Боженюк Александр - 1 PDF (тест PDF)")
    print("  • Донская Марина - onlinetext.html (тест HTML)")
    print()
    print("⚙️  AI-проверка: ВКЛЮЧЕНА")
    print("🌐 Прокси: SOCKS5 настроен через переменные окружения")
    print("🔑 API Keys: Ротация 12 ключей Gemini")
    print()
    print("⏱️  Примерное время: ~15-25 минут для всех студентов")
    print()
    input("▶️  Нажмите Enter для начала проверки...")
    print()

    try:
        df, summary_path = await run_auto_checker_async(
            root_dir=root_dir,
            template_path=template_path,
            room_prompt="",
            ai_check_enabled=True,  # Включаем AI-проверку
        )

        if df is not None and summary_path is not None:
            print()
            print("=" * 80)
            print("✅ ПРОВЕРКА ЗАВЕРШЕНА УСПЕШНО!")
            print("=" * 80)
            print()
            print(f"📊 Итоговая ведомость: {summary_path}")
            print(f"📈 Обработано студентов: {len(df)}")
            print()
            print("🔍 Результаты:")
            print(df[['Студент', 'Результат', 'AI-детекция']].to_string(index=False))
            print()

            # Проверяем ключевые случаи
            print("=" * 80)
            print("🎯 ПРОВЕРКА КЛЮЧЕВЫХ СЛУЧАЕВ")
            print("=" * 80)
            print()

            # 1. Денисенко - множественные DOCX
            denisenko = df[df['Студент'].str.contains('Денисенко', na=False)]
            if not denisenko.empty:
                print("✅ Денисенко Максим (2 DOCX - агрегация):")
                print(f"   Результат: {denisenko.iloc[0]['Результат']}")
                results_dir = Path(root_dir) / "Денисенко Максим Евгеньевич_76330_assignsubmission_file" / "results"
                if results_dir.exists():
                    json_files = list(results_dir.glob("*.json"))
                    print(f"   Файлов проверено: {len(json_files)}")
                    for jf in json_files:
                        print(f"     - {jf.name}")
                print()

            # 2. Буи - множественные PDF
            bui = df[df['Студент'].str.contains('Буи', na=False)]
            if not bui.empty:
                print("✅ Буи А Боя (2 PDF - агрегация + PDF):")
                print(f"   Результат: {bui.iloc[0]['Результат']}")
                results_dir = Path(root_dir) / "Буи А Боя Бертран Фредерик_22660_assignsubmission_file" / "results"
                if results_dir.exists():
                    json_files = list(results_dir.glob("*.json"))
                    print(f"   Файлов проверено: {len(json_files)}")
                    for jf in json_files:
                        print(f"     - {jf.name}")
                print()

            # 3. Боженюк - одиночный PDF
            bozh = df[df['Студент'].str.contains('Боженюк', na=False)]
            if not bozh.empty:
                print("✅ Боженюк Александр (1 PDF):")
                print(f"   Результат: {bozh.iloc[0]['Результат']}")
                print()

            # 4. Донская - HTML
            don = df[df['Студент'].str.contains('Донская', na=False)]
            if not don.empty:
                print("✅ Донская Марина (HTML):")
                print(f"   Результат: {don.iloc[0]['Результат']}")
                print()

            print("=" * 80)
            print("🎉 ТЕСТИРОВАНИЕ ЗАВЕРШЕНО!")
            print("=" * 80)

        else:
            print()
            print("❌ ОШИБКА: Проверка завершена без формирования ведомости")

    except Exception as e:
        print()
        print(f"❌ ОШИБКА при выполнении проверки: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
