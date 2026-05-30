from flask import request
from app.models.role import Role
from app.traits.crud_trait import CrudTrait
from app.middleware.auth_middleware import admin_required
from app.helpers import (
    get_json_body, validate_required,
    success_response, created_response, error_response,
    not_found_response, validation_error_response,
)


class RoleController(CrudTrait):
    model_class = Role
    default_per_page = 20

    def get_list_query(self):
        """
        Custom query dengan filter:
          ?search=keyword → cari di name atau code
        Sorting ditangani otomatis oleh CrudTrait via ?sort=&order=
        """
        query = Role.query
        search = request.args.get('search', '').strip()
        if search:
            query = query.filter(
                Role.name.ilike(f'%{search}%') |
                Role.code.ilike(f'%{search}%')
            )
        return query

    @admin_required
    def index(self):
        """GET /roles - List roles (admin only)."""
        return super().index()

    @admin_required
    def show(self, id):
        """GET /roles/<id> - Detail role (admin only)."""
        return super().show(id)

    @admin_required
    def store(self):
        """POST /roles - Buat role baru (admin only)."""
        data = get_json_body()

        errors = validate_required(data, ['code', 'name'])
        if errors:
            return validation_error_response(errors)

        # Normalisasi code: lowercase, no space
        code = data['code'].lower().replace(' ', '_')

        if Role.first_where(code=code):
            return error_response("Code role sudah ada.", code=409)

        role = Role.create(code=code, name=data['name'])
        return created_response(message="Role berhasil dibuat.", data=role.to_dict())

    @admin_required
    def update(self, id):
        """PUT /roles/<id> - Update role (admin only)."""
        role = Role.find(id)
        if not role:
            return not_found_response("Role tidak ditemukan.")

        data = get_json_body()

        # Cek code unik jika diubah
        new_code = data.get('code')
        if new_code:
            new_code = new_code.lower().replace(' ', '_')
            existing = Role.first_where(code=new_code)
            if existing and existing.id != id:
                return error_response("Code role sudah digunakan.", code=409)
            data['code'] = new_code

        updatable = ['code', 'name']
        update_data = {k: v for k, v in data.items() if k in updatable and v is not None}

        role.update(**update_data)
        return success_response(message="Role berhasil diperbarui.", data=role.to_dict())

    @admin_required
    def destroy(self, id):
        """DELETE /roles/<id> - Hapus role (admin only)."""
        role = Role.find(id)
        if not role:
            return not_found_response("Role tidak ditemukan.")

        # Cek apakah role masih digunakan user
        if role.users.count() > 0:
            return error_response(
                "Role tidak dapat dihapus karena masih digunakan oleh user.",
                code=409
            )

        return super().destroy(id)

_role_controller = RoleController()
index = _role_controller.index
store = _role_controller.store
show = _role_controller.show
update = _role_controller.update
destroy = _role_controller.destroy
