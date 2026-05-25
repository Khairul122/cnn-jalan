from app import db


class HasilTraining(db.Model):
    __tablename__ = 'hasil_training'

    id            = db.Column(db.Integer, primary_key=True, autoincrement=True)
    arsitektur_id = db.Column(db.Integer, db.ForeignKey('arsitektur_config.id', ondelete='CASCADE'), nullable=False)
    epoch         = db.Column(db.Integer, nullable=False)
    loss          = db.Column(db.Float, nullable=False)
    accuracy      = db.Column(db.Float, nullable=False)
    val_loss      = db.Column(db.Float, nullable=False)
    val_accuracy  = db.Column(db.Float, nullable=False)

    def __repr__(self):
        return f'<HasilTraining arsitektur={self.arsitektur_id} epoch={self.epoch}>'
