"""
CrudTrait - Reusable CRUD operations yang bisa di-mixin ke controller.
Mirip seperti Trait di Laravel.
"""
from app.helpers.pagination import get_pagination_params, make_pagination_meta, apply_sort
from app.helpers.response import (
    success_response, created_response, not_found_response,
    error_response, paginated_response
)


class CrudTrait:
    """
    Mixin trait berisi operasi CRUD standar dengan pagination + sorting bawaan.

    Default: 20 data per halaman, sort by id desc.

    Query params yang didukung di endpoint index:
      ?page=1
      ?per_page=20     (max 100)
      ?sort=created_at
      ?order=asc|desc

    Wajib set di subclass:
        model_class = ModelName

    Opsional override:
        get_list_query(self) → untuk tambah filter/join/search custom
    """
    model_class = None
    default_per_page = 20  # bisa di-override per controller

    def get_list_query(self):
        """Override di controller untuk tambah filter/search/join."""
        return self.model_class.query

    def index(self):
        """GET / - List semua data dengan pagination + sorting."""
        page, per_page, sort_col, order = get_pagination_params(
            default_per_page=self.default_per_page
        )

        query = self.get_list_query()
        query = apply_sort(query, self.model_class, sort_col, order)

        paginated = query.paginate(page=page, per_page=per_page, error_out=False)

        data = [item.to_dict() for item in paginated.items]
        meta = make_pagination_meta(paginated)

        return paginated_response(
            message=f"Data {self.model_class.__tablename__} berhasil diambil.",
            data=data,
            meta=meta
        )

    def show(self, id):
        """GET /<id> - Detail satu record."""
        instance = self.model_class.find(id)
        if not instance:
            return not_found_response("Data tidak ditemukan.")
        return success_response(
            message="Detail data berhasil diambil.",
            data=instance.to_dict()
        )

    def destroy(self, id):
        """DELETE /<id> - Hapus record."""
        instance = self.model_class.find(id)
        if not instance:
            return not_found_response("Data tidak ditemukan.")
        try:
            instance.delete()
            return success_response(message="Data berhasil dihapus.")
        except Exception as e:
            return error_response(message=f"Gagal menghapus data: {str(e)}", code=500)
