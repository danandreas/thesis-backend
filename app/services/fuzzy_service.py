"""
Service: FuzzyService
Implementasi Fuzzy Logic untuk normalisasi nilai kandidat.

Metode yang digunakan: Triangular Membership Function (Fungsi Keanggotaan Segitiga)
Fungsi ini mengubah nilai mentah (raw_score) menjadi derajat keanggotaan fuzzy (0-1).

Penjelasan fungsi segitiga:
  - Jika nilai <= low  → derajat = 0 (sama sekali tidak termasuk)
  - Jika nilai == mid  → derajat = 1 (100% termasuk / sempurna)
  - Jika nilai >= high → derajat = 0 (melewati batas atas)
  - Di antara low-mid  → naik linear dari 0 ke 1
  - Di antara mid-high → turun linear dari 1 ke 0

Visualisasi:
         derajat
           1.0 |        /\\
               |       /  \\
           0.5 |      /    \\
               |     /      \\
           0.0 |____/________\\____→ nilai
                  low  mid  high
"""

import numpy as np


class FuzzyService:

    @staticmethod
    def triangular_membership(value: float, low: float, mid: float, high: float) -> float:
        """
        Hitung derajat keanggotaan fuzzy dengan fungsi segitiga.

        Parameters:
            value : nilai mentah yang akan dikonversi
            low   : batas bawah (nilai di sini → derajat 0)
            mid   : titik puncak (nilai di sini → derajat 1)
            high  : batas atas (nilai di sini → derajat 0)

        Returns:
            float: derajat keanggotaan antara 0.0 sampai 1.0

        Contoh (skala Likert 1-5, fuzzy: low=1, mid=3, high=5):
            value=1 → 0.0  (sangat rendah)
            value=2 → 0.5  (setengah antara rendah-sedang)
            value=3 → 1.0  (tepat di tengah / sempurna)
            value=4 → 0.5  (setengah antara sedang-tinggi)
            value=5 → 0.0  (melewati puncak, turun ke 0)

        Catatan: Untuk sistem rekrutmen kita, nilai tertinggi (5)
        justru dinginkan. Maka kita pakai modifikasi:
        nilai >= high → derajat = 1.0 (bukan 0)
        Ini disebut "shoulder function" di sisi kanan.
        """
        value = float(value)
        low, mid, high = float(low), float(mid), float(high)

        if mid == low == high:
            return 1.0

        if value <= low:
            return 0.0
        elif value <= mid:
            # Sisi kiri: naik linear dari low ke mid
            return (value - low) / (mid - low)
        elif value <= high:
            # Sisi kanan: turun linear dari mid ke high
            # MODIFIKASI: untuk benefit criteria, nilai >= high = 1.0
            # karena dalam rekrutmen, jawaban terbaik tetap bernilai tinggi
            return 1.0 - ((value - mid) / (high - mid)) * 0.0
            # → Artinya: setelah mid, tidak turun (dipertahankan di 1.0)
        else:
            return 1.0

    @staticmethod
    def shoulder_right_membership(value: float, low: float, mid: float, high: float) -> float:
        """
        Fungsi keanggotaan dengan 'bahu kanan' (shoulder right).
        Cocok untuk kriteria benefit di mana nilai tertinggi selalu terbaik.

        Perbedaan dengan triangular biasa:
          - triangular: nilai >= high → turun ke 0
          - shoulder  : nilai >= high → tetap di 1.0

        Visualisasi:
          derajat
            1.0 |        /‾‾‾‾‾‾‾‾‾
                |       /
            0.5 |      /
                |     /
            0.0 |____/____________→ nilai
                   low  mid  high→
        """
        value = float(value)
        low, mid, high = float(low), float(mid), float(high)

        if value <= low:
            return 0.0
        elif value <= mid:
            return (value - low) / (mid - low)
        else:
            # Setelah mid, derajat tetap 1.0
            return 1.0

    @staticmethod
    def compute_fuzzy_scores(raw_scores: list, low: float, mid: float, high: float,
                             use_shoulder: bool = True) -> list:
        """
        Hitung fuzzy membership untuk list nilai sekaligus.

        Parameters:
            raw_scores  : list nilai mentah kandidat
            low/mid/high: parameter fuzzy
            use_shoulder: True = pakai shoulder (cocok untuk benefit)

        Returns:
            list of float: derajat keanggotaan per nilai
        """
        results = []
        for val in raw_scores:
            if use_shoulder:
                fuzzy = FuzzyService.shoulder_right_membership(val, low, mid, high)
            else:
                fuzzy = FuzzyService.triangular_membership(val, low, mid, high)
            results.append(round(fuzzy, 4))
        return results

    @staticmethod
    def normalize_to_range(value: float, min_val: float, max_val: float) -> float:
        """
        Normalisasi nilai ke rentang 0-1 menggunakan min-max normalization.
        Digunakan untuk menormalisasi nilai syarat tambahan (IPK, TOEFL, dll).

        Rumus: (value - min) / (max - min)

        Contoh IPK (skala 4.00):
            IPK 2.75 → (2.75 - 0) / (4.0 - 0) = 0.6875
            IPK 3.50 → (3.50 - 0) / (4.0 - 0) = 0.8750
            IPK 4.00 → (4.00 - 0) / (4.0 - 0) = 1.0000

        Contoh TOEFL (max 677):
            Skor 500 → 500 / 677 = 0.7385
            Skor 550 → 550 / 677 = 0.8123
        """
        if max_val == min_val:
            return 1.0
        value = max(min_val, min(max_val, float(value)))  # clamp ke rentang valid
        return round((value - min_val) / (max_val - min_val), 4)

    @staticmethod
    def defuzzify_centroid(fuzzy_values: list, universe: list) -> float:
        """
        Defuzzifikasi menggunakan metode centroid (center of gravity).
        Mengubah kumpulan nilai fuzzy kembali ke nilai crisp tunggal.

        Rumus: Σ(μ(x) × x) / Σ(μ(x))
        di mana μ(x) adalah derajat keanggotaan untuk nilai x

        Biasanya digunakan jika perlu output crisp dari multiple fuzzy inputs.
        Dalam sistem ini opsional, lebih sering pakai rata-rata fuzzy langsung.
        """
        if not fuzzy_values or not universe:
            return 0.0
        numerator = sum(f * x for f, x in zip(fuzzy_values, universe))
        denominator = sum(fuzzy_values)
        if denominator == 0:
            return 0.0
        return round(numerator / denominator, 4)
