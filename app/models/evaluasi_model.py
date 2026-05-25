from datetime import datetime
from app import db


class EvaluasiModel(db.Model):
    __tablename__ = 'evaluasi_model'

    id                 = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nama_model         = db.Column(db.String(100), nullable=False)
    versi              = db.Column(db.String(20), nullable=False)
    total_data_uji     = db.Column(db.Integer, nullable=False)
    akurasi            = db.Column(db.Float, nullable=False)
    presisi            = db.Column(db.Float, nullable=False)
    recall             = db.Column(db.Float, nullable=False)
    f1_score           = db.Column(db.Float, nullable=False)
    cross_entropy_loss = db.Column(db.Float, nullable=False)
    tp                 = db.Column(db.Integer, nullable=False)
    fp                 = db.Column(db.Integer, nullable=False)
    tn                 = db.Column(db.Integer, nullable=False)
    fn                 = db.Column(db.Integer, nullable=False)
    catatan            = db.Column(db.Text, nullable=True)
    created_at         = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<EvaluasiModel {self.nama_model} v{self.versi} acc={self.akurasi}>'
