"""
Service: ScoringService
Orkestrator utama yang menggabungkan semua algoritma:
  Fuzzy → EWM → PSO → ELECTRE → Ranking

Alur lengkap saat admin klik tombol "Generate Ranking":
  1. Ambil semua aplikasi yang sudah submitted untuk satu posisi
  2. Hitung raw_score per kriteria (rata-rata jawaban Likert)
  3. Fuzzy: konversi raw_score ke fuzzy_value
  4. EWM: hitung bobot objektif dari distribusi data
  5. PSO: optimasi bobot (kombinasi EWM + manual admin)
  6. ELECTRE (manual): hitung ranking pakai bobot admin
  7. ELECTRE (ml)    : hitung ranking pakai bobot PSO
  8. Normalisasi syarat tambahan (IPK, TOEFL, sertifikat)
  9. Hitung final score gabungan (assessment + syarat)
  10. Simpan semua hasil ke database
  11. Return ringkasan hasil
"""

import time
from datetime import datetime

import numpy as np
from scipy.stats import spearmanr

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


class ScoringService:

    @staticmethod
    def generate_ranking(position_id: int, triggered_by: int) -> dict:
        """
        Entry point utama — dipanggil saat admin klik "Generate Ranking".

        Parameters:
            position_id  : ID posisi yang akan diproses
            triggered_by : ID admin yang menjalankan proses

        Returns:
            dict berisi hasil ranking dan metadata proses
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
        """Proses internal scoring lengkap."""

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

        # Simpan criteria_scores ke DB
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
                )
                db.session.add(score)
        db.session.flush()

        # ── STEP 4: EWM — hitung bobot objektif ──────────────────────────
        ewm_result = EWMService.compute_weights(fuzzy_matrix)
        ewm_weights = ewm_result['weights']

        log.ewm_entropy_values = ewm_result['entropy']
        log.ewm_weights        = {pc_list[j].criteria.code: ewm_weights[j]
                                   for j in range(n_criteria)}

        # ── STEP 5: Bobot manual admin (normalisasi) ──────────────────────
        raw_manual = [float(pc.weight_manual) for pc in pc_list]
        total_manual = sum(raw_manual) or 1.0
        manual_weights_norm = [w / total_manual for w in raw_manual]

        # ── STEP 6: PSO — optimasi bobot ─────────────────────────────────
        pso = PSOService(n_particles=30, max_iterations=100)
        pso_result = pso.optimize_weights(
            ewm_weights=ewm_weights,
            manual_weights=manual_weights_norm,
            decision_matrix=fuzzy_matrix,
            alpha=0.6,  # 60% EWM + 40% manual
        )
        ml_weights = pso_result['optimal_weights']

        log.pso_parameters   = {'n_particles': 30, 'max_iter': 100, 'w': 0.7, 'c1': 1.5, 'c2': 1.5}
        log.pso_best_weights = {pc_list[j].criteria.code: ml_weights[j] for j in range(n_criteria)}
        log.pso_best_fitness = pso_result['best_fitness']
        log.pso_iterations_used = pso_result['iterations_used']
        log.pso_converged    = pso_result['converged']

        # Simpan ml_weight_results ke DB
        generated_at = datetime.utcnow()
        MlWeightResult.query.filter_by(position_id=position_id).delete()
        for j, pc in enumerate(pc_list):
            mwr = MlWeightResult(
                position_id=position_id,
                position_criteria_id=pc.id,
                weight_manual=manual_weights_norm[j],
                weight_ewm=ewm_weights[j],
                weight_final=ml_weights[j],
                weight_difference=abs(ml_weights[j] - manual_weights_norm[j]),
                generated_at=generated_at,
                pso_iterations=pso_result['iterations_used'],
                pso_best_fitness=pso_result['best_fitness'],
            )
            db.session.add(mwr)
        db.session.flush()

        # ── STEP 7: ELECTRE — hitung ranking dua versi ───────────────────
        criteria_types = [pc.criteria_type for pc in pc_list]

        # Versi manual (bobot admin)
        electre_manual = ELECTREService.compute(
            decision_matrix=fuzzy_matrix,
            weights=manual_weights_norm,
            criteria_types=criteria_types,
        )

        # Versi ML (bobot PSO)
        electre_ml = ELECTREService.compute(
            decision_matrix=fuzzy_matrix,
            weights=ml_weights,
            criteria_types=criteria_types,
        )

        # ── STEP 8: Normalisasi syarat tambahan ──────────────────────────
        # IPK, TOEFL, sertifikat → normalized 0-100
        req_scores = ScoringService._compute_requirement_scores(
            applications=applications,
            recruitment=recruitment,
        )

        # Bobot komponen penilaian
        assessment_weight = recruitment.get_assessment_weight() / 100  # jadi 0-1
        req_weight        = 1.0 - assessment_weight

        # ── STEP 9: Hitung final score & simpan ──────────────────────────
        scores_manual = []
        scores_ml     = []

        for i, app in enumerate(applications):
            # ELECTRE net score sebagai assessment score (0-1 range → scale ke 0-100)
            # Normalisasi net score ELECTRE ke 0-100
            all_net_manual = electre_manual['net_score']
            all_net_ml     = electre_ml['net_score']

            # Min-max normalisasi net score ke 0-100
            assess_manual = ScoringService._minmax_scale(
                electre_manual['net_score'][i], all_net_manual
            ) * 100
            assess_ml = ScoringService._minmax_scale(
                electre_ml['net_score'][i], all_net_ml
            ) * 100

            req_score = req_scores.get(app.id, 0.0)

            final_manual = (assess_manual * assessment_weight) + (req_score * req_weight)
            final_ml     = (assess_ml * assessment_weight)     + (req_score * req_weight)

            scores_manual.append(final_manual)
            scores_ml.append(final_ml)

            # Simpan ke scoring_results
            ScoringResult.query.filter_by(application_id=app.id).delete()
            sr = ScoringResult(
                application_id=app.id,
                assessment_score_manual=round(assess_manual, 4),
                assessment_score_ml=round(assess_ml, 4),
                requirements_score=round(req_score, 4),
                electre_concordance_manual=electre_manual['net_concordance'][i],
                electre_discordance_manual=electre_manual['net_discordance'][i],
                electre_net_manual=electre_manual['net_score'][i],
                electre_concordance_ml=electre_ml['net_concordance'][i],
                electre_discordance_ml=electre_ml['net_discordance'][i],
                electre_net_ml=electre_ml['net_score'][i],
                final_score_manual=round(final_manual, 4),
                final_score_ml=round(final_ml, 4),
                generated_at=generated_at,
                generated_by=triggered_by,
            )
            db.session.add(sr)

            # Update status aplikasi
            app.status = 'scored'

        db.session.flush()

        # ── STEP 10: Ranking ──────────────────────────────────────────────
        # Urutkan berdasarkan final_score (bukan hanya ELECTRE)
        rank_manual_order = sorted(range(n_candidates), key=lambda i: scores_manual[i], reverse=True)
        rank_ml_order     = sorted(range(n_candidates), key=lambda i: scores_ml[i], reverse=True)

        rank_manual = [0] * n_candidates
        rank_ml     = [0] * n_candidates
        for rank, idx in enumerate(rank_manual_order):
            rank_manual[idx] = rank + 1
        for rank, idx in enumerate(rank_ml_order):
            rank_ml[idx] = rank + 1

        quota = position.quota
        RankingResult.query.filter_by(position_id=position_id).delete()

        for i, app in enumerate(applications):
            rr = RankingResult(
                position_id=position_id,
                application_id=app.id,
                rank_manual=rank_manual[i],
                final_score_manual=round(scores_manual[i], 4),
                rank_ml=rank_ml[i],
                final_score_ml=round(scores_ml[i], 4),
                is_recommended=(rank_ml[i] <= quota),  # default pakai ML
                final_status='pending',
                generated_at=generated_at,
            )
            db.session.add(rr)

        # ── STEP 11: Spearman Correlation (perbandingan ranking) ──────────
        if n_candidates >= 3:
            corr, _ = spearmanr(rank_manual, rank_ml)
            log.spearman_correlation = round(float(corr), 4)
            log.rank_changes_count = sum(
                1 for a, b in zip(rank_manual, rank_ml) if a != b
            )

        db.session.commit()

        # Susun response
        ranking_summary = []
        for i, app in enumerate(applications):
            ranking_summary.append({
                'application_id': app.id,
                'candidate_name': app.user.name,
                'candidate_email': app.user.email,
                'rank_manual': rank_manual[i],
                'rank_ml': rank_ml[i],
                'final_score_manual': round(scores_manual[i], 4),
                'final_score_ml': round(scores_ml[i], 4),
                'is_recommended': rank_ml[i] <= quota,
            })

        # Urutkan berdasarkan rank_ml untuk tampilan
        ranking_summary.sort(key=lambda x: x['rank_ml'])

        return {
            'position_id': position_id,
            'position_title': position.title,
            'total_candidates': n_candidates,
            'quota': quota,
            'assessment_weight_pct': round(assessment_weight * 100, 2),
            'requirement_weight_pct': round(req_weight * 100, 2),
            'pso_converged': pso_result['converged'],
            'pso_iterations': pso_result['iterations_used'],
            'spearman_correlation': log.spearman_correlation,
            'ranking': ranking_summary,
            'weight_comparison': [
                {
                    'criteria_code': pc_list[j].criteria.code,
                    'criteria_name': pc_list[j].criteria.name,
                    'weight_manual': round(manual_weights_norm[j], 6),
                    'weight_ewm': round(ewm_weights[j], 6),
                    'weight_ml': round(ml_weights[j], 6),
                    'difference': round(abs(ml_weights[j] - manual_weights_norm[j]), 6),
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
