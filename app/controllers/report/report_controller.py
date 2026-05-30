"""
Controller: Report - Laporan & Hasil Seleksi
Endpoint untuk admin melihat hasil, generate ranking, dan membuat keputusan.
Prefix URL: /api/report/...
"""
from flask import request
from flask_jwt_extended import jwt_required, get_jwt_identity

from app import db
from app.models import (
    Recruitment, RecruitmentPosition, CandidateApplication,
    CandidateRequirement, RankingResult, ScoringResult,
    CriteriaScore, MlWeightResult, MlProcessLog
)
from app.helpers.response import success, error
from app.middleware.auth_middleware import admin_required
from app.services.scoring_service import ScoringService


# ─────────────────────────────────────────────────────────────
# GENERATE RANKING
# ─────────────────────────────────────────────────────────────

@jwt_required()
@admin_required
def generate_ranking(position_id):
    """
    POST /api/report/generate/<position_id>
    Admin menekan tombol Generate Ranking.
    Menjalankan: Fuzzy → EWM → PSO → ELECTRE → Ranking

    Proses bisa memakan waktu 1-10 detik tergantung jumlah kandidat.
    """
    admin_id = get_jwt_identity()
    pos = RecruitmentPosition.query.get_or_404(position_id)

    if pos.recruitment.status not in ['active', 'closed']:
        return error("Generate hanya bisa dilakukan untuk rekrutmen aktif atau yang sudah ditutup.", 422)

    try:
        result = ScoringService.generate_ranking(
            position_id=position_id,
            triggered_by=admin_id,
        )
        return success(data=result, message="Ranking berhasil di-generate.")
    except ValueError as e:
        return error(str(e), 422)
    except Exception as e:
        return error(f"Terjadi kesalahan saat proses: {str(e)}", 500)


# ─────────────────────────────────────────────────────────────
# LIHAT RANKING
# ─────────────────────────────────────────────────────────────

@jwt_required()
@admin_required
def ranking_by_position(position_id):
    """
    GET /api/report/ranking/<position_id>
    Lihat ranking kandidat per posisi (dua versi: manual vs ML).
    """
    pos = RecruitmentPosition.query.get_or_404(position_id)
    rankings = RankingResult.query.filter_by(
        position_id=position_id
    ).order_by(RankingResult.rank_ml).all()

    if not rankings:
        return error("Ranking belum di-generate untuk posisi ini.", 404)

    # Bobot per kriteria (perbandingan manual vs ML)
    weights = MlWeightResult.query.filter_by(position_id=position_id).all()

    return success(data={
        'position_id': position_id,
        'position_title': pos.title,
        'quota': pos.quota,
        'ranking': [r.to_dict() for r in rankings],
        'weight_comparison': [w.to_dict() for w in weights],
    })


@jwt_required()
@admin_required
def ranking_detail(position_id, application_id):
    """
    GET /api/report/ranking/<position_id>/detail/<application_id>
    Detail skor satu kandidat: skor per kriteria + syarat tambahan.
    """
    rr = RankingResult.query.filter_by(
        position_id=position_id,
        application_id=application_id,
    ).first_or_404()

    app = rr.application
    sr  = ScoringResult.query.filter_by(application_id=application_id).first()

    # Skor per kriteria
    criteria_scores = CriteriaScore.query.filter_by(
        application_id=application_id
    ).all()

    # Nilai syarat tambahan
    req_scores = CandidateRequirement.query.filter_by(
        application_id=application_id
    ).all()

    return success(data={
        'candidate': {
            'id': app.user.id,
            'name': app.user.name,
            'email': app.user.email,
        },
        'ranking': rr.to_dict(),
        'scoring': sr.to_dict() if sr else None,
        'criteria_scores': [cs.to_dict() for cs in criteria_scores],
        'requirement_scores': [r.to_dict() for r in req_scores],
    })


# ─────────────────────────────────────────────────────────────
# HUMAN-IN-THE-LOOP: Admin memilih versi ranking
# ─────────────────────────────────────────────────────────────

@jwt_required()
@admin_required
def choose_ranking_version(position_id):
    """
    POST /api/report/ranking/<position_id>/choose
    Admin memilih menggunakan versi manual atau ML.
    Body: {"choice": "ml"} atau {"choice": "manual"}

    Setelah memilih, final_rank dan final_score diupdate.
    """
    body   = request.get_json() or {}
    choice = body.get('choice', 'ml')

    if choice not in ['manual', 'ml']:
        return error("Pilihan harus 'manual' atau 'ml'.", 422)

    rankings = RankingResult.query.filter_by(
        position_id=position_id
    ).all()

    if not rankings:
        return error("Ranking belum di-generate.", 404)

    pos   = RecruitmentPosition.query.get_or_404(position_id)
    quota = pos.quota

    for rr in rankings:
        rr.admin_choice = choice
        if choice == 'ml':
            rr.final_rank  = rr.rank_ml
            rr.final_score = rr.final_score_ml
        else:
            rr.final_rank  = rr.rank_manual
            rr.final_score = rr.final_score_manual
        rr.is_recommended = rr.final_rank <= quota

    db.session.commit()
    return success(
        message=f"Ranking versi '{choice}' berhasil dipilih sebagai final.",
        data={'choice': choice, 'total_updated': len(rankings)}
    )


