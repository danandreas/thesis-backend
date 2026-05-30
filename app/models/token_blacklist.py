from datetime import datetime
from app import db


class TokenBlacklist(db.Model):
    """
    Menyimpan token yang sudah di-logout/revoke sebelum expired.
    Token di sini tidak akan bisa dipakai lagi meskipun belum expired.

    Cara kerja:
    - Saat logout, JWT identifier (jti) disimpan ke tabel ini
    - Setiap request, middleware cek apakah jti ada di blacklist
    - Jika ada → tolak request (401)
    - Record lama (sudah melewati expires_at) bisa di-cleanup otomatis
    """
    __tablename__ = 'token_blacklist'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    jti = db.Column(db.String(36), unique=True, nullable=False, index=True)  # JWT ID
    token_type = db.Column(db.String(20), nullable=False, default='access')  # access / refresh
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    revoked_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    @classmethod
    def is_revoked(cls, jti: str) -> bool:
        """Cek apakah token sudah di-blacklist."""
        return db.session.query(
            cls.query.filter_by(jti=jti).exists()
        ).scalar()

    @classmethod
    def revoke(cls, jti: str, user_id: int, token_type: str, expires_at: datetime):
        """Tambahkan token ke blacklist."""
        entry = cls(
            jti=jti,
            user_id=user_id,
            token_type=token_type,
            expires_at=expires_at,
        )
        db.session.add(entry)
        db.session.commit()

    @classmethod
    def revoke_all_for_user(cls, user_id: int):
        """Revoke semua token milik user (logout dari semua device)."""
        cls.query.filter_by(user_id=user_id).delete()
        db.session.commit()

    @classmethod
    def cleanup_expired(cls):
        """Hapus record yang sudah melewati expires_at (untuk maintenance)."""
        now = datetime.utcnow()
        deleted = cls.query.filter(cls.expires_at < now).delete()
        db.session.commit()
        return deleted

    def __repr__(self):
        return f"<TokenBlacklist jti={self.jti} user_id={self.user_id}>"
