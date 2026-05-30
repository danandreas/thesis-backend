from flask import request
from app.models.user import User
from app.models.role import Role
from app.traits.crud_trait import CrudTrait
from app.middleware.auth_middleware import admin_required, auth_required, get_current_user
from app.helpers import (
    get_json_body, validate_required, validate_email,
    success_response, created_response, error_response,
    not_found_response, validation_error_response,
    get_pagination_params, make_pagination_meta, paginated_response
)


class UserController(CrudTrait):
    model_class = User
    default_per_page = 20  # override default jika perlu

    def get_list_query(self):
        """
        Custom query: join ke roles, support filter:
          ?search=keyword    → cari di name atau email
          ?role_id=1         → filter by role
          ?role_code=admin   → filter by role code
        Sorting ditangani otomatis oleh CrudTrait via ?sort=&order=
        """
        query = User.query.join(Role)

        search = request.args.get('search', '').strip()
        if search:
            query = query.filter(
                User.name.ilike(f'%{search}%') |
                User.email.ilike(f'%{search}%') |
                User.phone.ilike(f'%{search}%')
            )

        role_id = request.args.get('role_id')
        if role_id:
            query = query.filter(User.role_id == role_id)

        role_code = request.args.get('role_code', '').strip()
        if role_code:
            query = query.filter(Role.code == role_code)

        return query

    @admin_required
    def index(self):
        """GET /users - List users (admin only)."""
        return super().index()

    @admin_required
    def show(self, id):
        """GET /users/<id> - Detail user (admin only)."""
        return super().show(id)

    @admin_required
    def store(self):
        """POST /users - Buat user baru (admin only)."""
        data = get_json_body()

        errors = validate_required(data, ['name', 'email', 'password', 'role_id'])

        if 'email' not in errors and not validate_email(data.get('email', '')):
            errors['email'] = ['Format email tidak valid.']

        if 'password' not in errors and len(data.get('password', '')) < 6:
            errors['password'] = ['Password minimal 6 karakter.']

        if errors:
            return validation_error_response(errors)

        if User.first_where(email=data['email']):
            return error_response("Email sudah terdaftar.", code=409)

        role = Role.find(data['role_id'])
        if not role:
            return error_response("Role tidak ditemukan.", code=404)

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

        return created_response(message="User berhasil dibuat.", data=user.to_dict())

    @admin_required
    def update(self, id):
        """PUT /users/<id> - Update user (admin only)."""
        user = User.find(id)
        if not user:
            return not_found_response("User tidak ditemukan.")

        data = get_json_body()

        # Validasi email unik jika diubah
        new_email = data.get('email')
        if new_email:
            if not validate_email(new_email):
                return validation_error_response({'email': ['Format email tidak valid.']})
            existing = User.first_where(email=new_email)
            if existing and existing.id != id:
                return error_response("Email sudah digunakan user lain.", code=409)

        # Validasi role jika diubah
        new_role_id = data.get('role_id')
        if new_role_id and not Role.find(new_role_id):
            return not_found_response("Role tidak ditemukan.")

        # Update fields
        updatable = ['name', 'email', 'phone', 'address', 'role_id']
        update_data = {k: v for k, v in data.items() if k in updatable and v is not None}

        if 'password' in data and data['password']:
            if len(data['password']) < 6:
                return validation_error_response({'password': ['Password minimal 6 karakter.']})
            user.set_password(data['password'])

        user.update(**update_data)

        return success_response(message="User berhasil diperbarui.", data=user.to_dict())

    @admin_required
    def destroy(self, id):
        """DELETE /users/<id> - Hapus user (admin only)."""
        current = get_current_user()
        if current and current.id == id:
            return error_response("Tidak dapat menghapus akun sendiri.", code=400)
        return super().destroy(id)

_user_controller = UserController()
index = _user_controller.index
store = _user_controller.store
show = _user_controller.show
update = _user_controller.update
destroy = _user_controller.destroy
