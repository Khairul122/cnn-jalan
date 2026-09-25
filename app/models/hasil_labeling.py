from app import db
from app import utcnow


class HasilLabeling(db.Model):
    __tablename__ = 'hasil_labeling'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    config_id = db.Column(db.Integer, db.ForeignKey('labeling_config.id'), nullable=False)
    jumlah_lokasi = db.Column(db.Integer, nullable=False, default=0)
    jumlah_dilewati = db.Column(db.Integer, nullable=False, default=0)
    variansi_pca = db.Column(db.Numeric(5, 4), nullable=True)
    distribusi_kelas = db.Column(db.Text, nullable=True)
    status = db.Column(db.Enum('selesai', 'gagal'), nullable=False, default='selesai')
    catatan = db.Column(db.Text, nullable=True)
    is_diterapkan = db.Column(db.Boolean, nullable=False, default=False)
    diterapkan_at = db.Column(db.DateTime, nullable=True)
    pengguna_id = db.Column(db.Integer, db.ForeignKey('pengguna.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow)

    item_list = db.relationship(
        'HasilLabelingItem', backref='run', lazy=True, cascade='all, delete-orphan'
    )
    pengguna = db.relationship('Pengguna', backref='hasil_labeling_list', lazy=True)

    def __repr__(self):
        return (
            f'<HasilLabeling config={self.config_id} '
            f'status={self.status} diterapkan={self.is_diterapkan}>'
        )
