import os
import shutil
import uuid
import zipfile
from pathlib import Path

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from werkzeug.utils import secure_filename

from auto_checker import run_auto_checker

from .default_prompts import DEFAULT_ROOM_PROMPT
from .models import Room
from . import db


bp = Blueprint("main", __name__)


def init_app(app):
    app.register_blueprint(bp)


def _room_storage(room_id: str) -> Path:
    storage = Path(current_app.config["DATA_STORAGE"]) / room_id
    uploads = storage / "uploads"
    templates = storage / "templates"
    uploads.mkdir(parents=True, exist_ok=True)
    templates.mkdir(parents=True, exist_ok=True)
    return storage


def _list_files(directory: Path):
    if not directory.exists():
        return []
    return sorted(
        [
            {
                "name": filename,
                "size": (directory / filename).stat().st_size,
            }
            for filename in os.listdir(directory)
            if (directory / filename).is_file()
        ],
        key=lambda item: item["name"].lower(),
    )


@bp.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip() or None

        if not name:
            flash("Укажите название комнаты.", "error")
        else:
            room = Room(
                id=str(uuid.uuid4()),
                name=name,
                description=description,
                check_prompt=DEFAULT_ROOM_PROMPT,
                task_prompt=DEFAULT_ROOM_PROMPT,
            )
            db.session.add(room)
            db.session.commit()
            flash("Комната успешно создана.", "success")
            return redirect(url_for("main.room_detail", room_id=room.id))

    rooms = Room.query.order_by(Room.created_at.desc()).all()
    return render_template(
        "index.html",
        rooms=rooms,
        default_room_prompt=DEFAULT_ROOM_PROMPT,
    )


@bp.route("/rooms/<room_id>", methods=["GET", "POST"])
def room_detail(room_id: str):
    room = Room.query.get_or_404(room_id)
    storage = _room_storage(room_id)
    uploads_dir = storage / "uploads"
    templates_dir = storage / "templates"

    if request.method == "POST":
        action = request.form.get("action")

        if action == "update_prompt":
            new_prompt = request.form.get("prompt", "").strip()
            if not new_prompt:
                flash("Введите текст промпта для комнаты.", "error")
            else:
                room.prompt = new_prompt
                db.session.commit()
                flash("Промпт комнаты обновлён.", "success")
            return redirect(url_for("main.room_detail", room_id=room.id))

        if action == "reset_prompt":
            room.prompt = DEFAULT_ROOM_PROMPT
            db.session.commit()
            flash("Промпт комнаты сброшен к шаблону.", "info")
            return redirect(url_for("main.room_detail", room_id=room.id))

        if action == "upload_submission":
            file = request.files.get("submission_zip")
            if not file or not file.filename:
                flash("Выберите zip-файл для загрузки.", "error")
            else:
                filename = secure_filename(file.filename)
                if not filename.lower().endswith(".zip"):
                    flash("Разрешена загрузка только .zip файлов.", "error")
                else:
                    destination = uploads_dir / filename
                    file.save(destination)
                    flash("Архив с заданиями загружен.", "success")
            return redirect(url_for("main.room_detail", room_id=room.id))

        if action == "upload_template":
            template_file = request.files.get("template_file")
            if not template_file or not template_file.filename:
                flash("Выберите файл шаблона для загрузки.", "error")
            else:
                filename = secure_filename(template_file.filename)
                destination = templates_dir / filename
                template_file.save(destination)
                room.template_filename = filename
                db.session.commit()
                flash("Шаблон сохранён для комнаты.", "success")
            return redirect(url_for("main.room_detail", room_id=room.id))

        if action == "run_auto_checker":
            archive_name = request.form.get("dataset")
            if not archive_name:
                flash("Выберите архив с заданиями для проверки.", "error")
                return redirect(url_for("main.room_detail", room_id=room.id))

            archive_path = uploads_dir / archive_name
            if not archive_path.exists():
                flash("Выбранный архив не найден.", "error")
                return redirect(url_for("main.room_detail", room_id=room.id))

            workspace_dir = storage / "workspace" / Path(archive_name).stem
            if workspace_dir.exists():
                shutil.rmtree(workspace_dir)

            try:
                _extract_zip_safe(archive_path, workspace_dir)
            except (ValueError, zipfile.BadZipFile) as err:
                flash(f"Не удалось распаковать архив: {err}", "error")
                return redirect(url_for("main.room_detail", room_id=room.id))

            if room.template_filename:
                template_path = templates_dir / room.template_filename
            else:
                template_path = Path(current_app.config["DEFAULT_TEMPLATE_PATH"])

            if not template_path.exists():
                flash("Файл шаблона для проверки не найден.", "error")
                return redirect(url_for("main.room_detail", room_id=room.id))

            try:
                summary_path = run_auto_checker(
                    root_dir=str(workspace_dir),
                    template_path=str(template_path),
                    room_prompt=room.prompt,
                )
            except Exception as err:  # noqa: BLE001
                current_app.logger.exception("Auto-checker failed")
                flash(f"Проверка завершилась с ошибкой: {err}", "error")
                return redirect(url_for("main.room_detail", room_id=room.id))

            if not summary_path or not Path(summary_path).exists():
                flash("Не удалось сформировать итоговый отчёт.", "error")
                return redirect(url_for("main.room_detail", room_id=room.id))

            reports_dir = storage / "reports"
            reports_dir.mkdir(parents=True, exist_ok=True)
            destination_report = reports_dir / Path(summary_path).name
            shutil.copy(summary_path, destination_report)

            return send_from_directory(
                reports_dir,
                destination_report.name,
                as_attachment=True,
                download_name=destination_report.name,
            )

    uploads = _list_files(uploads_dir)
    templates = _list_files(templates_dir)

    return render_template(
        "room.html",
        room=room,
        uploads=uploads,
        templates=templates,
        default_room_prompt=DEFAULT_ROOM_PROMPT,
        available_archives=[item["name"] for item in uploads],
    )


@bp.route("/rooms/<room_id>/uploads/<path:filename>")
def download_upload(room_id: str, filename: str):
    storage = _room_storage(room_id)
    return send_from_directory(storage / "uploads", filename, as_attachment=True)


@bp.route("/rooms/<room_id>/templates/<path:filename>")
def download_template(room_id: str, filename: str):
    storage = _room_storage(room_id)
    return send_from_directory(storage / "templates", filename, as_attachment=True)
def _extract_zip_safe(zip_path: Path, destination: Path) -> None:
    with zipfile.ZipFile(zip_path) as archive:
        destination.mkdir(parents=True, exist_ok=True)
        root = destination.resolve()
        for member in archive.infolist():
            target_path = (root / member.filename).resolve(strict=False)
            if not str(target_path).startswith(str(root)):
                raise ValueError("Обнаружена небезопасная структура архива.")
        archive.extractall(destination)
