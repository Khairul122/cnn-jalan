import json
from datetime import datetime
from app import db


class HasilEvaluasi(db.Model):
    __tablename__ = 'hasil_evaluasi'

    id               = db.Column(db.Integer, primary_key=True, autoincrement=True)
    arsitektur_id    = db.Column(db.Integer, db.ForeignKey('arsitektur_config.id', ondelete='CASCADE'), nullable=False)
    total_data_val   = db.Column(db.Integer, nullable=False)
    akurasi          = db.Column(db.Float, nullable=False)
    confusion_matrix = db.Column(db.Text, nullable=False)
    precision_berat  = db.Column(db.Float, nullable=False)
    recall_berat     = db.Column(db.Float, nullable=False)
    f1_berat         = db.Column(db.Float, nullable=False)
    precision_sedang = db.Column(db.Float, nullable=False)
    recall_sedang    = db.Column(db.Float, nullable=False)
    f1_sedang        = db.Column(db.Float, nullable=False)
    precision_ringan = db.Column(db.Float, nullable=False)
    recall_ringan    = db.Column(db.Float, nullable=False)
    f1_ringan        = db.Column(db.Float, nullable=False)
    macro_precision  = db.Column(db.Float, nullable=False)
    macro_recall     = db.Column(db.Float, nullable=False)
    macro_f1         = db.Column(db.Float, nullable=False)
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)

    arsitektur = db.relationship('ArsitekturConfig', backref=db.backref('evaluasi_list', cascade='all, delete-orphan'))

    def get_cm(self):
        return json.loads(self.confusion_matrix)
