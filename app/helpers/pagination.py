from flask import request


def get_pagination_params(default_per_page: int = 20):
    """
    Ambil parameter pagination dari query string.

    Query params yang didukung:
      ?page=1          → halaman ke berapa (default: 1)
      ?per_page=20     → jumlah data per halaman (default: 20, max: 100)
      ?sort=created_at → kolom untuk sorting (default: id)
      ?order=desc      → arah sort: asc / desc (default: desc)
      ?search=keyword  → pencarian (diproses di controller/query)
    """
    try:
        page = max(1, int(request.args.get('page', 1)))
    except (ValueError, TypeError):
        page = 1

    try:
        per_page = min(100, max(1, int(request.args.get('per_page', default_per_page))))
    except (ValueError, TypeError):
        per_page = default_per_page

    sort = request.args.get('sort', 'id')
    order = request.args.get('order', 'desc').lower()
    if order not in ('asc', 'desc'):
        order = 'desc'

    return page, per_page, sort, order


def make_pagination_meta(paginated_obj):
    """
    Bangun pagination meta dari SQLAlchemy paginate object.
    Format mirip Laravel ResourceCollection.
    """
    page = paginated_obj.page
    per_page = paginated_obj.per_page
    total = paginated_obj.total
    total_pages = paginated_obj.pages

    # Nomor record dari-sampai di halaman ini
    from_record = ((page - 1) * per_page) + 1 if total > 0 else 0
    to_record = min(page * per_page, total)

    # Build base URL untuk next/prev links
    base_url = request.base_url
    args = request.args.to_dict()

    def build_url(p):
        args['page'] = p
        args['per_page'] = per_page
        params = '&'.join(f"{k}={v}" for k, v in args.items())
        return f"{base_url}?{params}"

    return {
        "current_page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": total_pages,
        "from": from_record,
        "to": to_record,
        "has_next": paginated_obj.has_next,
        "has_prev": paginated_obj.has_prev,
        "next_url": build_url(page + 1) if paginated_obj.has_next else None,
        "prev_url": build_url(page - 1) if paginated_obj.has_prev else None,
        "first_url": build_url(1),
        "last_url": build_url(total_pages) if total_pages > 0 else build_url(1),
    }


def apply_sort(query, model_class, sort_col: str, order: str):
    """
    Terapkan sorting ke query SQLAlchemy secara aman.
    Hanya izinkan kolom yang benar-benar ada di model (hindari SQL injection).
    """
    column = getattr(model_class, sort_col, None)
    if column is None:
        # Fallback ke id jika kolom tidak ditemukan
        column = getattr(model_class, 'id', None)

    if column is not None:
        query = query.order_by(column.desc() if order == 'desc' else column.asc())

    return query
