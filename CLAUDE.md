# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an automated student assignment review system that uses Google's Gemini API to evaluate student work. The system consists of:

1. **Web Application** (Flask-based): Provides a "rooms" interface for organizing review tasks, with isolated configurations and file storage per room.
2. **CLI Checker** (`auto_checker.py`): Core processing engine that extracts text from documents (.docx, .doc, .pdf, onlinetext.html) and evaluates them using AI.

The system supports multiple document formats per student, AI-generated content detection, and generates comprehensive Excel-based grade reports.

## Development Commands

### Local Development
```bash
# Setup virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Run Flask app in debug mode
flask --app app:create_app run --debug
# Access at http://localhost:5000
```

### Docker Deployment
```bash
# Build image (includes OpenVPN client)
docker build -t auto-checker .

# Run container (requires NET_ADMIN for VPN)
docker run \
  --cap-add=NET_ADMIN \
  --device /dev/net/tun \
  -p 9003:9003 \
  auto-checker
# Access at http://localhost:9003
```

### Testing

**Offline test** (deterministic evaluation without AI API):
```bash
export DUMMY_EVAL=true
tmp_dir=$(mktemp -d)
unzip -q example/ii.zip -d "$tmp_dir"
root_dir=$(find "$tmp_dir" -maxdepth 1 -type d ! -path "$tmp_dir" | head -n1)

python - <<'PY'
import asyncio, os
from auto_checker import run_auto_checker_async

async def main():
    df, summary = await run_auto_checker_async(
        root_dir=os.environ['root_dir'],
        template_path='Шаблон.docx',
        room_prompt='',
        ai_check_enabled=False,
    )
    print('Ведомость:', summary)

asyncio.run(main())
PY
```

## Architecture

### Multi-File Processing Logic (auto_checker.py)

The system processes all documents per student and aggregates results:
- Each file produces a detailed JSON result in `results/<filename>.json`
- An aggregated `result.txt` is written with the best result (priority: "зачтено" > latest date > longest comment)
- Final grade sheet is `Итоговая_ведомость_<folder>.xlsx` in the root directory

Key functions:
- `find_all_submissions()`: Discovers all student files recursively
- `process_submission()`: Extracts text and evaluates a single file
- `generate_final_summary()`: Aggregates per-file results, applies deduplication by student ID, creates Excel report

### AI Integration

**API Key Rotation** (`GeminiClient`):
- Rotates through 12+ Gemini API keys to avoid quota limits
- Implements exponential backoff and automatic key switching on 429/RESOURCE_EXHAUSTED errors
- Respects rate limits with configurable delays (10-20s between requests)

**Two-Stage Evaluation**:
1. `check_ai_generation()`: Detects AI-generated content (confidence levels: низкая/средняя/высокая)
2. `get_binary_evaluation()`: Final grading (зачтено/не зачтено) incorporating AI detection confidence

**AI Check Toggle** (`ai_check_enabled`):
- When enabled: AI detection is performed, and high-confidence AI-generated work receives "не зачтено"
- When disabled: Focuses solely on content quality, logic, and formatting

### Web Application (Flask)

**Room-based Architecture** (`app/`):
- Each Room has isolated storage under `DATA_STORAGE/<room_id>/`
- Subdirectories: `uploads/` (ZIP archives), `templates/` (custom criteria), `workspace/` (extracted files), `reports/` (results)
- Background job system (`app/background.py`, `job_manager`) prevents concurrent checks per room

**Database** (SQLite via Flask-SQLAlchemy):
- `Room` model: stores name, description, prompt configurations, template filename, AI check toggle
- Two prompt fields (`check_prompt`, `task_prompt`) unified via `prompt` property for backward compatibility

**Key Routes** (`app/routes.py`):
- `/`: List rooms, create new room
- `/room/<room_id>`: Room detail page
- `/room/<room_id>/check`: Launch auto-check job
- `/room/<room_id>/job/<job_id>`: Monitor job progress

## Configuration

### Environment Variables
- `SECRET_KEY`: Flask session secret (default: "dev-secret-key")
- `DATABASE_PATH`: Custom database location (default: instance/auto_checker.db)
- `DATA_STORAGE`: File storage root (default: instance/data)
- `DEFAULT_TEMPLATE_PATH`: Default grading criteria template (default: Шаблон.docx)
- `PROJECT_TAGLINE`: UI tagline (default: "поддержка наставников и студентов")
- `DUMMY_EVAL`: Set to "true" for deterministic offline testing (evaluates by text length >= 400 chars)

### Proxy Configuration
The checker supports SOCKS5/HTTP proxies via:
- `HTTPS_PROXY` / `HTTP_PROXY` (standard env vars)
- OR explicit: `PROXY_HOST`, `PROXY_PORT`, `PROXY_USER`, `PROXY_PASS`

All traffic to Gemini API is routed through the proxy if configured.

## Important Implementation Notes

### PDF Support
PDF text extraction uses PyPDF2 (`extract_text_from_pdf()`). Falls back to binary decoding if PyPDF2 is unavailable.

### Student Deduplication
`generate_final_summary()` deduplicates students by:
1. Extracting student ID from folder name (Moodle format: `Name_123_assignsubmission_file`)
2. Using normalized student name as fallback key
3. Selecting best result per student: "зачтено" > latest date > longest comment

### Unicode Filename Handling
All file uploads preserve Unicode characters (`_preserve_upload_name()` uses NFC normalization) to support Cyrillic filenames from Moodle exports.

## Testing Workflow

When implementing new features:
1. Test with `DUMMY_EVAL=true` first to verify file processing logic without API calls
2. Use `example/ii.zip` as test data (contains PDF/DOCX samples)
3. Verify both web UI (`/room/<id>/check`) and CLI (`auto_checker.py`) paths
4. Check `results/*.json` structure and final Excel output formatting

## Migration Notes

- Database schema changes require manual migration (see `migrate_add_ai_check_field.py` as example)
- When adding new Room fields, update both model (`app/models.py`) and forms/templates
