import json

from app import utcnow
from app import db

from app.kelas import LABEL as LABEL_MAP, WARNA as WARNA_MAP


class PrediksiModel(db.Model):
    __tablename__ = 'prediksi_model'

    id             = db.Column(db.Integer, primary_key=True, autoincrement=True)
    arsitektur_id  = db.Column(db.Integer, db.ForeignKey('arsitektur_config.id', ondelete='CASCADE'), nullable=False)
    dokumentasi_id = db.Column(db.Integer, db.ForeignKey('dokumentasi_foto.id', ondelete='CASCADE'), nullable=False)
    prediksi       = db.Column(db.SmallInteger, nullable=False)
    aktual         = db.Column(db.SmallInteger, nullable=True)
    confidence     = db.Column(db.Float, nullable=False)
    probabilitas   = db.Column(db.Text, nullable=True)   # JSON [p_kelas0..p_kelas3]; NULL = prediksi lama
    created_at     = db.Column(db.DateTime, default=utcnow)

    arsitektur  = db.relationship('ArsitekturConfig', backref=db.backref('prediksi_list', cascade='all, delete-orphan'))
    dokumentasi = db.relationship('DokumentasiFoto')

    @classmethod
    def dari_hasil(cls, arsitektur_id, r):
        """Baris dari dict hasil cnn_service.predict_* ({dokumentasi_id, prediksi, aktual, confidence, probabilitas})."""
        return cls(arsitektur_id=arsitektur_id, dokumentasi_id=r['dokumentasi_id'], prediksi=r['prediksi'],
                   aktual=r['aktual'], confidence=r['confidence'],
                   probabilitas=json.dumps(r['probabilitas']) if r.get('probabilitas') is not None else None)

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

