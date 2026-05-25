from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db, login_manager


class Pengguna(UserMixin, db.Model):
    __tablename__ = 'pengguna'

    id            = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nama          = db.Column(db.String(100), nullable=False)
    email         = db.Column(db.String(150), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role          = db.Column(db.Enum('admin', 'viewer'), nullable=False, default='viewer')
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

    lokasi_list = db.relationship('LokasiKerusakan', backref='pengguna', lazy=True)
    peta_list   = db.relationship('PetaKerusakan', backref='pengguna', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_admin(self):
        return self.role == 'admin'

    def __repr__(self):
        return f'<Pengguna {self.email}>'


@login_manager.user_loader
def load_user(user_id):
    return Pengguna.query.get(int(user_id))
