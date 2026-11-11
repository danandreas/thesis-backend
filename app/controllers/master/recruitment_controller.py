"""
Controller: Master - Recruitment, Position, Requirement, PositionCriteria
CRUD untuk setup rekrutmen lengkap. Hanya admin.
"""
from flask import request
from flask_jwt_extended import jwt_required, get_jwt_identity

from app import db
from app.models import (
    Recruitment, RecruitmentPosition, RecruitmentRequirement,
    RequirementType, PositionCriteria, Criteria,
    AssessmentQuestion, AssessmentOption
)
from app.helpers.response import success, error
from app.middleware.auth_middleware import admin_required


# ─────────────────────────────────────────────────────────────
# RECRUITMENT CRUD
# ─────────────────────────────────────────────────────────────

@jwt_required()
@admin_required
def recruitment_index():
    """
    GET /api/master/recruitments
    Query params:
      - page     : nomor halaman (default 1)
      - per_page : item per halaman (default 20, max 100)
      - search   : cari berdasarkan title / code
      - status   : filter status (draft|active|closed)
    """
    page     = int(request.args.get('page',     1))
    per_page = min(int(request.args.get('per_page', 20)), 100)
    search   = request.args.get('search',  '').strip()
    status   = request.args.get('status',  '').strip()

    q = Recruitment.query
    if search:
        q = q.filter(
            db.or_(
                Recruitment.title.ilike(f'%{search}%'),
                Recruitment.code.ilike(f'%{search}%'),
            )
        )
    if status:
        q = q.filter(Recruitment.status == status)

    paginated = q.order_by(Recruitment.id.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    result = []
    for r in paginated.items:
        d = r.to_dict()
        d['positions'] = [p.to_dict() for p in r.positions]
        result.append(d)

    return success(data={
        'items':       result,
        'total':       paginated.total,
        'page':        paginated.page,
        'per_page':    paginated.per_page,
        'total_pages': paginated.pages,
    })



@jwt_required()
@admin_required
def recruitment_store():
    """POST /api/master/recruitments"""
    body = request.get_json() or {}
    user_id = get_jwt_identity()

    code  = (body.get('code') or '').strip()
    title = (body.get('title') or '').strip()
    if not code or not title:
        return error("Field 'code' dan 'title' wajib diisi.", 422)
    if Recruitment.query.filter_by(code=code).first():
        return error(f"Kode rekrutmen '{code}' sudah digunakan.", 409)

    item = Recruitment(
        code=code,
        title=title,
        description=body.get('description'),
        created_by=user_id,
    )
    db.session.add(item)
    db.session.commit()
    return success(data=item.to_dict(), message="Rekrutmen berhasil dibuat.", code=201)


@jwt_required()
@admin_required
def recruitment_show(id):
    """GET /api/master/recruitments/<id> — Detail + posisi + bobot assessment"""
    item = Recruitment.query.get_or_404(id)
    data = item.to_dict()
    data['positions'] = [p.to_dict() for p in item.positions]
    data['requirements'] = [r.to_dict() for r in item.requirements.order_by(
        RecruitmentRequirement.display_order)]
    return success(data=data)


@jwt_required()
@admin_required
def recruitment_update(id):
    """PUT /api/master/recruitments/<id>"""
    item = Recruitment.query.get_or_404(id)
    if item.status not in ['draft']:
        return error("Rekrutmen yang sudah aktif tidak bisa diedit. Tutup dulu.", 422)
    body = request.get_json() or {}
    for field in ['title', 'description']:
        if field in body:
            setattr(item, field, body[field])
    db.session.commit()
    return success(data=item.to_dict(), message="Rekrutmen berhasil diperbarui.")


@jwt_required()
@admin_required
def recruitment_publish(id):
    """POST /api/master/recruitments/<id>/publish — Publish rekrutmen"""
    item = Recruitment.query.get_or_404(id)
    if item.status != 'draft':
        return error(f"Rekrutmen berstatus '{item.status}', tidak bisa dipublish.", 422)

    if not list(item.positions):
        return error("Rekrutmen harus memiliki minimal satu posisi.", 422)

    # Validasi: setiap posisi harus punya kriteria + pertanyaan
    for pos in item.positions:
        if pos.criteria_setup.count() == 0:
            return error(f"Posisi '{pos.title}' belum memiliki setup kriteria.", 422)

        # Bug #12 fix: cek setiap kriteria punya minimal 1 pertanyaan aktif
        for pc in pos.criteria_setup.all():
            q_count = pc.questions.filter_by(is_active=True).count()
            if q_count == 0:
                return error(
                    f"Kriteria '{pc.criteria.name}' pada posisi '{pos.title}' "
                    f"belum memiliki pertanyaan asesmen. "
                    f"Tambahkan minimal 1 pertanyaan sebelum publish.",
                    422
                )

    item.publish()
    return success(data=item.to_dict(), message="Rekrutmen berhasil dipublish.")



@jwt_required()
@admin_required
def recruitment_close(id):
    """POST /api/master/recruitments/<id>/close — Tutup rekrutmen"""
    item = Recruitment.query.get_or_404(id)
    if item.status != 'active':
        return error("Hanya rekrutmen aktif yang bisa ditutup.", 422)
    item.close()
    return success(data=item.to_dict(), message="Rekrutmen berhasil ditutup.")


@jwt_required()
@admin_required
def recruitment_destroy(id):
    """DELETE /api/master/recruitments/<id>"""
    item = Recruitment.query.get_or_404(id)
    if item.status != 'draft':
        return error("Hanya rekrutmen berstatus draft yang bisa dihapus.", 422)
    db.session.delete(item)
    db.session.commit()
    return success(message="Rekrutmen berhasil dihapus.")


# ─────────────────────────────────────────────────────────────
# RECRUITMENT REQUIREMENTS (Syarat tambahan: IPK, TOEFL, dll)
# ─────────────────────────────────────────────────────────────

@jwt_required()
@admin_required
def requirement_setup(recruitment_id):
    """
    POST /api/master/recruitments/<id>/requirements
    Setup syarat tambahan untuk rekrutmen.
    Body: list of {requirement_type_id, weight, minimum_value, is_mandatory, display_order}
    Menggantikan seluruh setup syarat tambahan yang ada.
    """
    item = Recruitment.query.get_or_404(recruitment_id)
    body = request.get_json() or {}
    reqs = body.get('requirements', [])

    # Validasi total bobot tidak melebihi 100
    total_weight = sum(float(r.get('weight', 0)) for r in reqs)
    if total_weight >= 100:
        return error(f"Total bobot syarat tambahan ({total_weight}%) tidak boleh >= 100%. "
                     f"Sisakan minimal 1% untuk assessment.", 422)

    # Hapus yang lama, insert yang baru
    RecruitmentRequirement.query.filter_by(recruitment_id=recruitment_id).delete()
    for r in reqs:
        rtype_id = r.get('requirement_type_id')
        if not RequirementType.query.get(rtype_id):
            return error(f"requirement_type_id {rtype_id} tidak ditemukan.", 404)
        rr = RecruitmentRequirement(
            recruitment_id=recruitment_id,
            requirement_type_id=rtype_id,
            weight=float(r.get('weight', 0)),
            minimum_value=r.get('minimum_value'),
            is_mandatory=bool(r.get('is_mandatory', False)),
            display_order=int(r.get('display_order', 0)),
        )
        db.session.add(rr)

    db.session.commit()
    data = item.to_dict()
    data['requirements'] = [r.to_dict() for r in item.requirements]
    return success(data=data, message="Syarat tambahan berhasil disimpan.")


@jwt_required()
@admin_required
def requirement_update(recruitment_id, requirement_id):
    """
    PUT /api/master/recruitments/<id>/requirements/<rid>
    Update satu syarat tambahan.
    """
    rr = RecruitmentRequirement.query.filter_by(
        id=requirement_id, recruitment_id=recruitment_id
    ).first_or_404()
    body = request.get_json() or {}
    if 'weight' in body:
        rr.weight = float(body['weight'])
    if 'minimum_value' in body:
        rr.minimum_value = body['minimum_value']
    if 'is_mandatory' in body:
        rr.is_mandatory = bool(body['is_mandatory'])
    if 'display_order' in body:
        rr.display_order = int(body['display_order'])
    db.session.commit()
    return success(data=rr.to_dict(), message="Syarat tambahan berhasil diperbarui.")


@jwt_required()
@admin_required
def requirement_destroy(recruitment_id, requirement_id):
    """
    DELETE /api/master/recruitments/<id>/requirements/<rid>
    Hapus satu syarat tambahan.
    """
    rr = RecruitmentRequirement.query.filter_by(
        id=requirement_id, recruitment_id=recruitment_id
    ).first_or_404()
    db.session.delete(rr)
    db.session.commit()
    return success(message="Syarat tambahan berhasil dihapus.")


# ─────────────────────────────────────────────────────────────
# POSITION CRUD
# ─────────────────────────────────────────────────────────────

@jwt_required()
@admin_required
def position_index(recruitment_id):
    """GET /api/master/recruitments/<id>/positions"""
    Recruitment.query.get_or_404(recruitment_id)
    items = RecruitmentPosition.query.filter_by(recruitment_id=recruitment_id).all()
    return success(data=[p.to_dict() for p in items])


@jwt_required()
@admin_required
def position_store(recruitment_id):
    """POST /api/master/recruitments/<id>/positions"""
    Recruitment.query.get_or_404(recruitment_id)
    body = request.get_json() or {}
    title = (body.get('title') or '').strip()
    if not title:
        return error("Field 'title' wajib diisi.", 422)

    item = RecruitmentPosition(
        recruitment_id=recruitment_id,
        title=title,
        description=body.get('description'),
        quota=int(body.get('quota', 1)),
    )
    db.session.add(item)
    db.session.commit()
    return success(data=item.to_dict(), message="Posisi berhasil ditambahkan.", code=201)


@jwt_required()
@admin_required
def position_show(recruitment_id, position_id):
    """GET /api/master/recruitments/<id>/positions/<pid> — Detail posisi + kriteria"""
    pos = RecruitmentPosition.query.filter_by(
        id=position_id, recruitment_id=recruitment_id
    ).first_or_404()
    data = pos.to_dict()
    data['recruitment_title'] = pos.recruitment.title if pos.recruitment else None
    data['criteria_setup'] = [pc.to_dict() for pc in pos.criteria_setup.order_by(
        PositionCriteria.display_order)]
    return success(data=data)


@jwt_required()
@admin_required
def position_update(recruitment_id, position_id):
    """PUT /api/master/recruitments/<id>/positions/<pid>"""
    pos = RecruitmentPosition.query.filter_by(
        id=position_id, recruitment_id=recruitment_id
    ).first_or_404()
    body = request.get_json() or {}
    for field in ['title', 'description']:
        if field in body:
            setattr(pos, field, body[field])
    if 'quota' in body:
        pos.quota = int(body['quota'])
    db.session.commit()
    return success(data=pos.to_dict(), message="Posisi berhasil diperbarui.")


@jwt_required()
@admin_required
def position_destroy(recruitment_id, position_id):
    """DELETE /api/master/recruitments/<id>/positions/<pid>"""
    pos = RecruitmentPosition.query.filter_by(
        id=position_id, recruitment_id=recruitment_id
    ).first_or_404()
    db.session.delete(pos)
    db.session.commit()
    return success(message="Posisi berhasil dihapus.")


# ─────────────────────────────────────────────────────────────
# POSITION CRITERIA SETUP
# ─────────────────────────────────────────────────────────────

@jwt_required()
@admin_required
def position_criteria_setup(recruitment_id, position_id):
    """
    POST /api/master/recruitments/<id>/positions/<pid>/criteria
    Setup kriteria untuk posisi tertentu.
    Body: list of {criteria_id, weight_manual, fuzzy_low, fuzzy_mid, fuzzy_high, criteria_type}
    """
    pos = RecruitmentPosition.query.filter_by(
        id=position_id, recruitment_id=recruitment_id
    ).first_or_404()
    body  = request.get_json() or {}

    # Bentuk body terbungkus {"criteria": [...]} berarti ganti seluruh setup (replace);
    # bentuk body polos {criteria_id, weight_manual, ...} dari UI berarti tambah satu
    # kriteria baru ke setup yang sudah berjalan tanpa menghapus setup lama.
    replace_mode = 'criteria' in body
    if replace_mode:
        items = body.get('criteria') or []
    elif body.get('criteria_id'):
        items = [body]
    else:
        items = []

    if not items:
        return error("Minimal satu kriteria harus diisi.", 422)

    if replace_mode:
        # Hapus setup lama
        PositionCriteria.query.filter_by(position_id=position_id).delete()

    start_order = 0 if replace_mode else PositionCriteria.query.filter_by(
        position_id=position_id).count()

    for i, c in enumerate(items):
        crit_id = c.get('criteria_id')
        if not replace_mode:
            sudah = PositionCriteria.query.filter_by(
                position_id=position_id, criteria_id=crit_id
            ).first()
            if sudah:
                return error("Kriteria tersebut sudah ada pada posisi ini.", 422)
        if not Criteria.query.get(crit_id):
            return error(f"criteria_id {crit_id} tidak ditemukan.", 404)

        pc = PositionCriteria(
            position_id=position_id,
            criteria_id=crit_id,
            weight_manual=float(c.get('weight_manual', 50)),
            fuzzy_low=float(c.get('fuzzy_low', 1)),
            fuzzy_mid=float(c.get('fuzzy_mid', 3)),
            fuzzy_high=float(c.get('fuzzy_high', 5)),
            criteria_type=c.get('criteria_type', 'benefit'),
            display_order=start_order + i,
        )
        db.session.add(pc)

    db.session.commit()
    data = pos.to_dict()
    data['criteria_setup'] = [pc.to_dict() for pc in pos.criteria_setup.order_by(
        PositionCriteria.display_order)]
    return success(data=data, message="Setup kriteria posisi berhasil disimpan.")


@jwt_required()
@admin_required
def position_criteria_update(position_criteria_id):
    """
    PUT /api/master/position-criteria/<id>
    Update satu kriteria posisi.
    """
    pc   = PositionCriteria.query.get_or_404(position_criteria_id)
    body = request.get_json() or {}
    if 'weight_manual' in body:
        pc.weight_manual = float(body['weight_manual'])
    if 'fuzzy_low' in body:
        pc.fuzzy_low = float(body['fuzzy_low'])
    if 'fuzzy_mid' in body:
        pc.fuzzy_mid = float(body['fuzzy_mid'])
    if 'fuzzy_high' in body:
        pc.fuzzy_high = float(body['fuzzy_high'])
    if 'criteria_type' in body:
        pc.criteria_type = body['criteria_type']
    if 'display_order' in body:
        pc.display_order = int(body['display_order'])
    db.session.commit()
    return success(data=pc.to_dict(), message="Kriteria posisi berhasil diperbarui.")


@jwt_required()
@admin_required
def position_criteria_destroy(position_criteria_id):
    """
    DELETE /api/master/position-criteria/<id>
    Hapus satu kriteria posisi beserta semua pertanyaannya.
    """
    pc = PositionCriteria.query.get_or_404(position_criteria_id)
    db.session.delete(pc)
    db.session.commit()
    return success(message="Kriteria posisi berhasil dihapus.")


# ─────────────────────────────────────────────────────────────
# ASSESSMENT QUESTIONS & OPTIONS
# ─────────────────────────────────────────────────────────────

@jwt_required()
@admin_required
def question_index(position_criteria_id):
    """GET /api/master/position-criteria/<id>/questions"""
    pc = PositionCriteria.query.get_or_404(position_criteria_id)
    questions = pc.questions.order_by(AssessmentQuestion.display_order).all()
    return success(data=[q.to_dict() for q in questions])


@jwt_required()
@admin_required
def question_store(position_criteria_id):
    """POST /api/master/position-criteria/<id>/questions"""
    pc   = PositionCriteria.query.get_or_404(position_criteria_id)
    body = request.get_json() or {}
    text = (body.get('question_text') or '').strip()
    if not text:
        return error("Field 'question_text' wajib diisi.", 422)

    q = AssessmentQuestion(
        position_criteria_id=position_criteria_id,
        question_text=text,
        display_order=body.get('display_order', pc.questions.count()),
        is_active=body.get('is_active', True),
    )
    db.session.add(q)
    db.session.flush()

    # Tambah options sekaligus jika disertakan; bila UI tidak mengirim opsi apa pun,
    # isikan lima opsi Likert standar (samadengan seeder) agar pertanyaan baru
    # langsung dapat dijawab kandidat.
    opts = body.get('options')
    if not opts:
        opts = [
            {'option_text': 'Tidak Pernah / Sangat Tidak Setuju', 'option_value': 1},
            {'option_text': 'Jarang / Tidak Setuju',              'option_value': 2},
            {'option_text': 'Kadang-kadang / Netral',             'option_value': 3},
            {'option_text': 'Sering / Setuju',                    'option_value': 4},
            {'option_text': 'Selalu / Sangat Setuju',             'option_value': 5},
        ]
    for i, opt in enumerate(opts):
        o = AssessmentOption(
            question_id=q.id,
            option_text=opt.get('option_text', ''),
            option_value=float(opt.get('option_value', i + 1)),
            display_order=opt.get('option_value', i + 1),
        )
        db.session.add(o)

    db.session.commit()
    return success(data=q.to_dict(), message="Pertanyaan berhasil ditambahkan.", code=201)


@jwt_required()
@admin_required
def question_update(position_criteria_id, question_id):
    """PUT /api/master/position-criteria/<id>/questions/<qid>"""
    q    = AssessmentQuestion.query.filter_by(
        id=question_id, position_criteria_id=position_criteria_id
    ).first_or_404()
    body = request.get_json() or {}
    if 'question_text' in body:
        q.question_text = body['question_text']
    if 'display_order' in body:
        q.display_order = body['display_order']
    if 'is_active' in body:
        q.is_active = bool(body['is_active'])
    db.session.commit()
    return success(data=q.to_dict(), message="Pertanyaan berhasil diperbarui.")


@jwt_required()
@admin_required
def question_destroy(position_criteria_id, question_id):
    """DELETE /api/master/position-criteria/<id>/questions/<qid>"""
    q = AssessmentQuestion.query.filter_by(
        id=question_id, position_criteria_id=position_criteria_id
    ).first_or_404()
    db.session.delete(q)
    db.session.commit()
    return success(message="Pertanyaan berhasil dihapus.")


@jwt_required()
@admin_required
def option_store(question_id):
    """POST /api/master/questions/<id>/options — Tambah pilihan jawaban"""
    q    = AssessmentQuestion.query.get_or_404(question_id)
    body = request.get_json() or {}
    text = (body.get('option_text') or '').strip()
    if not text:
        return error("Field 'option_text' wajib diisi.", 422)

    o = AssessmentOption(
        question_id=question_id,
        option_text=text,
        option_value=float(body.get('option_value', 1)),
        display_order=body.get('display_order', q.options.count()),
    )
    db.session.add(o)
    db.session.commit()
    return success(data=o.to_dict(), message="Pilihan jawaban berhasil ditambahkan.", code=201)


@jwt_required()
@admin_required
def option_update(question_id, option_id):
    """PUT /api/master/questions/<id>/options/<oid>"""
    o    = AssessmentOption.query.filter_by(
        id=option_id, question_id=question_id
    ).first_or_404()
    body = request.get_json() or {}
    if 'option_text' in body:
        o.option_text = body['option_text']
    if 'option_value' in body:
        o.option_value = float(body['option_value'])
    if 'display_order' in body:
        o.display_order = body['display_order']
    db.session.commit()
    return success(data=o.to_dict(), message="Pilihan berhasil diperbarui.")


@jwt_required()
@admin_required
def option_destroy(question_id, option_id):
    """DELETE /api/master/questions/<id>/options/<oid>"""
    o = AssessmentOption.query.filter_by(
        id=option_id, question_id=question_id
    ).first_or_404()
    db.session.delete(o)
    db.session.commit()
    return success(message="Pilihan berhasil dihapus.")
