from datetime import datetime, timezone
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    get_jwt_identity, get_jwt, verify_jwt_in_request
)
from app.models.user import User
from app.models.role import Role
from app.models.token_blacklist import TokenBlacklist
from app.helpers import (
    get_json_body, validate_required, validate_email,
    success_response, created_response, error_response,
    validation_error_response, unauthorized_response
)
from app.middleware.auth_middleware import auth_required, get_current_user


class AuthController:

    def register(self):
        """POST /auth/register - Daftarkan user baru."""
        data = get_json_body()

        errors = validate_required(data, ['name', 'email', 'password'])

        if 'email' not in errors and not validate_email(data.get('email', '')):
            errors['email'] = ['Format email tidak valid.']

        if 'password' not in errors and len(data.get('password', '')) < 6:
            errors['password'] = ['Password minimal 6 karakter.']

        if errors:
            return validation_error_response(errors)

        if User.first_where(email=data['email']):
            return error_response("Email sudah terdaftar.", code=409)

        role = Role.first_where(code='candidate') or Role.first_where(code='user')
        if not role:
            return error_response("Role 'candidate' belum dikonfigurasi. Jalankan seeder terlebih dahulu.", code=500)

        user = User(
            role_id=role.id,
            name=data['name'],
            email=data['email'],
            phone=data.get('phone'),
            address=data.get('address'),
            password='',
        )
        user.set_password(data['password'])
        user.save()

        access_token = create_access_token(identity=str(user.id))
        refresh_token = create_refresh_token(identity=str(user.id))

        return created_response(
            message="Registrasi berhasil.",
            data={
                "user": user.to_dict(),
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "Bearer",
            }
        )

    def login(self):
        """POST /auth/login - Login dan dapatkan token."""
        data = get_json_body()

        errors = validate_required(data, ['email', 'password'])
        if errors:
            return validation_error_response(errors)

        user = User.first_where(email=data['email'])
        if not user or not user.check_password(data['password']):
            return unauthorized_response("Email atau password salah.")

        access_token = create_access_token(identity=str(user.id))
        refresh_token = create_refresh_token(identity=str(user.id))

        return success_response(
            message="Login berhasil.",
            data={
                "user": user.to_dict(),
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "Bearer",
            }
        )

    @auth_required
    def me(self):
        """GET /auth/me - Profile user yang sedang login."""
        user = get_current_user()
        if not user:
            return unauthorized_response()
        return success_response(message="Profile berhasil diambil.", data=user.to_dict())

    def refresh(self):
        """
        POST /auth/refresh - Tukar refresh_token dengan access_token baru.
        Endpoint ini harus dikirim dengan refresh_token (bukan access_token).
        Setelah refresh, refresh_token lama di-blacklist agar tidak bisa dipakai ulang.
        """
        # Bug #9 fix: gunakan verify_jwt_in_request(refresh=True) bukan @auth_required
        # supaya endpoint ini menerima refresh_token, bukan access_token
        try:
            verify_jwt_in_request(refresh=True)
        except Exception:
            from app.helpers import unauthorized_response as _unauth
            return _unauth("Refresh token tidak valid atau sudah kadaluarsa.")

        jwt_data = get_jwt()
        user_id  = get_jwt_identity()

        user = User.find(user_id)
        if not user:
            return unauthorized_response("User tidak ditemukan.")

        # Blacklist refresh token lama yang dipakai untuk refresh ini
        jti = jwt_data.get('jti')
        exp_timestamp = jwt_data.get('exp')
        expires_at = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc).replace(tzinfo=None)

        TokenBlacklist.revoke(
            jti=jti,
            user_id=user.id,
            token_type='refresh',
            expires_at=expires_at
        )

        # Terbitkan token baru (access + refresh baru)
        new_access_token  = create_access_token(identity=str(user.id))
        new_refresh_token = create_refresh_token(identity=str(user.id))

        return success_response(
            message="Token berhasil diperbarui.",
            data={
                "access_token":  new_access_token,
                "refresh_token": new_refresh_token,
                "token_type":    "Bearer",
            }
        )


    @auth_required
    def logout(self):
        """
        POST /auth/logout - Logout: blacklist access_token saat ini.
        Token ini tidak akan bisa dipakai lagi meskipun belum expired.
        """
        jwt_data = get_jwt()
        user_id = get_jwt_identity()

        jti = jwt_data.get('jti')
        exp_timestamp = jwt_data.get('exp')
        expires_at = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc).replace(tzinfo=None)

        TokenBlacklist.revoke(
            jti=jti,
            user_id=int(user_id),
            token_type='access',
            expires_at=expires_at
        )

        return success_response(message="Logout berhasil. Token telah dicabut.")

    @auth_required
    def logout_all(self):
        """
        POST /auth/logout-all - Logout dari semua device.
        """
        user = get_current_user()
        if not user:
            return unauthorized_response()
        user.update(force_logout_at=datetime.utcnow())
        return success_response(message="Berhasil logout dari semua perangkat.")

    @auth_required
    def update_me(self):
        """
        PUT /auth/me - Update profil user yang sedang login (nama, phone, address).
        Bisa dipakai oleh semua role (admin maupun kandidat).
        """
        from flask import request as flask_request
        from app import db as _db
        user = get_current_user()
        if not user:
            return unauthorized_response()

        body = flask_request.get_json() or {}
        for field in ['name', 'phone', 'address']:
            if field in body:
                setattr(user, field, body[field])
        _db.session.commit()
        return success_response(message="Profil berhasil diperbarui.", data=user.to_dict())

    @auth_required
    def update_password(self):
        """
        PUT /auth/me/password - Ganti password user yang sedang login.
        Body: { current_password, password, password_confirm }
        """
        from flask import request as flask_request
        user = get_current_user()
        if not user:
            return unauthorized_response()

        body = flask_request.get_json() or {}
        current_pw  = body.get('current_password', '')
        new_pw      = body.get('password', '')
        confirm_pw  = body.get('password_confirm', '')

        if not user.check_password(current_pw):
            return error_response("Password saat ini tidak valid.", code=422)
        if len(new_pw) < 6:
            return error_response("Password baru minimal 6 karakter.", code=422)
        if new_pw != confirm_pw:
            return error_response("Konfirmasi password tidak cocok.", code=422)

        user.set_password(new_pw)
        user.save()
        return success_response(message="Password berhasil diubah.")

_auth_controller = AuthController()
register        = _auth_controller.register
login           = _auth_controller.login
me              = _auth_controller.me
refresh         = _auth_controller.refresh
logout          = _auth_controller.logout
logout_all      = _auth_controller.logout_all
update_me       = _auth_controller.update_me
update_password = _auth_controller.update_password
