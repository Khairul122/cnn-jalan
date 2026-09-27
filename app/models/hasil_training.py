from app import db


class HasilTraining(db.Model):
    __tablename__ = 'hasil_training'

    id            = db.Column(db.Integer, primary_key=True, autoincrement=True)
    arsitektur_id = db.Column(db.Integer, db.ForeignKey('arsitektur_config.id', ondelete='CASCADE'), nullable=False)
    fold_index    = db.Column(db.Integer, nullable=True)  # 0-based, NULL = legacy single-fold
    epoch         = db.Column(db.Integer, nullable=False)
    loss          = db.Column(db.Float, nullable=False)
    accuracy      = db.Column(db.Float, nullable=False)
    val_loss      = db.Column(db.Float, nullable=False)
    val_accuracy  = db.Column(db.Float, nullable=False)

    def __repr__(self):
        return f'<HasilTraining arsitektur={self.arsitektur_id} fold={self.fold_index} epoch={self.epoch}>'
