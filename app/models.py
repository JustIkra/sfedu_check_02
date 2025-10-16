from datetime import datetime
from typing import Optional

from . import db


class Room(db.Model):
    __tablename__ = "rooms"

    id: str = db.Column(db.String(36), primary_key=True)
    name: str = db.Column(db.String(255), nullable=False)
    description: Optional[str] = db.Column(db.Text, nullable=True)
    check_prompt: str = db.Column(db.Text, nullable=False)
    task_prompt: str = db.Column(db.Text, nullable=False)
    template_filename: Optional[str] = db.Column(db.String(255), nullable=True)
    ai_check_enabled: bool = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<Room {self.id} {self.name}>"

    @property
    def prompt(self) -> str:
        """Единый человеко-понятный промпт для комнаты."""

        return self.check_prompt

    @prompt.setter
    def prompt(self, value: str) -> None:
        """Сохраняет новое значение во всех связанных полях."""

        self.check_prompt = value
        self.task_prompt = value
