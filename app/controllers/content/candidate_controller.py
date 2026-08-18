"""
Controller: Content - untuk kandidat
Semua endpoint yang diakses kandidat (role=candidate).
Prefix URL: /api/content/...
"""
from datetime import datetime
from flask import request
from flask_jwt_extended import jwt_required, get_jwt_identity

from app import db
from app.models import (
    Recruitment, RecruitmentPosition, RecruitmentRequirement,
    PositionCriteria, AssessmentQuestion, AssessmentOption,
    CandidateApplication, AssessmentAnswer, CandidateRequirement,
    CandidateProfile, CandidateEducation, User
)
from app.helpers.response import success, error


def _get_current_user():
    return User.query.get(get_jwt_identity())


# ─────────────────────────────────────────────────────────────
# PROFILE KANDIDAT
# ─────────────────────────────────────────────────────────────

@jwt_required()
def profile_show():
    """GET /api/content/profile — Lihat profil kandidat sendiri."""
    user = _get_current_user()
    profile = user.candidate_profile
    data = {
        'user': {
            'id': user.id,
            'name': user.name,
            'email': user.email,
            'phone': user.phone,
            'address': user.address,
        },
        'profile': profile.to_dict() if profile else None,
        'educations': [e.to_dict() for e in user.educations],
    }
    return success(data=data)


@jwt_required()
def profile_update():
    """PUT /api/content/profile — Update profil kandidat."""
    user = _get_current_user()
    body = request.get_json() or {}

    # Update user fields
    for field in ['name', 'phone', 'address']:
        if field in body:
            setattr(user, field, body[field])

    # Upsert candidate_profile
    profile = user.candidate_profile
    if not profile:
        profile = CandidateProfile(user_id=user.id)
        db.session.add(profile)

    # Bug #16 fix: validasi gender enum sebelum ke DB agar error 422, bukan 500
    if 'gender' in body:
        valid_genders = ('male', 'female', 'other')
        if body['gender'] not in valid_genders:
            return error(
                f"Nilai gender tidak valid. Gunakan: {', '.join(valid_genders)}.",
                422
            )

    for field in ['birth_date', 'gender', 'linkedin_url', 'resume_url']:
        if field in body:
            setattr(profile, field, body[field])

    db.session.commit()
    return success(data=profile.to_dict(), message="Profil berhasil diperbarui.")



# ─────────────────────────────────────────────────────────────
# PENDIDIKAN KANDIDAT
# ─────────────────────────────────────────────────────────────

@jwt_required()
def education_index():
    """GET /api/content/educations — Daftar pendidikan kandidat."""
    user = _get_current_user()
    return success(data=[e.to_dict() for e in user.educations])


@jwt_required()
def education_store():
    """POST /api/content/educations — Tambah riwayat pendidikan."""
    user = _get_current_user()
    body = request.get_json() or {}

    degree      = body.get('degree', '').strip()
    institution = body.get('institution', '').strip()
    if not degree or not institution:
        return error("Field 'degree' dan 'institution' wajib diisi.", 422)

    # Jika is_latest=True, reset semua yang lain
    is_latest = bool(body.get('is_latest', False))
    if is_latest:
        CandidateEducation.query.filter_by(user_id=user.id).update({'is_latest': False})

    edu = CandidateEducation(
        user_id=user.id,
        degree=degree,
        institution=institution,
        major=body.get('major'),
        gpa=body.get('gpa'),
        gpa_scale=float(body.get('gpa_scale', 4.0)),
        graduation_year=body.get('graduation_year'),
        is_latest=is_latest,
    )
    db.session.add(edu)
    db.session.commit()
    return success(data=edu.to_dict(), message="Pendidikan berhasil ditambahkan.", code=201)


