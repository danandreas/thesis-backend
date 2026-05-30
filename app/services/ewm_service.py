"""
Service: EWMService (Entropy Weight Method)
Metode untuk menghitung bobot kriteria secara OBJEKTIF berdasarkan
distribusi data aktual kandidat.

Filosofi EWM:
  - Kriteria yang nilainya BERVARIASI antar kandidat → informatif → bobot TINGGI
  - Kriteria yang nilainya SERAGAM antar kandidat → kurang informatif → bobot RENDAH

  Contoh intuitif:
    Jika semua kandidat Backend Developer mendapat skor Logical Thinking
    yang hampir sama (misal semua 4-5), kriteria ini tidak bisa membedakan
    siapa yang terbaik → EWM akan beri bobot rendah.

    Sebaliknya jika skor Technical Skill sangat bervariasi (1-5),
    kriteria ini sangat informatif untuk membedakan kandidat → bobot tinggi.

Referensi: Shannon Entropy untuk pembobotan MCDM.
"""

import numpy as np


class EWMService:

    @staticmethod
    def compute_weights(decision_matrix: list[list[float]]) -> dict:
        """
        Hitung bobot kriteria menggunakan Entropy Weight Method.

        Parameters:
            decision_matrix: matriks [n_kandidat × n_kriteria]
                             Setiap baris = satu kandidat
                             Setiap kolom = satu kriteria
                             Nilai sudah dalam bentuk fuzzy (0-1)

                             Contoh (3 kandidat, 3 kriteria):
                             [[0.8, 0.6, 0.9],  ← kandidat A
                              [0.5, 0.7, 0.4],  ← kandidat B
                              [0.9, 0.6, 0.7]]  ← kandidat C

        Returns:
            dict berisi:
              'weights'    : list bobot per kriteria (sum = 1.0)
              'entropy'    : list nilai entropy per kriteria
              'diversity'  : list nilai diversitas per kriteria
              'normalized' : matriks yang sudah dinormalisasi

        Langkah-langkah EWM:
          1. Normalisasi matriks (proporsi tiap nilai dalam kolomnya)
          2. Hitung entropy tiap kriteria
          3. Hitung diversitas = 1 - entropy
          4. Normalisasi diversitas → bobot akhir
        """
        matrix = np.array(decision_matrix, dtype=float)
        n_candidates, n_criteria = matrix.shape

        if n_candidates < 2:
            # Tidak cukup data, kembalikan bobot seragam
            equal_weight = 1.0 / n_criteria
            return {
                'weights': [equal_weight] * n_criteria,
                'entropy': [0.0] * n_criteria,
                'diversity': [1.0] * n_criteria,
                'normalized': matrix.tolist(),
                'warning': 'Kandidat kurang dari 2, bobot seragam digunakan'
            }

        # ── STEP 1: Normalisasi Proporsi ─────────────────────────────────
        # Hitung proporsi: p_ij = x_ij / Σ(x_ij) untuk tiap kolom j
        # Ini mengubah nilai absolut menjadi proporsi relatif
        col_sums = matrix.sum(axis=0)
        # Hindari pembagian dengan nol
        col_sums = np.where(col_sums == 0, 1e-10, col_sums)
        normalized = matrix / col_sums  # shape: (n_candidates, n_criteria)

        # ── STEP 2: Hitung Entropy ────────────────────────────────────────
        # Rumus entropy Shannon: E_j = -(1/ln(n)) × Σ(p_ij × ln(p_ij))
        # Konstanta k = 1/ln(n) untuk memastikan 0 ≤ E_j ≤ 1
        k = 1.0 / np.log(n_candidates)

        # Hindari log(0): ganti 0 dengan nilai sangat kecil
        safe_normalized = np.where(normalized <= 0, 1e-10, normalized)
        entropy_matrix = safe_normalized * np.log(safe_normalized)
        entropy = -k * entropy_matrix.sum(axis=0)  # shape: (n_criteria,)

        # ── STEP 3: Hitung Diversitas (Degree of Divergence) ─────────────
        # d_j = 1 - E_j
        # Semakin tinggi diversitas → semakin informatif kriteria → bobot lebih besar
        diversity = 1.0 - entropy  # shape: (n_criteria,)

        # ── STEP 4: Normalisasi Diversitas → Bobot ───────────────────────
        # w_j = d_j / Σ(d_j)
        diversity_sum = diversity.sum()
        if diversity_sum == 0:
            weights = np.ones(n_criteria) / n_criteria
        else:
            weights = diversity / diversity_sum  # shape: (n_criteria,)

        return {
            'weights': weights.tolist(),       # bobot per kriteria, sum=1
            'entropy': entropy.tolist(),        # entropy per kriteria (0-1)
            'diversity': diversity.tolist(),    # diversitas per kriteria (0-1)
            'normalized': normalized.tolist(),  # matriks proporsi
        }

    @staticmethod
    def validate_matrix(decision_matrix: list[list[float]]) -> tuple[bool, str]:
        """
        Validasi decision matrix sebelum diproses EWM.
        Returns: (is_valid, error_message)
        """
        if not decision_matrix:
            return False, "Decision matrix kosong"

        n_cols = len(decision_matrix[0])
        for i, row in enumerate(decision_matrix):
            if len(row) != n_cols:
                return False, f"Baris {i} memiliki jumlah kolom berbeda"
            for j, val in enumerate(row):
                if not (0 <= val <= 1):
                    return False, f"Nilai [{i}][{j}]={val} di luar rentang 0-1"

        if len(decision_matrix) < 2:
            return True, "PERINGATAN: Kurang dari 2 kandidat, hasil EWM mungkin tidak representatif"

        return True, "OK"
