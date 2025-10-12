import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")

    instance_path = app.instance_path
    os.makedirs(instance_path, exist_ok=True)

    database_path = os.environ.get("DATABASE_PATH")
    if database_path:
        database_uri = f"sqlite:///{database_path}"
    else:
        database_file = os.path.join(instance_path, "auto_checker.db")
        database_uri = f"sqlite:///{database_file}"

    app.config["SQLALCHEMY_DATABASE_URI"] = database_uri
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    data_storage = os.environ.get("DATA_STORAGE") or os.path.join(instance_path, "data")
    os.makedirs(data_storage, exist_ok=True)
    app.config["DATA_STORAGE"] = data_storage

    db.init_app(app)

    from . import routes  # noqa: WPS433
    routes.init_app(app)

    with app.app_context():
        db.create_all()

    return app