@jwt_required()
def education_update(id):
    """PUT /api/content/educations/<id>"""
    user = _get_current_user()
    edu  = CandidateEducation.query.filter_by(id=id, user_id=user.id).first_or_404()
    body = request.get_json() or {}

    is_latest = body.get('is_latest')
    if is_latest:
        CandidateEducation.query.filter_by(user_id=user.id).update({'is_latest': False})
        edu.is_latest = True

    for field in ['degree', 'institution', 'major', 'graduation_year']:
        if field in body:
            setattr(edu, field, body[field])
    if 'gpa' in body:
        edu.gpa = body['gpa']
    if 'gpa_scale' in body:
        edu.gpa_scale = float(body['gpa_scale'])

    db.session.commit()
    return success(data=edu.to_dict(), message="Pendidikan berhasil diperbarui.")


@jwt_required()
def education_destroy(id):
    """DELETE /api/content/educations/<id>"""
    user = _get_current_user()
    edu  = CandidateEducation.query.filter_by(id=id, user_id=user.id).first_or_404()
    db.session.delete(edu)
    db.session.commit()
    return success(message="Pendidikan berhasil dihapus.")


# ─────────────────────────────────────────────────────────────
# LIHAT REKRUTMEN AKTIF (untuk kandidat)
# ─────────────────────────────────────────────────────────────

@jwt_required()
def recruitment_list():
    """GET /api/content/recruitments — Daftar rekrutmen aktif + status aplikasi user."""
    from app.models import CandidateApplication
    user = _get_current_user()
    items = Recruitment.query.filter_by(status='active').all()
    result = []
    for r in items:
        positions = []
        for p in r.positions.filter_by(status='active'):
            app = CandidateApplication.query.filter_by(
                user_id=user.id, position_id=p.id
            ).first()
            positions.append({
                'id':                    p.id,
                'title':                 p.title,
                'description':           p.description,
                'quota':                 p.quota,
                'my_application_status': app.status if app else None,
                'my_application_id':     app.id if app else None,
            })
        active_reqs = r.requirements.filter(RecruitmentRequirement.weight > 0).all()
        result.append({
            'id':                r.id,
            'code':              r.code,
            'title':             r.title,
            'description':       r.description,
            'assessment_weight': r.get_assessment_weight(),
            'published_at':      r.published_at.isoformat() if r.published_at else None,
            'positions':         positions,
            'requirements': [
                {
                    'weight':       float(rq.weight),
                    'is_mandatory': rq.is_mandatory,
                    'requirement_type': {'name': rq.requirement_type.name},
                }
                for rq in active_reqs
            ],
        })
    return success(data=result)


@jwt_required()
def recruitment_detail(recruitment_id):
    """GET /api/content/recruitments/<id> — Detail rekrutmen + info syarat."""
    r = Recruitment.query.filter_by(id=recruitment_id, status='active').first_or_404()
    user = _get_current_user()

    positions = []
    for p in r.positions.filter_by(status='active'):
        # Cek apakah kandidat sudah mendaftar ke posisi ini
        app = CandidateApplication.query.filter_by(
            user_id=user.id, position_id=p.id
        ).first()
        positions.append({
            'id': p.id,
            'title': p.title,
            'description': p.description,
            'quota': p.quota,
            'criteria_count': p.criteria_setup.count(),
            'my_application_status': app.status if app else None,
            'my_application_id': app.id if app else None,
        })

    active_reqs = r.requirements.filter(RecruitmentRequirement.weight > 0).all()
    return success(data={
        'id': r.id,
        'code': r.code,
        'title': r.title,
        'description': r.description,
        'assessment_weight': r.get_assessment_weight(),
        'positions': positions,
        'requirements': [rq.to_dict() for rq in active_reqs],
    })


# ─────────────────────────────────────────────────────────────
# PENDAFTARAN KANDIDAT
# ─────────────────────────────────────────────────────────────

