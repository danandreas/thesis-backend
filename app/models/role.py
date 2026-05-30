from app import db
from app.models.base import BaseModel


class Role(BaseModel):
    __tablename__ = 'roles'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)

    # Relationship
    users = db.relationship('User', backref='role', lazy='dynamic')

    def to_dict(self, exclude: list = None):
        return super().to_dict(exclude=exclude or [])

    def __repr__(self):
        return f"<Role {self.code}>"