@jwt_required()
@admin_required
def finalize_candidate(position_id, application_id):
    """
    POST /api/report/ranking/<position_id>/finalize/<application_id>
    Admin menetapkan status akhir kandidat: accepted atau rejected.
    Body: {"status": "accepted", "notes": "..."}
    """
    rr  = RankingResult.query.filter_by(
        position_id=position_id,
        application_id=application_id,
    ).first_or_404()

    body   = request.get_json() or {}
    status = body.get('status', 'pending')

    if status not in ['accepted', 'rejected', 'pending']:
        return error("Status harus 'accepted', 'rejected', atau 'pending'.", 422)

    rr.final_status = status
    app = rr.application
    app.status = status
    if body.get('notes'):
        app.notes = body['notes']

    db.session.commit()
    return success(
        message=f"Status kandidat berhasil diupdate ke '{status}'.",
        data=rr.to_dict()
    )


# ─────────────────────────────────────────────────────────────
# VERIFIKASI DOKUMEN (admin edit nilai syarat kandidat)
# ─────────────────────────────────────────────────────────────

@jwt_required()
@admin_required
def verify_requirements(application_id):
    """
    PUT /api/report/applications/<id>/verify-requirements
    Admin mengedit nilai syarat tambahan kandidat setelah
    verifikasi dokumen fisik (ijazah, sertifikat TOEFL, dll).

    Body:
    {
      "requirements": [
        {"id": 1, "raw_value": 3.75},
        {"id": 2, "raw_value": 500}
      ],
      "notes": "Dokumen sudah diverifikasi"
    }
    """
    app  = CandidateApplication.query.get_or_404(application_id)
    body = request.get_json() or {}
    reqs = body.get('requirements', [])

    for r in reqs:
        cr = CandidateRequirement.query.filter_by(
            id=r.get('id'),
            application_id=application_id
        ).first()
        if cr:
            cr.raw_value = r.get('raw_value', cr.raw_value)

    if body.get('notes'):
        app.notes = body['notes']

    # Update status ke verified
    if app.status == 'submitted':
        app.status = 'verified'
        from datetime import datetime
        app.verified_at = datetime.utcnow()
        app.verified_by = get_jwt_identity()

    db.session.commit()
    return success(message="Data syarat kandidat berhasil diverifikasi.", data=app.to_dict())


# ─────────────────────────────────────────────────────────────
# DASHBOARD SUMMARY
# ─────────────────────────────────────────────────────────────

@jwt_required()
@admin_required
def dashboard():
    """
    GET /api/report/dashboard
    Ringkasan data untuk halaman dashboard admin.
    """
    total_recruitments = Recruitment.query.count()
    active_recruitments = Recruitment.query.filter_by(status='active').count()
    total_applications = CandidateApplication.query.count()
    submitted = CandidateApplication.query.filter_by(status='submitted').count()
    accepted  = CandidateApplication.query.filter_by(status='accepted').count()
    rejected  = CandidateApplication.query.filter_by(status='rejected').count()

    # Rekrutmen aktif beserta jumlah pelamar per posisi
    active_recs = Recruitment.query.filter_by(status='active').all()
    active_summary = []
    for r in active_recs:
        positions = []
        for p in r.positions:
            app_count = p.applications.count()
            ranked    = RankingResult.query.filter_by(position_id=p.id).count()
            positions.append({
                'id': p.id,
                'title': p.title,
                'quota': p.quota,
                'applicant_count': app_count,
                'ranked': ranked > 0,
            })
        active_summary.append({
            'id': r.id,
            'code': r.code,
            'title': r.title,
            'positions': positions,
        })

    return success(data={
        'summary': {
            'total_recruitments': total_recruitments,
            'active_recruitments': active_recruitments,
            'total_applications': total_applications,
            'submitted': submitted,
            'accepted': accepted,
            'rejected': rejected,
        },
        'active_recruitments': active_summary,
    })


# ─────────────────────────────────────────────────────────────
# LOG PROSES ML
# ─────────────────────────────────────────────────────────────

@jwt_required()
@admin_required
def ml_logs(position_id):
    """
    GET /api/report/ml-logs/<position_id>
    Riwayat proses ML untuk satu posisi.
    Berguna untuk bab analisis thesis.
    """
    logs = MlProcessLog.query.filter_by(
        position_id=position_id
    ).order_by(MlProcessLog.created_at.desc()).all()
    return success(data=[l.to_dict() for l in logs])
