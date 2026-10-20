"""
Service: TOPSISService — Lintasan B (Fuzzy-TOPSIS, Hwang & Yoon).
Menerima input yang identik dengan Lintasan A (ELECTRE):
  - matriks keputusan: nilai fuzzy shoulder_right (satu sumber data)
  - vektor bobot     : hasil EWM-PSO (satu set bobot)
  - normalisasi vektor: r_ij = x_ij / sqrt(Σ_i x_ij²) (dipakai bersama)

Rumus (pers. 2.9–2.12 naskah):
  A⁺/A⁻  : maksimum/minimum tiap kolom matriks terbobot v = r × w
  D⁺/D⁻  : jarak Euclidean baris v_i ke A⁺/A⁻
  CL     : D⁻ / (D⁺ + D⁻)   → 1 = terbaik
  Skor   : min-max closeness ke skala 0–100
"""

import numpy as np


class TOPSISService:

    @staticmethod
    def compute(
        decision_matrix: list[list[float]],
        weights: list[float],
        criteria_types: list[str],  # 'benefit' atau 'cost'
    ) -> dict:
        matrix = np.array(decision_matrix, dtype=float)
        weights = np.array(weights, dtype=float)
        n = matrix.shape[0]

        if n < 2:
            return {
                'ideal_best': [],
                'ideal_worst': [],
                'distance_positive': [0.0] * n,
                'distance_negative': [0.0] * n,
                'closeness': [1.0] * n,
                'score': [100.0] * n,
                'ranking': [1] * n,
                'warning': 'Hanya 1 kandidat, TOPSIS tidak dapat dijalankan',
            }

        # ── Normalisasi vektor r (sama dengan ELECTRE) ─────────────────
        col_norms = np.sqrt((matrix ** 2).sum(axis=0))
        col_norms = np.where(col_norms == 0, 1e-10, col_norms)
        normalized = matrix / col_norms

        # ── Matriks terbobot v = r × w ─────────────────────────────────
        weighted = normalized * weights

        # ── Solusi ideal A⁺ / A⁻ per kolom ────────────────────────────
        ideal_best  = np.where(
            np.array(criteria_types) == 'benefit',
            weighted.max(axis=0), weighted.min(axis=0),
        )
        ideal_worst = np.where(
            np.array(criteria_types) == 'benefit',
            weighted.min(axis=0), weighted.max(axis=0),
        )

        # ── Jarak Euclidean D⁺ / D⁻ ───────────────────────────────────
        dp = np.sqrt(((weighted - ideal_best) ** 2).sum(axis=1))
        dm = np.sqrt(((weighted - ideal_worst) ** 2).sum(axis=1))

        # ── Closeness coefficient & skor & peringkat ─────────────────
        total = dp + dm
        closeness = np.where(total > 0, dm / np.where(total > 0, total, 1e-10), 0.5)

        lo, hi = closeness.min(), closeness.max()
        score = np.zeros_like(closeness) if hi == lo else (closeness - lo) / (hi - lo) * 100

        # Peringkat kompetitif (duplikat berbagi nomor, konsisten ELECTRE)
        order = np.argsort(-closeness, kind="stable")
        ranking = np.empty(n, dtype=int)
        ranking[order[0]] = 1
        for k in range(1, n):
            same = abs(closeness[order[k]] - closeness[order[k-1]]) < 1e-12
            ranking[order[k]] = ranking[order[k-1]] if same else k + 1

        return {
            'ideal_best': ideal_best.tolist(),
            'ideal_worst': ideal_worst.tolist(),
            'distance_positive': [round(float(v), 6) for v in dp],
            'distance_negative': [round(float(v), 6) for v in dm],
            'closeness': [round(float(v), 6) for v in closeness],
            'score': [round(float(v), 4) for v in score],
            'ranking': [int(r) for r in ranking],
        }