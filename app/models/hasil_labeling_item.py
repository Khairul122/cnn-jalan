from app import db


class HasilLabelingItem(db.Model):
    __tablename__ = 'hasil_labeling_item'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    run_id = db.Column(
        db.Integer, db.ForeignKey('hasil_labeling.id', ondelete='CASCADE'), nullable=False
    )
    lokasi_id = db.Column(
        db.Integer, db.ForeignKey('lokasi_kerusakan.id', ondelete='CASCADE'), nullable=False
    )
    klaster = db.Column(db.Integer, nullable=False)
    kepadatan_tepi = db.Column(db.Numeric(6, 4), nullable=False)
    jarak_centroid = db.Column(db.Numeric(10, 4), nullable=True)
    tingkat_kerusakan_id = db.Column(
        db.Integer, db.ForeignKey('tingkat_kerusakan.id'), nullable=False
    )

    lokasi = db.relationship('LokasiKerusakan', lazy=True)
    tingkat = db.relationship('TingkatKerusakan', lazy=True)

    def __repr__(self):
        return f'<HasilLabelingItem lokasi={self.lokasi_id} klaster={self.klaster}>'
