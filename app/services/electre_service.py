"""
Service: ELECTREService
Implementasi metode ELECTRE (ELimination Et Choix Traduisant la REalité)
untuk meranking kandidat berdasarkan multiple kriteria.

ELECTRE membandingkan kandidat secara BERPASANGAN menggunakan dua matriks:
  1. Concordance Matrix  → seberapa sering kandidat A lebih baik dari B
  2. Discordance Matrix  → seberapa jauh kandidat A kalah dari B di kriteria tertentu

Hasil akhir: Net Score per kandidat = concordance - discordance
Ranking diurutkan dari Net Score tertinggi.

Referensi: ELECTRE I / ELECTRE II (versi yang dipakai di sini adalah
variasi yang umum digunakan di penelitian MCDM Indonesia)
"""

import numpy as np


class ELECTREService:

    @staticmethod
    def compute(
        decision_matrix: list[list[float]],
        weights: list[float],
        criteria_types: list[str],  # 'benefit' atau 'cost'
    ) -> dict:
        """
        Hitung ELECTRE lengkap dari decision matrix.

        Parameters:
            decision_matrix : [n_kandidat × n_kriteria] nilai fuzzy (0-1)
            weights         : bobot per kriteria (sum = 1.0)
            criteria_types  : tipe per kriteria ('benefit' atau 'cost')

        Returns:
            dict berisi concordance, discordance, net score, dan ranking

        Contoh decision_matrix (3 kandidat, 3 kriteria):
            [[0.8, 0.6, 0.9],   ← kandidat A
             [0.5, 0.7, 0.4],   ← kandidat B
             [0.9, 0.6, 0.7]]   ← kandidat C
        """
        matrix = np.array(decision_matrix, dtype=float)
        weights = np.array(weights, dtype=float)
        n = matrix.shape[0]  # jumlah kandidat
        m = matrix.shape[1]  # jumlah kriteria

        if n < 2:
            return {
                'concordance_matrix': [],
                'discordance_matrix': [],
                'net_concordance': [1.0] * n,
                'net_discordance': [0.0] * n,
                'net_score': [1.0] * n,
                'score': [100.0] * n,
                'ranking': [1] * n,
                'warning': 'Hanya 1 kandidat, ELECTRE tidak dapat dijalankan'
            }

        # ── STEP 1: Normalisasi Matriks ──────────────────────────────────
        # Normalisasi vektor: r_ij = x_ij / sqrt(Σ x_ij²)
        # Memastikan semua nilai dalam skala yang sama
        col_norms = np.sqrt((matrix ** 2).sum(axis=0))
        col_norms = np.where(col_norms == 0, 1e-10, col_norms)
        normalized = matrix / col_norms

        # ── STEP 2: Matriks Terbobot ─────────────────────────────────────
        # v_ij = w_j × r_ij
        weighted = normalized * weights

        # ── STEP 3: Concordance Matrix ───────────────────────────────────
        # C(a,b) = Σ w_j dimana v_aj >= v_bj  (kandidat a tidak kalah dari b)
        # C(a,b) berkisar 0-1, makin tinggi = kandidat a makin dominan atas b
        concordance = np.zeros((n, n))
        for a in range(n):
            for b in range(n):
                if a == b:
                    continue
                for j in range(m):
                    if criteria_types[j] == 'benefit':
                        # benefit: nilai lebih tinggi lebih baik
                        if weighted[a, j] >= weighted[b, j]:
                            concordance[a, b] += weights[j]
                    else:
                        # cost: nilai lebih rendah lebih baik
                        if weighted[a, j] <= weighted[b, j]:
                            concordance[a, b] += weights[j]

        # ── STEP 4: Discordance Matrix ───────────────────────────────────
        # D(a,b) = max(|v_bj - v_aj|) dimana b lebih baik dari a  /  max(|v_bj - v_aj|) semua j
        # D(a,b) berkisar 0-1, makin tinggi = kandidat a makin kalah jauh dari b
        discordance = np.zeros((n, n))
        for a in range(n):
            for b in range(n):
                if a == b:
                    continue

                # Selisih nilai di mana b lebih baik dari a
                disadvantage = []
                all_diff     = []

                for j in range(m):
                    diff = abs(weighted[b, j] - weighted[a, j])
                    all_diff.append(diff)
                    if criteria_types[j] == 'benefit':
                        if weighted[b, j] > weighted[a, j]:
                            disadvantage.append(diff)
                    else:
                        if weighted[b, j] < weighted[a, j]:
                            disadvantage.append(diff)

                max_all  = max(all_diff) if all_diff else 1e-10
                max_disadv = max(disadvantage) if disadvantage else 0.0
                discordance[a, b] = max_disadv / max_all if max_all > 0 else 0.0

        # ── STEP 5: Net Concordance & Discordance ────────────────────────
        # Net Concordance: C_a = Σ C(a,b) - Σ C(b,a)  untuk semua b≠a
        # Kandidat dengan net concordance tinggi = sering unggul
        net_concordance = []
        net_discordance = []
        for a in range(n):
            # Sum di atas elemen numpy menghasilkan np.float64 — dibungkus
            # float() agar aman lewat jsonify & perhitungan lanjutan.
            c_sum = float(sum(concordance[a, b] for b in range(n) if b != a))
            c_opp = float(sum(concordance[b, a] for b in range(n) if b != a))
            net_concordance.append(round(c_sum - c_opp, 6))

            d_sum = float(sum(discordance[a, b] for b in range(n) if b != a))
            d_opp = float(sum(discordance[b, a] for b in range(n) if b != a))
            net_discordance.append(round(d_sum - d_opp, 6))

        # ── STEP 6: Net Score & Ranking ──────────────────────────────────
        # Net Score = Net Concordance - Net Discordance
        # Makin tinggi → kandidat makin direkomendasikan
        net_score = [
            round(nc - nd, 6)
            for nc, nd in zip(net_concordance, net_discordance)
        ]

        # Ranking: 1 = terbaik (net_score tertinggi)
        sorted_idx = np.argsort(net_score)[::-1]
        ranking    = [0] * n
        for rank, idx in enumerate(sorted_idx):
            ranking[idx] = rank + 1

        # ── STEP 7: Skor 0–100 (dikonsumsi ScoringService) ───────────────
        # Skor = min-max net score ke skala 100 — identik dengan kolom
        # "Skor (0–100)" tabel peringkat Lintasan A pada naskah (Tabel 4.9).
        ns = np.array(net_score, dtype=float)
        ns_lo, ns_hi = ns.min(), ns.max()
        if ns_hi > ns_lo:
            score = (ns - ns_lo) / (ns_hi - ns_lo) * 100.0
        else:
            score = np.ones(n) * 100.0

        return {
            'concordance_matrix': concordance.tolist(),
            'discordance_matrix': discordance.tolist(),
            'net_concordance': net_concordance,
            'net_discordance': net_discordance,
            'net_score': net_score,
            'score': [round(float(v), 2) for v in score],
            'ranking': ranking,
        }
