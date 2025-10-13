import os
import shutil
import uuid
import zipfile
from datetime import timezone
from pathlib import Path
from unicodedata import normalize
from zoneinfo import ZoneInfo

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from werkzeug.utils import secure_filename
from .default_prompts import DEFAULT_ROOM_PROMPT
from .models import Room
from . import db
from .background import ActiveJobError, job_manager


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


def _preserve_upload_name(original_name: str, allowed_suffixes: set[str], fallback: str) -> str:
    """Return a safe filename while keeping the original Unicode characters."""

    candidate = Path(original_name or "").name
    candidate = normalize("NFC", candidate.replace("\x00", ""))
    candidate = candidate.replace("/", "_").replace("\\", "_").strip()

    if not candidate or candidate in {".", ".."}:
        candidate = fallback

    suffix = Path(candidate).suffix.lower()
    if suffix not in allowed_suffixes:
        raise ValueError(suffix)

    return candidate


def _workspace_slug(filename: str, fallback: str = "archive") -> str:
    stem = Path(filename or "").stem
    stem = normalize("NFC", stem.replace("\x00", ""))
    stem = stem.replace("/", "_").replace("\\", "_").strip()

    if not stem or stem in {".", ".."}:
        ascii_fallback = secure_filename(Path(filename or "").stem)
        return ascii_fallback or fallback

    return stem


_MOSCOW_TZ = ZoneInfo("Europe/Moscow")


def _format_moscow(dt):
    if dt is None:
        return ""
    aware = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    localised = aware.astimezone(_MOSCOW_TZ)
    return localised.strftime("%d.%m.%Y %H:%M")


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
        format_moscow=_format_moscow,
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
            original_name = file.filename if file else ""
            if not file or not original_name:
                flash("Выберите zip-файл для загрузки.", "error")
            else:
                try:
                    filename = _preserve_upload_name(original_name, {".zip"}, "archive.zip")
                except ValueError:
                    flash("Разрешена загрузка только .zip файлов.", "error")
                else:
                    safe_stem = secure_filename(source_path.stem) or "archive"
                    filename = f"{safe_stem}.zip"
                    destination = uploads_dir / filename
                    file.save(destination)
                    flash("Архив с заданиями загружен.", "success")
            return redirect(url_for("main.room_detail", room_id=room.id))

        if action == "upload_template":
            template_file = request.files.get("template_file")
            original_name = template_file.filename if template_file else ""
            if not template_file or not original_name:
                flash("Выберите файл шаблона для загрузки.", "error")
            else:
                try:
                    filename = _preserve_upload_name(
                        original_name,
                        {".docx"},
                        "template.docx",
                    )
                except ValueError:
                    flash("Поддерживаются только файлы .docx.", "error")
                    return redirect(url_for("main.room_detail", room_id=room.id))

                destination = templates_dir / filename
                template_file.save(destination)
                room.template_filename = filename
                db.session.commit()
                flash("Шаблон сохранён для комнаты.", "success")
            return redirect(url_for("main.room_detail", room_id=room.id))

    uploads = _list_files(uploads_dir)
    templates = _list_files(templates_dir)
    latest_job = job_manager.latest_job_for_room(room.id)

    return render_template(
        "room.html",
        room=room,
        uploads=uploads,
        templates=templates,
        default_room_prompt=DEFAULT_ROOM_PROMPT,
        available_archives=[item["name"] for item in uploads],
        latest_job_id=latest_job.id if latest_job else None,
        format_moscow=_format_moscow,
    )


@bp.route("/rooms/<room_id>/uploads/<path:filename>")
def download_upload(room_id: str, filename: str):
    storage = _room_storage(room_id)
    return send_from_directory(storage / "uploads", filename, as_attachment=True)


@bp.route("/rooms/<room_id>/templates/<path:filename>")
def download_template(room_id: str, filename: str):
    storage = _room_storage(room_id)
    return send_from_directory(storage / "templates", filename, as_attachment=True)


