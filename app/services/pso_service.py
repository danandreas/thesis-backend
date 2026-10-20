"""
Service: PSOService (Particle Swarm Optimization)
Penyempurna bobot HASIL EWM — bobot manual pakar TIDAK ikut dalam
inisialisasi maupun fitness.

Konfigurasi (babi III & IV naskah):
  - Partikel          : 30  × 100 iterasi
  - Inertia ω         : 0.7 ; belajar c₁ = c₂ = 1.5
  - Inisialisasi      : w_EWM + gangguan Gaussian σ = 0.02 (seed 42)
  - Pengaman (box)    : w_j ∈ [0.02, 0.30] dengan proyeksi simplex
  - Fitness           : daya diskriminasi − pengaman regularisasi EWM
      var(s × 100²)/2500 dari s = X·w  ... (varians skor terbobot, diskali
      konstanta agar skala fitness mudah dibaca) dikurangi
      λ·Σ(w_j − w_j,EWM)² dengan λ = 1.0

Suku kedua mencegah degenerasi (semua bobot hampir nol kecuali satu
kriteria); suku pertama memaksa bobot membedakan kandidat dengan jelas.
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
        wmin: float = 0.02,         # batas bawah bobot (pengaman degenerasi)
        wmax: float = 0.30,         # batas atas bobot
        lam: float = 1.0,           # bobot penalti regularisasi EWM
        seed: int = 42,             # seed RNG untuk reproducibility
    ):
        self.n_particles   = n_particles
        self.max_iterations = max_iterations
        self.w             = w
        self.c1            = c1
        self.c2            = c2
        self.wmin          = wmin
        self.wmax          = wmax
        self.lam           = lam
        self.seed          = seed
        self.history       = []  # riwayat fitness terbaik per iterasi

    # ── Pengaman simplex box [wmin, wmax] dengan total 1 ─────────────
    def _box_project(self, w) -> np.ndarray:
        w = np.asarray(w, float).copy()
        if w.sum() <= 0:
            w = np.ones_like(w) / len(w)
        w = w / w.sum()
        for _ in range(200):
            bad = (w < self.wmin - 1e-12) | (w > self.wmax + 1e-12)
            if not bad.any():
                break
            w = np.clip(w, self.wmin, self.wmax)
            remaining = 1.0 - w.sum()
            free = ~bad
            if free.any() and abs(remaining) > 1e-12:
                base = w[free]
                w[free] = base + remaining * (base / base.sum())
            else:
                break
        return w

    def optimize_weights(
        self,
        ewm_weights: list[float],
        decision_matrix: list[list[float]],
    ) -> dict:
        """
        Optimasi bobot menggunakan PSO dengan inisialisasi EWM-murni.

        Parameters:
            ewm_weights    : bobot dari EWM (objektif, sum = 1)
            decision_matrix: matriks [n_kandidat × n_kriteria] nilai fuzzy

        Returns:
            dict berisi bobot optimal, fitness akhir, riwayat fitness,
            jumlah iterasi terpakai, dan status konvergensi.
        """
        n_criteria = len(ewm_weights)
        matrix = np.array(decision_matrix, dtype=float)

        if matrix.shape[0] < 2:
            return {
                'optimal_weights': list(ewm_weights),
                'best_fitness': 0.0,
                'iterations_used': 0,
                'converged': False,
                'history': [],
                'warning': 'Kandidat kurang dari 2, PSO tidak dijalankan',
            }

        rng = np.random.default_rng(self.seed)

        # ── INISIALISASI PARTIKEL: bobot EWM + Gaussian σ = 0.02 ────────
        # w0 = bobot EWM MENTAH (belum diproyeksi) — dipakai apa adanya
        # sebagai pusat inisialisasi DAN target regularisasi, sama persis
        # dengan simulasi bab IV (pso_refine(X, w_ewm)); proyeksi box hanya
        # dikenakan pada posisi partikel setelah gangguan noise ditambahkan.
        w0 = np.array(ewm_weights, dtype=float)
        positions = np.apply_along_axis(
            self._box_project, 1,
            np.tile(w0, (self.n_particles, 1))
            + rng.normal(0, 0.02, (self.n_particles, n_criteria))
        )
        velocities = rng.normal(0, 0.01, (self.n_particles, n_criteria))

        def fitness_of(w_vec) -> float:
            # fitness = varians skor terbobot (skala 0-100)/2500 − λ·‖w−w_EWM‖²
            s = matrix @ w_vec
            discrimination = (s.var() * 100 ** 2) / 2500.0
            penalty = self.lam * float(((w_vec - w0) ** 2).sum())
            return discrimination - penalty

        # Personal & global best awal
        P = positions.copy()
        Pf = np.apply_along_axis(fitness_of, 1, positions)
        g = P[Pf.argmax()].copy()
        gf = float(Pf.max())

        self.history = [gf]

        # ── ITERASI PSO ────────────────────────────────────────────────
        # Update per partikel (urut) agar konvensi identik dengan simulasi
        # bab IV; tanpa henti dini — konvergensi dibaca dari kurva fitness.
        for _ in range(self.max_iterations):
            for i in range(self.n_particles):
                r1 = rng.random()
                r2 = rng.random()
                velocities[i] = (
                    self.w * velocities[i]
                    + self.c1 * r1 * (P[i] - positions[i])
                    + self.c2 * r2 * (g - positions[i])
                )
                positions[i] = self._box_project(positions[i] + velocities[i])
                f = float(fitness_of(positions[i]))
                if f > Pf[i]:
                    Pf[i], P[i] = f, positions[i].copy()
                if f > gf:
                    gf, g = f, positions[i].copy()
            self.history.append(gf)

        iterations_used = self.max_iterations
        # Konvergen jika perbaikan fitness sesudah iterasi ke-5 sudah
        # tidak melebihi ambang 0.0001 (semua perbaikan bersifat mikro).
        converged = self._stabilized(tolerance=1e-4, since=5)

        return {
            # Semua nilai dipaksa jadi tipe Python murni (bukan np.float64 /
            # np.bool_) — Flask jsonify gagal menyerialisasi numpy scalar
            # ("Object of type bool/float64 is not JSON serializable").
            'optimal_weights': [float(v) for v in g],
            'best_fitness': float(gf),
            'iterations_used': int(iterations_used),
            'converged': bool(self._stabilized(tolerance=1e-4, since=5)),
            'history': [float(v) for v in self.history],
        }

    def _stabilized(self, tolerance: float = 1e-4, since: int = 5) -> bool:
        """True jika sejak iterasi ke-`since` tidak ada peningkatan > tolerance."""
        hist = self.history
        if len(hist) <= since + 1:
            return False
        baseline = hist[since]
        return max(hist[since:]) - baseline <= tolerance

    @staticmethod
    def parameters_dict(extra: dict | None = None) -> dict:
        """Metadata parameter PSO untuk ml_process_logs.pso_parameters."""
        params = {
            'n_particles': 30,
            'max_iter': 100,
            'w': 0.7,
            'c1': 1.5,
            'c2': 1.5,
            'init': 'ewm + gaussian sigma 0.02',
            'regularization_lambda': 1.0,
            'bounds': [0.02, 0.30],
            'seed': 42,
        }
        params.update(extra or {})
        return params