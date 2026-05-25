from datetime import datetime
from app import db

LABEL_MAP = {0: 'Berat', 1: 'Sedang', 2: 'Ringan'}
WARNA_MAP = {0: '#E53E3E', 1: '#F59E0B', 2: '#10B981'}


class PrediksiModel(db.Model):
    __tablename__ = 'prediksi_model'

    id             = db.Column(db.Integer, primary_key=True, autoincrement=True)
    arsitektur_id  = db.Column(db.Integer, db.ForeignKey('arsitektur_config.id', ondelete='CASCADE'), nullable=False)
    dokumentasi_id = db.Column(db.Integer, db.ForeignKey('dokumentasi_foto.id', ondelete='CASCADE'), nullable=False)
    prediksi       = db.Column(db.SmallInteger, nullable=False)
    aktual         = db.Column(db.SmallInteger, nullable=True)
    confidence     = db.Column(db.Float, nullable=False)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)

    arsitektur  = db.relationship('ArsitekturConfig', backref=db.backref('prediksi_list', cascade='all, delete-orphan'))
    dokumentasi = db.relationship('DokumentasiFoto')

    @property
    def label_prediksi(self):
        return LABEL_MAP.get(self.prediksi, '?')

    @property
    def label_aktual(self):
        return LABEL_MAP.get(self.aktual, '?')

    @property
    def warna(self):
        return WARNA_MAP.get(self.prediksi, '#999')

    @property
    def benar(self):
        return self.aktual is not None and self.prediksi == self.aktual
