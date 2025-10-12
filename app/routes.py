import os
import uuid
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

from .default_prompts import DEFAULT_CHECK_PROMPT, DEFAULT_TASK_PROMPT
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
                check_prompt=DEFAULT_CHECK_PROMPT,
                task_prompt=DEFAULT_TASK_PROMPT,
            )
            db.session.add(room)
            db.session.commit()
            flash("Комната успешно создана.", "success")
            return redirect(url_for("main.room_detail", room_id=room.id))

    rooms = Room.query.order_by(Room.created_at.desc()).all()
    return render_template(
        "index.html",
        rooms=rooms,
        default_check_prompt=DEFAULT_CHECK_PROMPT,
        default_task_prompt=DEFAULT_TASK_PROMPT,
    )


@bp.route("/rooms/<room_id>", methods=["GET", "POST"])
def room_detail(room_id: str):
    room = Room.query.get_or_404(room_id)
    storage = _room_storage(room_id)
    uploads_dir = storage / "uploads"
    templates_dir = storage / "templates"

    if request.method == "POST":
        action = request.form.get("action")

        if action == "update_prompts":
            room.check_prompt = request.form.get("check_prompt", room.check_prompt)
            room.task_prompt = request.form.get("task_prompt", room.task_prompt)
            db.session.commit()
            flash("Промпты обновлены только для этой комнаты.", "success")
            return redirect(url_for("main.room_detail", room_id=room.id))

        if action == "reset_prompts":
            room.check_prompt = DEFAULT_CHECK_PROMPT
            room.task_prompt = DEFAULT_TASK_PROMPT
            db.session.commit()
            flash("Промпты комнаты сброшены к шаблону.", "info")
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

    uploads = _list_files(uploads_dir)
    templates = _list_files(templates_dir)

    return render_template(
        "room.html",
        room=room,
        uploads=uploads,
        templates=templates,
        default_check_prompt=DEFAULT_CHECK_PROMPT,
        default_task_prompt=DEFAULT_TASK_PROMPT,
    )


@bp.route("/rooms/<room_id>/uploads/<path:filename>")
def download_upload(room_id: str, filename: str):
    storage = _room_storage(room_id)
    return send_from_directory(storage / "uploads", filename, as_attachment=True)


@bp.route("/rooms/<room_id>/templates/<path:filename>")
def download_template(room_id: str, filename: str):
    storage = _room_storage(room_id)
    return send_from_directory(storage / "templates", filename, as_attachment=True)
