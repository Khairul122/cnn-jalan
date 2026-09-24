from flask import Flask, flash, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFError, CSRFProtect
from datetime import datetime, timezone
from config import Config

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()
csrf = CSRFProtect()


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)

login_manager.login_view = 'auth.login'
login_manager.login_message = 'Silakan login terlebih dahulu.'
login_manager.login_message_category = 'warning'


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    from app.controllers.auth_controller import auth_bp
    from app.controllers.dashboard_controller import dashboard_bp
    from app.controllers.lokasi_controller import lokasi_bp
    from app.controllers.peta_controller import peta_bp
    from app.controllers.klasifikasi_controller import klasifikasi_bp
    from app.controllers.evaluasi_controller import evaluasi_bp
    from app.controllers.label_controller import label_bp
    from app.controllers.preprocessing_controller import preprocessing_bp
    from app.controllers.augmentasi_controller import augmentasi_bp
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
    app.register_blueprint(augmentasi_bp)
    app.register_blueprint(split_bp)
    app.register_blueprint(arsitektur_bp)

    @app.context_processor
    def inject_kelas():
        from app import kelas
        return {'KELAS': kelas.KELAS, 'KELAS_WARNA': kelas.WARNA_NAMA}

    @app.errorhandler(403)
    def forbidden(_):
        flash('Anda tidak memiliki izin untuk aksi ini. Hubungi admin.', 'danger')
        return redirect(url_for('dashboard.index'))

    @app.errorhandler(CSRFError)
    def csrf_error(_):
        flash('Sesi form kedaluwarsa atau tidak valid. Muat ulang halaman lalu coba lagi.', 'warning')
        return redirect(url_for('dashboard.index'))

    return app
