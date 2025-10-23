# Руководство: обработка PDF и нескольких документов

## Что изменилось
- Поддерживаются форматы: `.pdf`, `.docx`, `.doc`, `onlinetext.html`.
- Если в папке студента несколько файлов, обрабатываются все. В итоговый `result.txt` записывается лучший результат (приоритет: «зачтено», затем более поздняя дата, затем более подробный комментарий).
- Для каждого файла сохраняется детальный результат в `results/<имя_файла>.json`. Итоговая ведомость формируется в корневой папке как `Итоговая_ведомость_<папка>.xlsx`.

## Структура данных и пример
- Ожидается корневая папка с подпапками студентов (как в выгрузках Moodle).
- Пример архива с PDF/Docx находится в `example/ii.zip`.

## Быстрый офлайн‑тест (без обращения к внешнему ИИ)
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Включаем детерминированную оценку по объёму текста
export DUMMY_EVAL=true

# Распаковываем пример в временную директорию
tmp_dir=$(mktemp -d)
unzip -q example/ii.zip -d "$tmp_dir"
root_dir=$(find "$tmp_dir" -maxdepth 1 -type d ! -path "$tmp_dir" | head -n1)

python - <<'PY'
import asyncio, os
from auto_checker import run_auto_checker_async

root_dir = os.environ['root_dir'] if 'root_dir' in os.environ else None
template = 'Шаблон.docx'

async def main():
    df, summary = await run_auto_checker_async(
        root_dir=root_dir,
        template_path=template,
        room_prompt='',
        ai_check_enabled=False,  # отключаем детектор AI для офлайн‑прогона
    )
    print('Ведомость:', summary)

asyncio.run(main())
PY
```

Ожидаемый результат:
- Появится файл `Итоговая_ведомость_*.xlsx` в корне тестовой папки.
- В каждой папке студента: `results/*.json` по каждому документу и агрегированный `result.txt`.
- Если хотя бы один файл у студента «зачтено», агрегат также «зачтено».

## Прогон в «боевом» режиме
- Уберите `DUMMY_EVAL`, включите `ai_check_enabled=True` в запуске и настройте сеть/прокси (см. `start.sh`, переменные `PROXY_*`, `DISABLE_VPN`).
- Убедитесь, что используются безопасные ключи/секреты (не храните их в репозитории).

