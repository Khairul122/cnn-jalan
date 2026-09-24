import json
from app import utcnow
from app import db


class HasilEvaluasi(db.Model):
    __tablename__ = 'hasil_evaluasi'

    id               = db.Column(db.Integer, primary_key=True, autoincrement=True)
    arsitektur_id    = db.Column(db.Integer, db.ForeignKey('arsitektur_config.id', ondelete='CASCADE'), nullable=False)
    total_data_val   = db.Column(db.Integer, nullable=False)
    akurasi          = db.Column(db.Float, nullable=False)
    confusion_matrix = db.Column(db.Text, nullable=False)
    per_class        = db.Column(db.Text, nullable=False)   # JSON {kelas_key: {precision, recall, f1-score}}
    macro_precision  = db.Column(db.Float, nullable=False)
    macro_recall     = db.Column(db.Float, nullable=False)
    macro_f1         = db.Column(db.Float, nullable=False)
    created_at       = db.Column(db.DateTime, default=utcnow)

    arsitektur = db.relationship('ArsitekturConfig', backref=db.backref('evaluasi_list', cascade='all, delete-orphan'))

    def get_cm(self):
        return json.loads(self.confusion_matrix)

    def get_per_class(self):
        return json.loads(self.per_class)

