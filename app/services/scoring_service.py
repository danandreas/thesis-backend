"""
Service: ScoringService
Orkestrator utama yang menggabungkan semua algoritma:
  Fuzzy → EWM → PSO → Lintasan A (ELECTRE) + Lintasan B (TOPSIS) → Ranking

Alur lengkap saat admin klik tombol "Generate Ranking":
  1. Ambil semua aplikasi yang sudah submitted untuk satu posisi
  2. Hitung raw_score per kriteria (rata-rata jawaban Likert)
  3. Fuzzy: konversi raw_score ke fuzzy_value (shoulder_right, mid dari db)
  4. EWM: hitung bobot objektif dari distribusi data
  5. PSO: penyempurnaan bobot EWM (init EWM + Gaussian; fitness ter-regularisasi)
     — bobot manual pakar KELUAR dari perhitungan (hanya baseline justifikasi)
  6. Lintasan A (Fuzzy-ELECTRE)  : concordance → discordance → net → peringkat
  7. Lintasan B (Fuzzy-TOPSIS)   : solusi ideal → jarak → closeness → peringkat
     Kedua lintasan memakai matriks v = r × w yang sama (perbandingan terkontrol)
  8. Normalisasi syarat tambahan (IPK, TOEFL, sertifikat)
  9. Hitung final score gabungan (assessment Lintasan A + syarat)
 10. Simpan semua hasil ke database (rank_a, rank_b, closeness_b, ρ, τ)
 11. Return ringkasan hasil A-vs-B
"""

import time
from datetime import datetime

import numpy as np
from scipy.stats import spearmanr, kendalltau

from app import db
from app.models.candidate import (
    CandidateApplication, AssessmentAnswer, CandidateRequirement
)
from app.models.recruitment import (
    RecruitmentPosition, PositionCriteria,
    RecruitmentRequirement
)
from app.models.scoring import (
    CriteriaScore, MlWeightResult, ScoringResult,
    RankingResult, MlProcessLog
)
from app.services.fuzzy_service import FuzzyService
from app.services.ewm_service import EWMService
from app.services.pso_service import PSOService
from app.services.electre_service import ELECTREService
from app.services.topsis_service import TOPSISService


