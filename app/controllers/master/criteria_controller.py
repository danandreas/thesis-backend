"""
Controller: Master - Criteria & RequirementType
CRUD untuk data master kriteria dan jenis syarat tambahan.
Hanya bisa diakses oleh admin.
"""
from flask import request
from flask_jwt_extended import jwt_required, get_jwt_identity

from app import db
from app.models.criteria import Criteria, RequirementType
from app.helpers.response import success, error
from app.middleware.auth_middleware import admin_required


# ─────────────────────────────────────────────────────────────
# CRITERIA
# ─────────────────────────────────────────────────────────────

@jwt_required()
@admin_required
def criteria_index():
    """GET /api/master/criteria — Daftar semua kriteria."""
    items = Criteria.query.order_by(Criteria.id).all()
    return success(data=[c.to_dict() for c in items], message="Data kriteria berhasil diambil")


@jwt_required()
@admin_required
def criteria_store():
    """POST /api/master/criteria — Tambah kriteria baru."""
    body = request.get_json() or {}
    code = (body.get('code') or '').strip().upper()
    name = (body.get('name') or '').strip()

    if not code or not name:
        return error("Field 'code' dan 'name' wajib diisi.", 422)

    if Criteria.query.filter_by(code=code).first():
        return error(f"Kode kriteria '{code}' sudah digunakan.", 409)

    item = Criteria(
        code=code,
        name=name,
        description=body.get('description'),
        is_active=body.get('is_active', True),
    )
    db.session.add(item)
    db.session.commit()
    return success(data=item.to_dict(), message="Kriteria berhasil ditambahkan.", code=201)


@jwt_required()
@admin_required
def criteria_show(id):
    """GET /api/master/criteria/<id> — Detail kriteria."""
    item = Criteria.query.get_or_404(id)
    return success(data=item.to_dict())


@jwt_required()
@admin_required
def criteria_update(id):
    """PUT /api/master/criteria/<id> — Update kriteria."""
    item = Criteria.query.get_or_404(id)
    body = request.get_json() or {}

    if 'code' in body:
        code = body['code'].strip().upper()
        existing = Criteria.query.filter_by(code=code).first()
        if existing and existing.id != id:
            return error(f"Kode '{code}' sudah digunakan.", 409)
        item.code = code

    if 'name' in body:
        item.name = body['name'].strip()
    if 'description' in body:
        item.description = body['description']
    if 'is_active' in body:
        item.is_active = bool(body['is_active'])

    db.session.commit()
    return success(data=item.to_dict(), message="Kriteria berhasil diperbarui.")


@jwt_required()
@admin_required
def criteria_destroy(id):
    """DELETE /api/master/criteria/<id> — Hapus kriteria."""
    item = Criteria.query.get_or_404(id)
    # Cek apakah kriteria sudah dipakai di position_criteria
    if item.position_criteria.count() > 0:
        return error("Kriteria tidak bisa dihapus karena sudah digunakan di setup posisi.", 409)
    db.session.delete(item)
    db.session.commit()
    return success(message="Kriteria berhasil dihapus.")


# ─────────────────────────────────────────────────────────────
# REQUIREMENT TYPES
# ─────────────────────────────────────────────────────────────

@jwt_required()
@admin_required
def reqtype_index():
    """GET /api/master/requirement-types"""
    items = RequirementType.query.order_by(RequirementType.id).all()
    return success(data=[i.to_dict() for i in items])


@jwt_required()
@admin_required
def reqtype_store():
    """POST /api/master/requirement-types"""
    body = request.get_json() or {}
    code = (body.get('code') or '').strip().upper()
    name = (body.get('name') or '').strip()

    if not code or not name:
        return error("Field 'code' dan 'name' wajib diisi.", 422)
    if RequirementType.query.filter_by(code=code).first():
        return error(f"Kode '{code}' sudah digunakan.", 409)

    item = RequirementType(
        code=code,
        name=name,
        description=body.get('description'),
        value_type=body.get('value_type', 'numeric'),
        min_value=body.get('min_value', 0),
        max_value=body.get('max_value', 100),
        unit=body.get('unit'),
        is_active=body.get('is_active', True),
    )
    db.session.add(item)
    db.session.commit()
    return success(data=item.to_dict(), message="Jenis syarat berhasil ditambahkan.", code=201)


@jwt_required()
@admin_required
def reqtype_show(id):
    """GET /api/master/requirement-types/<id>"""
    return success(data=RequirementType.query.get_or_404(id).to_dict())


@jwt_required()
@admin_required
def reqtype_update(id):
    """PUT /api/master/requirement-types/<id>"""
    item = RequirementType.query.get_or_404(id)
    body = request.get_json() or {}
    for field in ['name', 'description', 'unit']:
        if field in body:
            setattr(item, field, body[field])
    if 'value_type' in body:
        item.value_type = body['value_type']
    if 'min_value' in body:
        item.min_value = body['min_value']
    if 'max_value' in body:
        item.max_value = body['max_value']
    if 'is_active' in body:
        item.is_active = bool(body['is_active'])
    db.session.commit()
    return success(data=item.to_dict(), message="Jenis syarat berhasil diperbarui.")


@jwt_required()
@admin_required
def reqtype_destroy(id):
    """DELETE /api/master/requirement-types/<id>"""
    item = RequirementType.query.get_or_404(id)
    db.session.delete(item)
    db.session.commit()
    return success(message="Jenis syarat berhasil dihapus.")
