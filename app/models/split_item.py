from datetime import datetime
from app import db


class SplitItem(db.Model):
    __tablename__ = 'split_item'

    id                   = db.Column(db.Integer, primary_key=True, autoincrement=True)
    config_id            = db.Column(db.Integer, db.ForeignKey('split_config.id', ondelete='CASCADE'), nullable=False)
    dokumentasi_id       = db.Column(db.Integer, db.ForeignKey('dokumentasi_foto.id', ondelete='CASCADE'), nullable=False)
    tingkat_kerusakan_id = db.Column(db.Integer, db.ForeignKey('tingkat_kerusakan.id'), nullable=False)
    fold_index           = db.Column(db.SmallInteger, nullable=False)
    created_at           = db.Column(db.DateTime, default=datetime.utcnow)

    dokumentasi = db.relationship('DokumentasiFoto', backref='split_list', lazy=True)
    tingkat     = db.relationship('TingkatKerusakan', backref='split_list', lazy=True)

    def __repr__(self):
        return f'<SplitItem doc={self.dokumentasi_id} fold={self.fold_index}>'
