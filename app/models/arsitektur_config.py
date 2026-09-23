from app import utcnow
from app import db


class ArsitekturConfig(db.Model):
    __tablename__ = 'arsitektur_config'

    id              = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nama            = db.Column(db.String(100), nullable=False)
    model_type      = db.Column(db.Enum('mobilenetv2', 'efficientnetb0'), nullable=False, default='mobilenetv2')
    input_size      = db.Column(db.Integer, nullable=False, default=224)
    learning_rate   = db.Column(db.Float, nullable=False, default=0.0001)
    batch_size      = db.Column(db.Integer, nullable=False, default=16)
    epochs          = db.Column(db.Integer, nullable=False, default=30)
    patience        = db.Column(db.SmallInteger, nullable=False, default=5)
    dropout_rate    = db.Column(db.Float, nullable=False, default=0.3)
    optimizer       = db.Column(db.Enum('adam', 'sgd', 'rmsprop'), nullable=False, default='adam')
    mixup_alpha     = db.Column(db.Float, nullable=False, default=0)  # 0 = nonaktif (default, tidak ubah perilaku lama)
    label_smoothing = db.Column(db.Float, nullable=False, default=0)  # 0 = nonaktif (default)
    dense_units     = db.Column(db.Integer, nullable=False, default=64)   # head Dense(units) — TODO.md P4
    dense_l2        = db.Column(db.Float, nullable=False, default=1e-4)   # L2 regularizer head — TODO.md P4
    skip_fine_tuning = db.Column(db.Boolean, nullable=False, default=False)  # Jalur A: backbone beku penuh — TODO.md P4
    split_config_id = db.Column(db.Integer, db.ForeignKey('split_config.id'), nullable=False)
    fold_val        = db.Column(db.SmallInteger, nullable=False, default=0)
    status          = db.Column(db.Enum('draft', 'training', 'selesai', 'gagal'), nullable=False, default='draft')
    model_path      = db.Column(db.String(500), nullable=True)
    final_model_path = db.Column(db.String(500), nullable=True)   # dilatih pada semua data
    pred_type       = db.Column(db.String(10), nullable=False, default='none')  # none | single | cv
    pengguna_id     = db.Column(db.Integer, db.ForeignKey('pengguna.id'), nullable=False)
    created_at      = db.Column(db.DateTime, default=utcnow)

    split_config  = db.relationship('SplitConfig', backref=db.backref('arsitektur_list', lazy=True, passive_deletes=True), lazy=True)
    pengguna      = db.relationship('Pengguna', backref='arsitektur_list', lazy=True)
    hasil_list    = db.relationship('HasilTraining', backref='arsitektur', lazy=True,
                                    cascade='all, delete-orphan')

    def __repr__(self):
        return f'<ArsitekturConfig {self.nama} {self.model_type}>'

