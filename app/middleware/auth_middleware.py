from functools import wraps
from datetime import datetime, timezone
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity, get_jwt
from app.models.user import User
from app.helpers.response import unauthorized_response, forbidden_response


def _check_force_logout(user, jwt_data: dict) -> bool:
    """
    Cek apakah token diterbitkan sebelum force_logout_at.
    Jika iya, token dianggap tidak valid (user sudah logout semua device).
    """
    if not user.force_logout_at:
        return False
    # 'iat' = issued at (unix timestamp) — kapan token diterbitkan
    issued_at = jwt_data.get('iat')
    if not issued_at:
        return False
    token_issued_at = datetime.fromtimestamp(issued_at, tz=timezone.utc).replace(tzinfo=None)
    return token_issued_at < user.force_logout_at


def auth_required(fn):
    """
    Middleware: wajib bearer token valid + belum di-blacklist.
    Flask-JWT-Extended otomatis cek blacklist via token_in_blocklist_loader.
    Middleware ini tambahan cek force_logout_at untuk 'logout all devices'.
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            verify_jwt_in_request()
        except Exception:
            return unauthorized_response("Token tidak valid atau sudah kadaluarsa.")

        # Cek force_logout_at
        user_id = get_jwt_identity()
        jwt_data = get_jwt()
        user = User.find(user_id)
        if not user:
            return unauthorized_response("User tidak ditemukan.")
        if _check_force_logout(user, jwt_data):
            return unauthorized_response("Sesi telah berakhir. Silakan login kembali.")

        return fn(*args, **kwargs)
    return wrapper


def admin_required(fn):
    """Middleware: wajib token valid + role admin + cek force_logout_at."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            verify_jwt_in_request()
        except Exception:
            return unauthorized_response("Token tidak valid atau sudah kadaluarsa.")

        user_id = get_jwt_identity()
        jwt_data = get_jwt()
        user = User.find(user_id)

        if not user:
            return unauthorized_response("User tidak ditemukan.")

        if _check_force_logout(user, jwt_data):
            return unauthorized_response("Sesi telah berakhir. Silakan login kembali.")

        if not user.is_admin():
            return forbidden_response("Hanya admin yang dapat mengakses endpoint ini.")

        return fn(*args, **kwargs)
    return wrapper


def get_current_user():
    """Helper: ambil user yang sedang login dari token."""
    user_id = get_jwt_identity()
    return User.find(user_id)


def get_jwt_claims():
    """Helper: ambil seluruh data JWT (termasuk jti, exp, iat, dll)."""
    return get_jwt()