@jwt_required()
def apply(position_id):
    """
    POST /api/content/apply/<position_id>
    Kandidat mendaftar ke posisi tertentu.
    """
    user = _get_current_user()
    pos  = RecruitmentPosition.query.filter_by(
        id=position_id, status='active'
    ).first_or_404()

    # Cek sudah daftar?
    existing = CandidateApplication.query.filter_by(
        user_id=user.id, position_id=position_id
    ).first()
    if existing:
        return error("Kamu sudah mendaftar ke posisi ini.", 409)

    app = CandidateApplication(
        user_id=user.id,
        position_id=position_id,
        status='registered',
    )
    db.session.add(app)
    db.session.commit()
    return success(data=app.to_dict(), message="Berhasil mendaftar. Silakan isi form assessment.", code=201)


@jwt_required()
def my_applications():
    """GET /api/content/my-applications — Daftar aplikasi kandidat."""
    user = _get_current_user()
    apps = CandidateApplication.query.filter_by(user_id=user.id).all()
    return success(data=[a.to_dict() for a in apps])


# ─────────────────────────────────────────────────────────────
# FORM ASSESSMENT
# ─────────────────────────────────────────────────────────────

@jwt_required()
def assessment_questions(application_id):
    """
    GET /api/content/applications/<id>/questions
    Ambil semua pertanyaan assessment untuk aplikasi ini.
    PENTING: option_value TIDAK dikirim ke kandidat (tersembunyi).
    Pertanyaan diurutkan secara acak agar tidak mudah ditebak polanya.
    """
    import random
    user = _get_current_user()
    app  = CandidateApplication.query.filter_by(
        id=application_id, user_id=user.id
    ).first_or_404()

    if app.status not in ['registered', 'in_progress']:
        return error("Form assessment sudah tidak bisa diakses (status: {}).".format(app.status), 422)

    # Update status ke in_progress
    if app.status == 'registered':
        app.status = 'in_progress'
        db.session.commit()

    pc_list = PositionCriteria.query.filter_by(
        position_id=app.position_id
    ).all()

    all_questions = []
    for pc in pc_list:
        for q in pc.questions.filter_by(is_active=True).all():
            all_questions.append({
                'question_id': q.id,
                'question_text': q.question_text,
                # Kirim opsi tanpa option_value
                'options': [o.to_candidate_dict() for o in
                            q.options.order_by(AssessmentOption.display_order)],
            })

    # Acak urutan pertanyaan agar tidak ketahuan pola kriterianya
    random.shuffle(all_questions)

    # Ambil requirements rekrutmen yang perlu diisi kandidat
    recruitment = app.position.recruitment
    req_infos = []
    for rr in recruitment.requirements.filter(RecruitmentRequirement.weight > 0).all():
        rt = rr.requirement_type
        req_infos.append({
            'recruitment_requirement_id': rr.id,
            'name':         rt.name,
            'value_type':   rt.value_type,
            'min_value':    float(rt.min_value),
            'max_value':    float(rt.max_value),
            'unit':         rt.unit,
            'is_mandatory': rr.is_mandatory,
        })

    return success(data={
        'application_id':  application_id,
        'position_title':  app.position.title,
        'total_questions': len(all_questions),
        'questions':       all_questions,
        'requirements':    req_infos,
    })


