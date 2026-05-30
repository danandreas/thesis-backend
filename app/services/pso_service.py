"""
Service: PSOService (Particle Swarm Optimization)
Algoritma optimasi terinspirasi dari perilaku kawanan burung/ikan.
Digunakan untuk mengoptimasi bobot kriteria dengan mempertimbangkan
KEDUA sumber: bobot admin (subjektif) dan bobot EWM (objektif).

Analogi PSO:
  Bayangkan kawanan burung mencari sumber makanan.
  Setiap burung (partikel) = satu kandidat solusi (vektor bobot)
  Setiap burung bergerak berdasarkan:
    1. Ingatan terbaik dirinya sendiri (pbest)
    2. Posisi terbaik di seluruh kawanan (gbest)
  Lama-kelamaan kawanan berkumpul di titik optimal.

Dalam konteks thesis:
  Setiap partikel = satu set bobot kriteria [w1, w2, ..., w10]
  Fungsi fitness = seberapa baik bobot ini memisahkan kandidat
                   (kandidat dengan skor tinggi vs rendah harus jelas berbeda)
"""

import numpy as np


class PSOService:

    def __init__(
        self,
        n_particles: int = 30,      # jumlah partikel dalam kawanan
        max_iterations: int = 100,  # maksimum iterasi
        w: float = 0.7,             # inertia weight (momentum partikel)
        c1: float = 1.5,            # cognitive coefficient (tarik ke pbest)
        c2: float = 1.5,            # social coefficient (tarik ke gbest)
        tolerance: float = 1e-6,    # toleransi konvergensi
    ):
        """
        Inisialisasi parameter PSO.

        Parameter tuning:
          w  = 0.7-0.9 (tinggi = eksplorasi lebih luas, rendah = eksploitasi)
          c1 = c2 = 1.5-2.0 (biasanya sama agar seimbang)
          n_particles = 20-50 (lebih banyak = lebih akurat tapi lebih lambat)
        """
        self.n_particles   = n_particles
        self.max_iterations = max_iterations
        self.w             = w
        self.c1            = c1
        self.c2            = c2
        self.tolerance     = tolerance
        self.history       = []  # riwayat fitness per iterasi

    def optimize_weights(
        self,
        ewm_weights: list[float],
        manual_weights: list[float],
        decision_matrix: list[list[float]],
        alpha: float = 0.6,  # proporsi EWM dalam bobot awal (0-1)
    ) -> dict:
        """
        Optimasi bobot menggunakan PSO.

        Parameters:
            ewm_weights    : bobot dari EWM (objektif, sum=1)
            manual_weights : bobot dari admin (subjektif, sudah dinormalisasi, sum=1)
            decision_matrix: matriks [n_kandidat × n_kriteria] nilai fuzzy
            alpha          : bobot campuran EWM vs manual
                             alpha=0.6 → 60% EWM + 40% manual

        Returns:
            dict berisi bobot optimal dan metadata PSO

        Penjelasan fungsi fitness:
          Kita ingin bobot yang memaksimalkan SEPARATION antar kandidat.
          Semakin besar perbedaan skor antara kandidat terbaik dan terburuk,
          semakin baik bobot tersebut dalam membedakan kemampuan kandidat.
          Fitness = variance dari skor akhir semua kandidat (makin besar makin baik)
        """
        n_criteria = len(ewm_weights)
        matrix = np.array(decision_matrix, dtype=float)

        if matrix.shape[0] < 2:
            # Tidak cukup data untuk optimasi, kembalikan campuran EWM+manual
            combined = self._combine_weights(ewm_weights, manual_weights, alpha)
            return {
                'optimal_weights': combined,
                'best_fitness': 0.0,
                'iterations_used': 0,
                'converged': False,
                'history': [],
                'warning': 'Kandidat kurang dari 2, PSO tidak dijalankan'
            }

        # ── INISIALISASI PARTIKEL ────────────────────────────────────────
        # Setiap partikel dimulai dari bobot campuran EWM+manual
        # dengan sedikit gangguan acak (perturbation) agar beragam
        np.random.seed(42)  # untuk reproducibility (penting untuk thesis)

        base_weights = np.array(self._combine_weights(ewm_weights, manual_weights, alpha))

        # Posisi awal: perturbasi Gaussian di sekitar base_weights
        positions = np.abs(
            base_weights + np.random.normal(0, 0.05, (self.n_particles, n_criteria))
        )
        # Normalisasi agar tiap partikel sum=1
        positions = positions / positions.sum(axis=1, keepdims=True)

        # Kecepatan awal: kecil acak
        velocities = np.random.uniform(-0.01, 0.01, (self.n_particles, n_criteria))

        # Personal best: posisi awal masing-masing partikel
        pbest_positions = positions.copy()
        pbest_fitness   = np.array([self._fitness(p, matrix) for p in positions])

        # Global best: partikel dengan fitness terbaik
        gbest_idx      = np.argmax(pbest_fitness)
        gbest_position = pbest_positions[gbest_idx].copy()
        gbest_fitness  = pbest_fitness[gbest_idx]

        self.history = [gbest_fitness]
        prev_fitness = gbest_fitness
        converged    = False

        # ── ITERASI PSO ─────────────────────────────────────────────────
        for iteration in range(self.max_iterations):
            r1 = np.random.uniform(0, 1, (self.n_particles, n_criteria))
            r2 = np.random.uniform(0, 1, (self.n_particles, n_criteria))

            # Update kecepatan:
            # v(t+1) = w×v(t) + c1×r1×(pbest-x) + c2×r2×(gbest-x)
            velocities = (
                self.w * velocities
                + self.c1 * r1 * (pbest_positions - positions)
                + self.c2 * r2 * (gbest_position - positions)
            )

            # Update posisi
            positions = positions + velocities

            # Pastikan bobot non-negatif dan sum=1
            positions = np.abs(positions)
            row_sums  = positions.sum(axis=1, keepdims=True)
            row_sums  = np.where(row_sums == 0, 1e-10, row_sums)
            positions = positions / row_sums

            # Hitung fitness baru
            fitness = np.array([self._fitness(p, matrix) for p in positions])

            # Update personal best
            improved = fitness > pbest_fitness
            pbest_positions[improved] = positions[improved]
            pbest_fitness[improved]   = fitness[improved]

            # Update global best
            best_idx = np.argmax(pbest_fitness)
            if pbest_fitness[best_idx] > gbest_fitness:
                gbest_fitness  = pbest_fitness[best_idx]
                gbest_position = pbest_positions[best_idx].copy()

            self.history.append(gbest_fitness)

            # Cek konvergensi: jika perubahan sangat kecil, berhenti
            if abs(gbest_fitness - prev_fitness) < self.tolerance:
                converged = True
                break
            prev_fitness = gbest_fitness

        # Normalisasi akhir bobot optimal
        final_weights = gbest_position / gbest_position.sum()

        return {
            'optimal_weights': final_weights.tolist(),
            'best_fitness': float(gbest_fitness),
            'iterations_used': iteration + 1,
            'converged': converged,
            'history': self.history,
        }

    def _fitness(self, weights: np.ndarray, matrix: np.ndarray) -> float:
        """
        Fungsi fitness PSO.

        Mengukur seberapa baik vektor bobot ini dalam MEMBEDAKAN kandidat.
        Skor akhir tiap kandidat = Σ(nilai_kriteria × bobot_kriteria)

        Fitness = variance skor kandidat
          → Variance besar = perbedaan antar kandidat jelas = bobot informatif

        Catatan: Fungsi fitness ini bisa dimodifikasi sesuai kebutuhan,
        misalnya menggunakan Silhouette Score jika ada label kelompok.
        """
        scores = matrix @ weights  # dot product: [n_kandidat] = [n_kandidat, n_kriteria] @ [n_kriteria]
        return float(np.var(scores))  # variance skor kandidat

    def _combine_weights(
        self,
        ewm_weights: list[float],
        manual_weights: list[float],
        alpha: float
    ) -> list[float]:
        """
        Kombinasikan bobot EWM dan manual dengan rasio alpha.
        combined = alpha × EWM + (1-alpha) × manual

        alpha=0.6 → lebih percaya EWM (objektif)
        alpha=0.4 → lebih percaya admin (subjektif)
        """
        ewm    = np.array(ewm_weights, dtype=float)
        manual = np.array(manual_weights, dtype=float)
        combined = alpha * ewm + (1 - alpha) * manual
        # Normalisasi
        total = combined.sum()
        if total == 0:
            return (np.ones(len(ewm_weights)) / len(ewm_weights)).tolist()
        return (combined / total).tolist()
