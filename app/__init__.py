from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from config import Config

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()

login_manager.login_view = 'auth.login'
login_manager.login_message = 'Silakan login terlebih dahulu.'
login_manager.login_message_category = 'warning'


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)

    from app.controllers.auth_controller import auth_bp
    from app.controllers.dashboard_controller import dashboard_bp
    from app.controllers.lokasi_controller import lokasi_bp
    from app.controllers.peta_controller import peta_bp
    from app.controllers.klasifikasi_controller import klasifikasi_bp
    from app.controllers.evaluasi_controller import evaluasi_bp
    from app.controllers.label_controller import label_bp
    from app.controllers.preprocessing_controller import preprocessing_bp
    from app.controllers.split_controller import split_bp
    from app.controllers.arsitektur_controller import arsitektur_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(lokasi_bp)
    app.register_blueprint(peta_bp)
    app.register_blueprint(klasifikasi_bp)
    app.register_blueprint(evaluasi_bp)
    app.register_blueprint(label_bp)
    app.register_blueprint(preprocessing_bp)
    app.register_blueprint(split_bp)
    app.register_blueprint(arsitektur_bp)

    return app