@bp.post("/rooms/<room_id>/auto-check")
def start_auto_check(room_id: str):
    room = Room.query.get_or_404(room_id)
    storage = _room_storage(room_id)
    uploads_dir = storage / "uploads"
    templates_dir = storage / "templates"

    is_async = request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest"
    payload = request.get_json(silent=True) if request.is_json else None
    dataset = (payload or {}).get("dataset") if payload else request.form.get("dataset")
    dataset = (dataset or "").strip()

    if not dataset:
        message = "Выберите архив с заданиями для проверки."
        if is_async:
            return jsonify({"error": message}), 400
        flash(message, "error")
        return redirect(url_for("main.room_detail", room_id=room.id))

    archive_path = uploads_dir / dataset
    if not archive_path.exists():
        message = "Выбранный архив не найден."
        if is_async:
            return jsonify({"error": message}), 404
        flash(message, "error")
        return redirect(url_for("main.room_detail", room_id=room.id))

    if room.template_filename:
        template_path = templates_dir / room.template_filename
    else:
        template_path = Path(current_app.config["DEFAULT_TEMPLATE_PATH"])

    if not template_path.exists():
        message = "Файл шаблона для проверки не найден."
        if is_async:
            return jsonify({"error": message}), 404
        flash(message, "error")
        return redirect(url_for("main.room_detail", room_id=room.id))

    active_job = job_manager.active_job_for_room(room.id)
    if active_job:
        message = "Проверка уже выполняется для этой комнаты."
        if is_async:
            return jsonify({"error": message, "job_id": active_job.id}), 409
        flash(message, "info")
        return redirect(url_for("main.room_detail", room_id=room.id))

    workspace_dir = storage / "workspace" / _workspace_slug(dataset)
    if workspace_dir.exists():
        shutil.rmtree(workspace_dir)

    try:
        _extract_zip_safe(archive_path, workspace_dir)
    except (ValueError, zipfile.BadZipFile) as err:
        shutil.rmtree(workspace_dir, ignore_errors=True)
        message = f"Не удалось распаковать архив: {err}"
        if is_async:
            return jsonify({"error": message}), 400
        flash(message, "error")
        return redirect(url_for("main.room_detail", room_id=room.id))

    reports_dir = storage / "reports"

    try:
        job = job_manager.create_job(
            room_id=room.id,
            workspace_dir=workspace_dir,
            template_path=template_path,
            reports_dir=reports_dir,
            room_prompt=room.prompt or DEFAULT_ROOM_PROMPT,
        )
    except ActiveJobError as exc:
        message = "Проверка уже выполняется для этой комнаты."
        if is_async:
            return jsonify({"error": message, "job_id": exc.job_id}), 409
        flash(message, "info")
        return redirect(url_for("main.room_detail", room_id=room.id))

    if is_async:
        return jsonify({"job_id": job.id}), 202

    flash("Проверка запущена. Прогресс отображается ниже.", "info")
    return redirect(url_for("main.room_detail", room_id=room.id))


@bp.get("/rooms/<room_id>/auto-check/<job_id>")
def auto_check_status(room_id: str, job_id: str):
    job = job_manager.get_job(job_id)
    if job is None or job.room_id != room_id:
        abort(404)
    return jsonify(job.snapshot())


@bp.get("/rooms/<room_id>/auto-check/<job_id>/download")
def auto_check_download(room_id: str, job_id: str):
    job = job_manager.get_job(job_id)
    if job is None or job.room_id != room_id:
        abort(404)
    if job.status != "finished" or not job.download_name:
        abort(400)
    return send_from_directory(
        str(job.reports_dir),
        job.download_name,
        as_attachment=True,
        download_name=job.download_name,
    )
def _extract_zip_safe(zip_path: Path, destination: Path) -> None:
    with zipfile.ZipFile(zip_path) as archive:
        destination.mkdir(parents=True, exist_ok=True)
        root = destination.resolve()
        for member in archive.infolist():
            target_path = (root / member.filename).resolve(strict=False)
            if not str(target_path).startswith(str(root)):
                raise ValueError("Обнаружена небезопасная структура архива.")
        archive.extractall(destination)
