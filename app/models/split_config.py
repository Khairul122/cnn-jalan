from datetime import datetime
from app import db


class SplitConfig(db.Model):
    __tablename__ = 'split_config'

    id           = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nama         = db.Column(db.String(100), nullable=False)
    split_type   = db.Column(db.String(10), nullable=False, default='kfold')
    n_splits     = db.Column(db.Integer, nullable=False, default=5)
    random_state = db.Column(db.Integer, nullable=False, default=42)
    label_sumber = db.Column(db.Enum('tingkat', 'jenis'), nullable=False, default='tingkat')
    total_data   = db.Column(db.Integer, nullable=False, default=0)
    pengguna_id  = db.Column(db.Integer, db.ForeignKey('pengguna.id'), nullable=False)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)

    items    = db.relationship('SplitItem', backref='config', lazy=True, cascade='all, delete-orphan')
    pengguna = db.relationship('Pengguna', backref='split_config_list', lazy=True)

    def __repr__(self):
        return f'<SplitConfig {self.nama} K={self.n_splits}>'
