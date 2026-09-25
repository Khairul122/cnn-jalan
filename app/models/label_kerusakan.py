from app import db
from app import utcnow


class LabelKerusakan(db.Model):
    __tablename__ = 'label_kerusakan'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    lokasi_id = db.Column(
        db.Integer,
        db.ForeignKey('lokasi_kerusakan.id', ondelete='CASCADE'),
        nullable=False,
        unique=True,
    )
    tingkat_kerusakan_id = db.Column(
        db.Integer, db.ForeignKey('tingkat_kerusakan.id'), nullable=False
    )
    metode = db.Column(
        db.Enum('klasterisasi', 'manual'), nullable=False, default='klasterisasi'
    )
    cluster_id = db.Column(db.Integer, nullable=True)
    kepadatan_tepi = db.Column(db.Numeric(6, 4), nullable=True)
    jarak_centroid = db.Column(db.Numeric(10, 4), nullable=True)
    hasil_labeling_id = db.Column(
        db.Integer, db.ForeignKey('hasil_labeling.id', ondelete='SET NULL'), nullable=True
    )
    catatan = db.Column(db.Text, nullable=True)
    pengguna_id = db.Column(db.Integer, db.ForeignKey('pengguna.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    tingkat = db.relationship('TingkatKerusakan', backref='label_list', lazy=True)
    pengguna = db.relationship('Pengguna', backref='label_list', lazy=True)

    def __repr__(self):
        return (
            f'<LabelKerusakan lokasi={self.lokasi_id} '
            f'tingkat={self.tingkat_kerusakan_id} metode={self.metode}>'
        )
