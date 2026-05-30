import bcrypt
from app import db
from app.models.base import BaseModel


class User(BaseModel):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(200), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    address = db.Column(db.Text, nullable=True)
    force_logout_at = db.Column(db.DateTime, nullable=True, default=None)
    # Saat force_logout_at di-set, semua token yang diterbitkan SEBELUM waktu ini
    # akan ditolak oleh middleware — efeknya logout dari semua device.

    def set_password(self, plain_password: str):
        """Hash and set password."""
        hashed = bcrypt.hashpw(plain_password.encode('utf-8'), bcrypt.gensalt())
        self.password = hashed.decode('utf-8')

    def check_password(self, plain_password: str) -> bool:
        """Verify plain password against hashed."""
        return bcrypt.checkpw(
            plain_password.encode('utf-8'),
            self.password.encode('utf-8')
        )

    def to_dict(self, exclude: list = None):
        """Override to exclude password by default."""
        exclude = exclude or []
        if 'password' not in exclude:
            exclude.append('password')
        data = super().to_dict(exclude=exclude)
        # Include role info if loaded
        if self.role:
            data['role'] = self.role.to_dict()
        return data

    def is_admin(self) -> bool:
        return self.role and self.role.code == 'admin'

    def __repr__(self):
        return f"<User {self.email}>"
