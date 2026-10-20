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
    Lihat ranking kandidat per posisi (dua lintasan: A=Fuzzy-ELECTRE, B=Fuzzy-TOPSIS),
    termasuk metrik perbandingan (ρ, τ, durasi, konvergensi PSO) dari log terakhir.
    """
    pos = RecruitmentPosition.query.get_or_404(position_id)
    rankings = RankingResult.query.filter_by(
        position_id=position_id
    ).order_by(RankingResult.rank_a).all()

    if not rankings:
        return error("Ranking belum di-generate untuk posisi ini.", 404)

    # Skor per lintasan dari scoring_results (skor A = min-max net ELECTRE ×100,
    # skor B = min-max closeness TOPSIS ×100 — rumus sama dengan generate_ranking)
    app_ids = [r.application_id for r in rankings]
    scoring_results = ScoringResult.query.filter(
        ScoringResult.application_id.in_(app_ids)
    ).all()
    sr_by_app = {sr.application_id: sr for sr in scoring_results}
    nets   = [float(sr_by_app[r.application_id].electre_net_ml or 0) if sr_by_app.get(r.application_id) else 0.0 for r in rankings]
    closes = [float(sr_by_app[r.application_id].closeness_b or 0) if sr_by_app.get(r.application_id) else 0.0 for r in rankings]
    net_lo, net_hi = min(nets), max(nets)
    cl_lo,  cl_hi  = min(closes), max(closes)
    def sk_a(v): return 100.0 if net_hi == net_lo else round((v - net_lo) / (net_hi - net_lo) * 100, 2)
    def sk_b(v): return 100.0 if cl_hi == cl_lo else round((v - cl_lo) / (cl_hi - cl_lo) * 100, 2)

    # Bobot per kriteria (bobot manual hanya baseline justifikasi)
    weights = MlWeightResult.query.filter_by(position_id=position_id).all()

    # Log proses terakhir yang completed → sumber panel perbandingan & kurva PSO
    # MySQL: DESC sudah menempatkan NULL paling akhir (NULLS LAST adalah
    # sintaks PostgreSQL dan bikin error 1064 di MySQL).
    log_last = MlProcessLog.query.filter_by(
        position_id=position_id, status='completed'
    ).order_by(MlProcessLog.processed_at.desc(),
               MlProcessLog.id.desc()).first()
    process_info = None
    if log_last:
        params = log_last.pso_parameters or {}
        process_info = {
            'pso_converged': bool(log_last.pso_converged),
            'pso_iterations': log_last.pso_iterations_used,
            'pso_best_fitness': float(log_last.pso_best_fitness) if log_last.pso_best_fitness is not None else None,
            'pso_fitness_history': params.get('fitness_history') or [],
            'spearman_correlation': float(log_last.spearman_correlation) if log_last.spearman_correlation is not None else None,
            'kendall_tau': float(log_last.kendall_tau) if log_last.kendall_tau is not None else None,
            'rank_changes_count': log_last.rank_changes_count,
            'total_candidates': log_last.total_candidates,
            'process_duration_ms': log_last.process_duration_ms,
            'processed_at': log_last.processed_at.isoformat() if log_last.processed_at else None,
        }

    ranking_items = []
    for i, r in enumerate(rankings):
        item = r.to_dict()
        item['skor_a'] = sk_a(nets[i])          # skor Lintasan A (0-100)
        item['skor_b'] = sk_b(closes[i])        # skor Lintasan B (0-100)
        item['closeness_b'] = round(closes[i], 4)
        item['electre_net_ml'] = round(nets[i], 4)
        item['d_rank'] = (r.rank_a or 0) - (r.rank_b or 0)  # displacement
        ranking_items.append(item)

    return success(data={
        'position_id': position_id,
        'position_title': pos.title,
        'quota': pos.quota,
        'ranking': ranking_items,
        'weight_comparison': [w.to_dict() for w in weights],
        'process_info': process_info,
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
# FINALIZE: keputusan akhir (Human-in-the-Loop dua lintasan)
# ─────────────────────────────────────────────────────────────

@jwt_required()
@admin_required
def finalize_position(position_id):
    """
    POST /api/report/ranking/<position_id>/finalize
    Finalize otomatis seluruh kandidat satu posisi:
      - masuk kuota pada KEDUA lintasan → accepted
      - masuk kuota pada SATU lintasan → review (perlu konfirmasi admin)
      - sisanya → rejected
    final_rank / final_score diambil dari Lintasan A (ELECTRE).
    """
    rankings = RankingResult.query.filter_by(
        position_id=position_id
    ).all()

    if not rankings:
        return error("Ranking belum di-generate.", 404)

    pos = RecruitmentPosition.query.get_or_404(position_id)
    quota = pos.quota

    counts = {'accepted': 0, 'review': 0, 'rejected': 0}
    for rr in rankings:
        ra, rb = rr.rank_a if rr.rank_a is not None else rr.rank_ml, rr.rank_b
        in_a, in_b = (ra is not None and ra <= quota), (rb is not None and rb <= quota)
        if in_a and in_b:
            status = 'accepted'
        elif in_a or in_b:
            status = 'review'
        else:
            status = 'rejected'
        rr.final_status = status
        rr.final_rank  = ra
        rr.final_score = rr.final_score_ml
        rr.is_recommended = in_a
        counts[status] = counts.get(status, 0) + 1

    db.session.commit()
    return success(
        message="Finalize otomatis selesai: 2 lintasan dipertimbangkan bersama.",
        data={'auto_status_counts': counts, 'quota': quota,
              'ranking': [r.to_dict() for r in rankings]}
    )


@jwt_required()
@admin_required
def finalize_candidate(position_id, application_id):
    """
    POST /api/report/ranking/<position_id>/finalize/<application_id>
    Admin menetapkan status akhir satu kandidat (penyesuaian manual atas
    hasil finalize otomatis): accepted / rejected / review (atau pending).
    Body: {"status": "accepted", "notes": "..."}
    """
    rr  = RankingResult.query.filter_by(
        position_id=position_id,
        application_id=application_id,
    ).first_or_404()

    body   = request.get_json() or {}
    status = body.get('status', 'pending')

    if status not in ['accepted', 'rejected', 'pending', 'review']:
        return error("Status harus 'accepted', 'rejected', 'review', atau 'pending'.", 422)

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
