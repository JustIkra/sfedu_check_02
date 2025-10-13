"""Helper script to verify archive uploads via the Flask test client."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path


def _ensure_ok(status_code: int, step: str) -> None:
    if status_code >= 400:
        raise RuntimeError(f"Шаг '{step}' завершился ошибкой: {status_code}")


def _locate_sample_archive(repo_root: Path) -> Path:
    candidates = sorted(repo_root.glob("ИИ_*.zip"))
    if not candidates:
        raise SystemExit("Не найден образец архива с заданиями в корне репозитория.")
    return candidates[0]


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    archive_path = _locate_sample_archive(repo_root)
    sys.path.insert(0, str(repo_root))

    with tempfile.TemporaryDirectory(prefix="archive-upload-") as tmp_dir:
        tmp_root = Path(tmp_dir)
        os.environ["DATABASE_PATH"] = str(tmp_root / "demo.sqlite3")
        os.environ["DATA_STORAGE"] = str(tmp_root / "storage")

        from app import create_app  # noqa: WPS433
        from app.models import Room  # noqa: WPS433

        app = create_app()
        client = app.test_client()

        with app.app_context():
            response = client.post(
                "/",
                data={"name": "Тестовая комната", "description": ""},
                follow_redirects=False,
            )
            _ensure_ok(response.status_code, "создание комнаты")

            room = Room.query.filter_by(name="Тестовая комната").first()
            assert room is not None, "Комната должна быть создана"

            with archive_path.open("rb") as payload:
                response = client.post(
                    f"/rooms/{room.id}",
                    data={
                        "action": "upload_submission",
                        "submission_zip": (payload, archive_path.name),
                    },
                    content_type="multipart/form-data",
                    follow_redirects=False,
                )
            _ensure_ok(response.status_code, "загрузка архива")

            uploads_dir = Path(os.environ["DATA_STORAGE"]) / room.id / "uploads"
            stored_archives = sorted(item.name for item in uploads_dir.glob("*") if item.is_file())

        print("Загруженные архивы:", stored_archives)


if __name__ == "__main__":
    main()