@jwt_required()
def assessment_submit(application_id):
    """
    POST /api/content/applications/<id>/submit
    Submit semua jawaban assessment + nilai syarat tambahan sekaligus.

    Body:
    {
      "answers": [
        {"question_id": 1, "option_id": 3},
        {"question_id": 2, "option_id": 7},
        ...
      ],
      "requirements": [
        {"recruitment_requirement_id": 1, "raw_value": 3.75},  ← IPK
        {"recruitment_requirement_id": 2, "raw_value": 520},   ← TOEFL
        {"recruitment_requirement_id": 3, "raw_value": 3},     ← Sertifikat
      ]
    }
    """
    user = _get_current_user()
    app  = CandidateApplication.query.filter_by(
        id=application_id, user_id=user.id
    ).first_or_404()

    if app.status not in ['registered', 'in_progress']:
        return error("Aplikasi sudah disubmit sebelumnya.", 422)

    body    = request.get_json() or {}
    answers = body.get('answers', [])
    reqs    = body.get('requirements', [])

    if not answers:
        return error("Jawaban assessment tidak boleh kosong.", 422)

    # Validasi & simpan jawaban
    AssessmentAnswer.query.filter_by(application_id=app.id).delete()
    for ans in answers:
        q_id  = ans.get('question_id')
        opt_id = ans.get('option_id')

        q   = AssessmentQuestion.query.get(q_id)
        opt = AssessmentOption.query.filter_by(id=opt_id, question_id=q_id).first()

        if not q or not opt:
            return error(f"Pertanyaan {q_id} atau pilihan {opt_id} tidak valid.", 422)

        a = AssessmentAnswer(
            application_id=app.id,
            question_id=q_id,
            option_id=opt_id,
            # Salin nilai saat submit agar tidak berubah meski admin edit option nanti
            answer_value=opt.option_value,
        )
        db.session.add(a)

    # Simpan nilai syarat tambahan
    CandidateRequirement.query.filter_by(application_id=app.id).delete()
    for r in reqs:
        rr_id = r.get('recruitment_requirement_id')
        val   = r.get('raw_value', 0)

        # Bug #11 fix: validasi range nilai terhadap RequirementType.min_value / max_value
        rr = RecruitmentRequirement.query.get(rr_id)
        if rr:
            rt = rr.requirement_type
            try:
                val_float = float(val)
            except (TypeError, ValueError):
                db.session.rollback()
                return error(f"Nilai '{rt.name}' harus berupa angka.", 422)

            if val_float < float(rt.min_value) or val_float > float(rt.max_value):
                db.session.rollback()
                return error(
                    f"Nilai '{rt.name}' harus antara {rt.min_value} dan {rt.max_value}. "
                    f"Nilai yang dikirim: {val_float}.",
                    422
                )
            val = val_float

        cr = CandidateRequirement(
            application_id=app.id,
            recruitment_requirement_id=rr_id,
            raw_value=val,
        )
        db.session.add(cr)

    # Cek mandatory requirements
    recruitment = app.position.recruitment
    mandatory_reqs = RecruitmentRequirement.query.filter_by(
        recruitment_id=recruitment.id,
        is_mandatory=True,
    ).filter(RecruitmentRequirement.weight > 0).all()

    submitted_req_ids = {r.get('recruitment_requirement_id') for r in reqs}
    for mr in mandatory_reqs:
        if mr.id not in submitted_req_ids:
            db.session.rollback()
            return error(
                f"Syarat '{mr.requirement_type.name}' wajib diisi.", 422
            )


    # Update status
    app.status       = 'submitted'
    app.submitted_at = datetime.utcnow()
    db.session.commit()

    return success(
        data={'application_id': app.id, 'status': app.status},
        message="Assessment berhasil disubmit. Tunggu hasil seleksi."
    )


# ─────────────────────────────────────────────────────────────
# LIHAT HASIL (kandidat)
# ─────────────────────────────────────────────────────────────

@jwt_required()
def my_result(application_id):
    """
    GET /api/content/applications/<id>/result
    Kandidat melihat hasil ranking dirinya sendiri.
    Hanya tampil setelah admin generate ranking.
    """
    user = _get_current_user()
    app  = CandidateApplication.query.filter_by(
        id=application_id, user_id=user.id
    ).first_or_404()

    ranking = app.ranking_result
    if not ranking:
        return error("Hasil belum tersedia. Proses seleksi masih berlangsung.", 404)

    return success(data={
        'application_id': app.id,
        'position': app.position.title,
        'status': app.status,
        'final_rank': ranking.final_rank,
        'final_status': ranking.final_status,
        'is_recommended': ranking.is_recommended,
    })
