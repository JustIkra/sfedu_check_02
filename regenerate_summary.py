#!/usr/bin/env python3
"""
Скрипт для пересоздания итоговой ведомости из существующих JSON результатов.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from auto_checker import generate_final_summary


async def main():
    test_dir = "/Users/maksim/git_projects/sfedu_check_02/test_run/ИИ_в_образовании_и_науке_Задание_№2_Исследование_применения_технологий (3)"

    print(f"Пересоздание итоговой ведомости из: {test_dir}")
    print()

    await generate_final_summary(test_dir)

    summary_path = Path(test_dir) / f"Итоговая_ведомость_{Path(test_dir).name}.xlsx"
    if summary_path.exists():
        print(f"✅ Ведомость создана: {summary_path}")

        # Читаем и показываем содержимое
        import pandas as pd
        df = pd.read_excel(summary_path)
        print(f"\n📊 Обработано студентов: {len(df)}")
        print("\n🔍 Результаты:")
        print(df[['Студент', 'Результат', 'AI-детекция']].to_string(index=False))
    else:
        print("❌ Ведомость не создана")


if __name__ == "__main__":
    asyncio.run(main())
