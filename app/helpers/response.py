from flask import jsonify


def api_response(success: bool = True, message: str = "OK", code: int = 200, data=None, **kwargs):
    """
    Standard API response format.

    Usage:
        api_response(success=True, message="Data fetched", data=[...])
        api_response(success=False, message="Not found", code=404)
        api_response(success=True, message="Deleted successfully")  # no data key
    """
    payload = {
        "code": code,
        "success": success,
        "message": message,
    }

    # Only include data key if data is explicitly provided (not None)
    if data is not None:
        payload["data"] = data

    # Include any extra kwargs (e.g., pagination meta)
    payload.update(kwargs)

    return jsonify(payload), code


def success_response(message: str = "Berhasil", data=None, code: int = 200, **kwargs):
    return api_response(success=True, message=message, code=code, data=data, **kwargs)


def created_response(message: str = "Data berhasil dibuat", data=None, **kwargs):
    return api_response(success=True, message=message, code=201, data=data, **kwargs)


def error_response(message: str = "Terjadi kesalahan", code: int = 400, data=None, **kwargs):
    return api_response(success=False, message=message, code=code, data=data, **kwargs)


def not_found_response(message: str = "Data tidak ditemukan"):
    return api_response(success=False, message=message, code=404)


def unauthorized_response(message: str = "Tidak terotorisasi"):
    return api_response(success=False, message=message, code=401)


def forbidden_response(message: str = "Akses ditolak"):
    return api_response(success=False, message=message, code=403)


def validation_error_response(errors, message: str = "Validasi gagal"):
    return api_response(success=False, message=message, code=422, data=errors)


def paginated_response(message: str = "Berhasil", data=None, meta: dict = None, **kwargs):
    """Response dengan pagination meta."""
    return api_response(
        success=True,
        message=message,
        code=200,
        data=data,
        meta=meta or {},
        **kwargs
    )


# ── Alias pendek untuk kemudahan controller ──────────────────
# Import: from app.helpers.response import success, error
def success(message: str = "Berhasil", data=None, code: int = 200, **kwargs):
    return api_response(success=True, message=message, code=code, data=data, **kwargs)


def error(message: str = "Terjadi kesalahan", code: int = 400, data=None, **kwargs):
    return api_response(success=False, message=message, code=code, data=data, **kwargs)
