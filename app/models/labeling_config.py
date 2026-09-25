from app import db
from app import utcnow


class LabelingConfig(db.Model):
    __tablename__ = 'labeling_config'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nama_config = db.Column(db.String(100), nullable=False)
    n_cluster = db.Column(db.Integer, nullable=False, default=4)
    pca_komponen = db.Column(db.Integer, nullable=False, default=50)
    random_state = db.Column(db.Integer, nullable=False, default=42)
    canny_low = db.Column(db.Integer, nullable=False, default=50)
    canny_high = db.Column(db.Integer, nullable=False, default=150)
    is_default = db.Column(db.Boolean, nullable=False, default=False)
    pengguna_id = db.Column(db.Integer, db.ForeignKey('pengguna.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow)

    hasil_list = db.relationship(
        'HasilLabeling', backref='config', lazy=True, cascade='all, delete-orphan'
    )
    pengguna = db.relationship('Pengguna', backref='labeling_config_list', lazy=True)

    @classmethod
    def aktif(cls):
        from app.models.hasil_labeling import HasilLabeling

        terakhir = (
            HasilLabeling.query.filter_by(is_diterapkan=True)
            .order_by(HasilLabeling.id.desc())
            .first()
        )
        return (
            (terakhir.config if terakhir else None)
            or cls.query.filter_by(is_default=True).first()
            or cls.query.order_by(cls.id).first()
        )

    def __repr__(self):
        return f'<LabelingConfig {self.nama_config}>'