class ScoringService:

    @staticmethod
    def generate_ranking(position_id: int, triggered_by: int) -> dict:
        """
        Entry point utama — dipanggil saat admin klik "Generate Ranking".

        Parameters:
            position_id  : ID posisi yang akan diproses
            triggered_by : ID admin yang menjalankan proses

        Returns:
            dict berisi hasil ranking A-vs-B dan metadata proses
        """
        start_time = time.time()

        # Buat log awal
        log = MlProcessLog(
            position_id=position_id,
            triggered_by=triggered_by,
            status='processing',
        )
        db.session.add(log)
        db.session.commit()

        try:
            result = ScoringService._process(position_id, triggered_by, log)
            duration_ms = int((time.time() - start_time) * 1000)
            log.status              = 'completed'
            log.process_duration_ms = duration_ms
            log.processed_at        = datetime.utcnow()
            db.session.commit()
            result['process_duration_ms'] = duration_ms
            return result

        except Exception as e:
            log.status        = 'failed'
            log.error_message = str(e)
            db.session.commit()
            raise e

    @staticmethod
    def _process(position_id: int, triggered_by: int, log: MlProcessLog) -> dict:
        """Proses internal scoring lengkap (dua lintasan)."""

        # ── STEP 1: Load data posisi & aplikasi ──────────────────────────
        position = RecruitmentPosition.query.get_or_404(position_id)
        recruitment = position.recruitment

        # Hanya proses aplikasi yang sudah submitted atau verified
        applications = CandidateApplication.query.filter(
            CandidateApplication.position_id == position_id,
            CandidateApplication.status.in_(['submitted', 'verified', 'scored'])
        ).all()

        if not applications:
            raise ValueError("Tidak ada aplikasi yang bisa diproses untuk posisi ini.")

        # Load setup kriteria untuk posisi ini (urut by display_order)
        pc_list = PositionCriteria.query.filter_by(
            position_id=position_id
        ).order_by(PositionCriteria.display_order).all()

        if not pc_list:
            raise ValueError("Posisi belum memiliki setup kriteria.")

        n_candidates = len(applications)
        n_criteria   = len(pc_list)
        log.total_candidates = n_candidates

        # ── STEP 2: Hitung raw_score per kriteria per kandidat ────────────
        # raw_score = rata-rata nilai jawaban Likert untuk semua pertanyaan
        # dalam satu kriteria
        raw_matrix = []  # [n_kandidat × n_kriteria]

        for app in applications:
            row = []
            for pc in pc_list:
                # Ambil semua jawaban kandidat untuk pertanyaan kriteria ini
                question_ids = [q.id for q in pc.questions.all()]
                if not question_ids:
                    row.append(0.0)
                    continue

                answers = AssessmentAnswer.query.filter(
                    AssessmentAnswer.application_id == app.id,
                    AssessmentAnswer.question_id.in_(question_ids)
                ).all()

                if answers:
                    avg = sum(float(a.answer_value) for a in answers) / len(answers)
                else:
                    avg = 0.0
                row.append(round(avg, 4))
            raw_matrix.append(row)

        # ── STEP 3: Fuzzy — konversi raw_score ke fuzzy_value ────────────
        # Untuk setiap kriteria, konversi nilai mentah ke derajat fuzzy
        fuzzy_matrix = []  # [n_kandidat × n_kriteria]

        for row in raw_matrix:
            fuzzy_row = []
            for j, pc in enumerate(pc_list):
                fuzzy_val = FuzzyService.shoulder_right_membership(
                    value=row[j],
                    low=float(pc.fuzzy_low),
                    mid=float(pc.fuzzy_mid),
                    high=float(pc.fuzzy_high),
                )
                fuzzy_row.append(fuzzy_val)
            fuzzy_matrix.append(fuzzy_row)

        # ── STEP 4: EWM — hitung bobot objektif ──────────────────────────
        ewm_result = EWMService.compute_weights(fuzzy_matrix)
        ewm_weights = ewm_result['weights']

        log.ewm_entropy_values = ewm_result['entropy']
        log.ewm_weights        = {pc_list[j].criteria.code: ewm_weights[j]
                                   for j in range(n_criteria)}

        # ── STEP 5: Bobot manual (hanya baseline justifikasi tabel) ──────
        # Bobot manual TIDAK IKUT dalam perhitungan (init PSO maupun ranking)
        raw_manual = [float(pc.weight_manual) for pc in pc_list]
        total_manual = sum(raw_manual) or 1.0
        manual_weights_norm = [w / total_manual for w in raw_manual]

        # ── STEP 6: PSO — penyempurnaan bobot EWM ────────────────────────
        pso = PSOService(n_particles=30, max_iterations=100)
        pso_result = pso.optimize_weights(
            ewm_weights=ewm_weights,
            decision_matrix=fuzzy_matrix,
        )
        pso_weights = pso_result['optimal_weights']

        log.pso_parameters   = PSOService.parameters_dict({
            'fitness_history': [round(float(v), 6) for v in pso_result['history']],
        })
        log.pso_best_weights = {pc_list[j].criteria.code: pso_weights[j] for j in range(n_criteria)}
        log.pso_best_fitness = pso_result['best_fitness']
        log.pso_iterations_used = pso_result['iterations_used']
        log.pso_converged    = pso_result['converged']

        # Simpan criteria_scores ke DB (dengan bobot PSO)
        generated_at = datetime.utcnow()
        criteria_types = [pc.criteria_type for pc in pc_list]
        for i, app in enumerate(applications):
            for j, pc in enumerate(pc_list):
                # Hapus score lama jika ada (re-generate)
                CriteriaScore.query.filter_by(
                    application_id=app.id,
                    position_criteria_id=pc.id
                ).delete()
                score = CriteriaScore(
                    application_id=app.id,
                    position_criteria_id=pc.id,
                    raw_score=raw_matrix[i][j],
                    fuzzy_value=fuzzy_matrix[i][j],
                    weighted_score=round(fuzzy_matrix[i][j] * pso_weights[j], 4),
                )
                db.session.add(score)
        db.session.flush()

        # Simpan ml_weight_results ke DB (manual disimpan sbg baseline saja)
        MlWeightResult.query.filter_by(position_id=position_id).delete()
        for j, pc in enumerate(pc_list):
            mwr = MlWeightResult(
                position_id=position_id,
                position_criteria_id=pc.id,
                weight_manual=manual_weights_norm[j],
                weight_ewm=ewm_weights[j],
                weight_final=pso_weights[j],
                weight_difference=pso_weights[j] - ewm_weights[j],  # PSO − EWM
                generated_at=generated_at,
                pso_iterations=pso_result['iterations_used'],
                pso_best_fitness=pso_result['best_fitness'],
            )
            db.session.add(mwr)
        db.session.flush()

        # ── STEP 7: Dua lintasan dengan input identik ────────────────────
        t0 = time.perf_counter()
        electre_lane_a = ELECTREService.compute(       # Lintasan A
            decision_matrix=fuzzy_matrix,
            weights=pso_weights,
            criteria_types=criteria_types,
        )
        duration_a_ms = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        topsis_lane_b = TOPSISService.compute(         # Lintasan B
            decision_matrix=fuzzy_matrix,
            weights=pso_weights,
            criteria_types=criteria_types,
        )
        duration_b_ms = (time.perf_counter() - t0) * 1000

        # Durasi per lintasan ikut ke log (dibaca ulang pada GET ranking)
        log.pso_parameters = {
            **(log.pso_parameters or {}),
            'duration_a_ms': round(duration_a_ms, 3),
            'duration_b_ms': round(duration_b_ms, 3),
        }

        rank_a = electre_lane_a['ranking']
        rank_b = topsis_lane_b['ranking']

        # ── STEP 8: Normalisasi syarat tambahan ──────────────────────────
        # IPK, TOEFL, sertifikat → normalized 0-100
        req_scores = ScoringService._compute_requirement_scores(
            applications=applications,
            recruitment=recruitment,
        )

        # Bobot komponen penilaian
        assessment_weight = recruitment.get_assessment_weight() / 100  # jadi 0-1
        req_weight        = 1.0 - assessment_weight

        # ── STEP 9: Final score & simpan scoring_results ─────────────────
        final_scores = []  # assessment Lintasan A + syarat (dasar keputusan)

        for i, app in enumerate(applications):
            # Net score ELECTRE sebagai assessment score → min-max ke 0-100
            net_scores_a = electre_lane_a['net_score']
            assess_a = ScoringService._minmax_scale(
                net_scores_a[i], net_scores_a
            ) * 100
            # Peringkat Lintasan A sebagai dasar final score (legacy kolom _ml)
            closeness_b = topsis_lane_b['closeness'][i]

            req_score = req_scores.get(app.id, 0.0)

            final = (assess_a * assessment_weight) + (req_score * req_weight)
            final_scores.append(final)

            # Simpan ke scoring_results (kolom _manual disisakan NULL:
            # bobot manual tidak lagi dihitung sistem)
            ScoringResult.query.filter_by(application_id=app.id).delete()
            sr = ScoringResult(
                application_id=app.id,
                assessment_score_manual=None,
                assessment_score_ml=round(assess_a, 4),
                requirements_score=round(req_score, 4),
                electre_concordance_manual=None,
                electre_discordance_manual=None,
                electre_net_manual=None,
                electre_concordance_ml=electre_lane_a['net_concordance'][i],
                electre_discordance_ml=electre_lane_a['net_discordance'][i],
                electre_net_ml=electre_lane_a['net_score'][i],
                closeness_b=closeness_b,
                d_plus_b=round(topsis_lane_b['distance_positive'][i], 6),
                d_minus_b=round(topsis_lane_b['distance_negative'][i], 6),
                final_score_manual=None,
                final_score_ml=round(final, 4),
                generated_at=generated_at,
                generated_by=triggered_by,
            )
            db.session.add(sr)

            # Update status aplikasi
            app.status = 'scored'

        db.session.flush()

        # ── STEP 10: Ranking kedua lintasan ──────────────────────────────
        RankingResult.query.filter_by(position_id=position_id).delete()

        quota = position.quota
        for i, app in enumerate(applications):
            rr = RankingResult(
                position_id=position_id,
                application_id=app.id,
                rank_manual=None,                       # bobot manual keluar
                final_score_manual=None,
                rank_ml=rank_a[i],                      # legacy: dasar rekomendasi
                final_score_ml=round(final_scores[i], 4),
                rank_a=rank_a[i],
                rank_b=rank_b[i],
                is_recommended=(rank_a[i] <= quota),
                final_status='pending',
                generated_at=generated_at,
            )
            db.session.add(rr)

        db.session.flush()

        # ── STEP 11: Kesepakatan antar lintasan (ρ & τ) ──────────────────
        if n_candidates >= 3:
            corr, _ = spearmanr(rank_a, rank_b)
            log.spearman_correlation = round(float(corr), 4)
            tau, _ = kendalltau(rank_a, rank_b)
            log.kendall_tau = round(float(tau), 4)
        log.rank_changes_count = sum(1 for a, b in zip(rank_a, rank_b) if a != b)
        db.session.commit()

        # Susun response
        ranking_summary = []
        for i, app in enumerate(applications):
            ranking_summary.append({
                'application_id': app.id,
                'candidate_name': app.user.name,
                'candidate_email': app.user.email,
                'rank_a': rank_a[i],
                'skor_a': electre_lane_a['score'][i],
                # Metrik asli Lintasan A (ELECTRE) — berbeda semesta dgn Skor A
                'net_concordance_a': electre_lane_a['net_concordance'][i],
                'net_discordance_a': electre_lane_a['net_discordance'][i],
                'net_a': electre_lane_a['net_score'][i],
                'rank_b': rank_b[i],
                'skor_b': topsis_lane_b['score'][i],
                'closeness_b': topsis_lane_b['closeness'][i],
                # Metrik asli Lintasan B (TOPSIS)
                'd_plus_b': round(topsis_lane_b['distance_positive'][i], 6),
                'd_minus_b': round(topsis_lane_b['distance_negative'][i], 6),
                'rank_ml': rank_a[i],            # legacy frontend lama
                'final_score_ml': round(final_scores[i], 4),
                'is_recommended': rank_a[i] <= quota,
                'final_status': 'pending',
            })

        # Urutkan berdasarkan rank_a untuk tampilan
        ranking_summary.sort(key=lambda x: x['rank_a'])

        return {
            'position_id': position_id,
            'position_title': position.title,
            'total_candidates': n_candidates,
            'quota': quota,
            'assessment_weight_pct': round(assessment_weight * 100, 2),
            'requirement_weight_pct': round(req_weight * 100, 2),
            'pso_converged': pso_result['converged'],
            'pso_iterations': pso_result['iterations_used'],
            'pso_best_fitness': round(pso_result['best_fitness'], 6),
            'spearman_correlation': log.spearman_correlation,
            'kendall_tau': log.kendall_tau,
            'rank_agreement': log.rank_changes_count == 0,
            'duration_a_ms': round(duration_a_ms, 2),
            'duration_b_ms': round(duration_b_ms, 2),
            'ranking': ranking_summary,
            'weight_comparison': [
                {
                    'criteria_code': pc_list[j].criteria.code,
                    'criteria_name': pc_list[j].criteria.name,
                    'weight_manual': round(manual_weights_norm[j], 6),  # baseline
                    'weight_ewm': round(ewm_weights[j], 6),
                    'weight_ml': round(pso_weights[j], 6),
                    'difference': round(pso_weights[j] - ewm_weights[j], 6),
                }
                for j in range(n_criteria)
            ],
        }

    @staticmethod
    def _compute_requirement_scores(applications, recruitment) -> dict:
        """
        Hitung skor gabungan syarat tambahan (IPK, TOEFL, sertifikat, dll)
        dalam skala 0-100 untuk setiap aplikasi.

        Rumus per syarat:
          normalized = (raw_value - min) / (max - min)  → 0-1
          contribution = normalized × weight_syarat

        Rumus total:
          req_score = Σ(contribution) / Σ(weight_aktif) × 100
        """
        # Load semua requirement yang aktif (weight > 0)
        active_reqs = RecruitmentRequirement.query.filter(
            RecruitmentRequirement.recruitment_id == recruitment.id,
            RecruitmentRequirement.weight > 0
        ).all()

        if not active_reqs:
            return {app.id: 0.0 for app in applications}

        result = {}
        total_req_weight = sum(float(r.weight) for r in active_reqs)

        for app in applications:
            total_score = 0.0
            for req in active_reqs:
                # Cari nilai kandidat untuk syarat ini
                cand_req = CandidateRequirement.query.filter_by(
                    application_id=app.id,
                    recruitment_requirement_id=req.id
                ).first()

                if not cand_req:
                    continue

                raw = float(cand_req.raw_value)
                rtype = req.requirement_type
                min_v = float(rtype.min_value)
                max_v = float(rtype.max_value)

                # Normalisasi ke 0-1
                norm = FuzzyService.normalize_to_range(raw, min_v, max_v)

                # Update normalized_score di DB
                cand_req.normalized_score = norm

                # Kontribusi ke total (dalam persentase bobot)
                total_score += norm * float(req.weight)

            # Konversi ke skala 0-100 relatif terhadap total bobot syarat
            result[app.id] = round((total_score / total_req_weight) * 100, 4) if total_req_weight > 0 else 0.0

        return result

    @staticmethod
    def _minmax_scale(value: float, all_values: list) -> float:
        """Normalisasi satu nilai ke rentang 0-1 berdasarkan min-max dari list."""
        min_v = min(all_values)
        max_v = max(all_values)
        if max_v == min_v:
            return 1.0
        return (value - min_v) / (max_v - min_v)