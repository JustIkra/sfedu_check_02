import logging
import shutil
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from auto_checker import run_auto_checker

logger = logging.getLogger(__name__)


class ActiveJobError(Exception):
    """Raised when a room already has an active job."""

    def __init__(self, job_id: str) -> None:
        super().__init__("a job is already running for this room")
        self.job_id = job_id


@dataclass
class AutoCheckJob:
    """Background job responsible for executing auto-check runs."""

    room_id: str
    workspace_dir: Path
    template_path: Path
    reports_dir: Path
    room_prompt: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    status: str = field(default="queued")
    stage: str = field(default="queued")
    message: str = field(default="Задача поставлена в очередь")
    completed: int = field(default=0)
    total: int = field(default=0)
    progress: float = field(default=0.0)
    error: Optional[str] = field(default=None)
    download_name: Optional[str] = field(default=None)
    created_at: datetime = field(default_factory=datetime.utcnow)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
    _thread: Optional[threading.Thread] = field(default=None, init=False, repr=False)

    STAGE_MESSAGES = {
        "queued": "Задача поставлена в очередь",
        "collecting_submissions": "Анализ загруженных заданий",
        "processing_submissions": "Проверка работ",
        "generating_summary": "Формирование итогового отчёта",
        "finished": "Проверка завершена",
        "failed": "Проверка остановлена из-за ошибки",
    }

    def start(self) -> None:
        thread = threading.Thread(target=self._run, daemon=True)
        self._thread = thread
        thread.start()

    @property
    def is_active(self) -> bool:
        return self.status in {"queued", "running"}

    def snapshot(self) -> Dict[str, object]:
        with self._lock:
            return {
                "id": self.id,
                "status": self.status,
                "stage": self.stage,
                "message": self.message,
                "completed": self.completed,
                "total": self.total,
                "progress": self.progress,
                "error": self.error,
                "download_name": self.download_name,
                "result_ready": self.download_name is not None,
            }

    def _run(self) -> None:
        self._update_status(status="running", stage="collecting_submissions")
        try:
            summary_path = run_auto_checker(
                root_dir=str(self.workspace_dir),
                template_path=str(self.template_path),
                room_prompt=self.room_prompt,
                progress_callback=self._handle_progress_update,
            )

            if not summary_path:
                raise RuntimeError("Не удалось сформировать итоговый отчёт.")

            summary_file = Path(summary_path)
            if not summary_file.exists():
                raise FileNotFoundError(summary_file)

            self.reports_dir.mkdir(parents=True, exist_ok=True)
            # Генерируем уникальное имя, чтобы не затирать предыдущие отчёты
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            unique_name = f"{summary_file.stem}_{timestamp}_{self.id[:8]}{summary_file.suffix}"
            destination = self.reports_dir / unique_name
            shutil.copy(summary_file, destination)

            with self._lock:
                self.status = "finished"
                self.stage = "finished"
                self.message = self.STAGE_MESSAGES["finished"]
                self.completed = self.total or self.completed
                self.progress = 1.0
                self.download_name = destination.name
        except Exception as exc:  # noqa: BLE001
            logger.exception("Auto-check job %s failed", self.id)
            with self._lock:
                self.status = "failed"
                self.stage = "failed"
                self.message = self.STAGE_MESSAGES["failed"]
                self.error = str(exc)
        finally:
            if self.workspace_dir.exists():
                logger.debug("Job %s completed with status %s", self.id, self.status)

    def _handle_progress_update(self, stage: str, completed: int, total: int) -> None:
        with self._lock:
            self.stage = stage
            self.total = total
            self.completed = completed
            self.progress = (completed / total) if total else self.progress
            self.message = self.STAGE_MESSAGES.get(stage, self.message)

    def _update_status(self, *, status: Optional[str] = None, stage: Optional[str] = None) -> None:
        with self._lock:
            if status:
                self.status = status
            if stage:
                self.stage = stage
                self.message = self.STAGE_MESSAGES.get(stage, self.message)


class AutoCheckJobManager:
    """Registry for background auto-check jobs."""

    def __init__(self) -> None:
        self._jobs: Dict[str, AutoCheckJob] = {}
        self._lock = threading.Lock()

    def create_job(
        self,
        *,
        room_id: str,
        workspace_dir: Path,
        template_path: Path,
        reports_dir: Path,
        room_prompt: str,
    ) -> AutoCheckJob:
        with self._lock:
            for job in self._jobs.values():
                if job.room_id == room_id and job.is_active:
                    raise ActiveJobError(job.id)

            job = AutoCheckJob(
                room_id=room_id,
                workspace_dir=workspace_dir,
                template_path=template_path,
                reports_dir=reports_dir,
                room_prompt=room_prompt,
            )
            self._jobs[job.id] = job

        job.start()
        return job

    def get_job(self, job_id: str) -> Optional[AutoCheckJob]:
        with self._lock:
            return self._jobs.get(job_id)

    def active_job_for_room(self, room_id: str) -> Optional[AutoCheckJob]:
        with self._lock:
            for job in self._jobs.values():
                if job.room_id == room_id and job.is_active:
                    return job
        return None

    def latest_job_for_room(self, room_id: str) -> Optional[AutoCheckJob]:
        with self._lock:
            candidates = [job for job in self._jobs.values() if job.room_id == room_id]
        if not candidates:
            return None
        return max(candidates, key=lambda job: job.created_at)


job_manager = AutoCheckJobManager()
