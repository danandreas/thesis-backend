"""
Model: CriteriaScore, MlWeightResult, ScoringResult, RankingResult, MlProcessLog

Ini adalah model untuk menyimpan hasil kalkulasi:
  CriteriaScore   → skor per kriteria per kandidat (setelah fuzzy)
  MlWeightResult  → bobot hasil EWM dan PSO per kriteria per posisi
  ScoringResult   → skor final per kandidat (manual vs ML)
  RankingResult   → peringkat per posisi (manual vs ML)
  MlProcessLog    → log detail setiap kali proses Generate dijalankan
"""
from app import db
from app.models.base import BaseModel


class CriteriaScore(BaseModel):
    """
    Skor per kriteria per aplikasi setelah diproses fuzzy.
    Dihitung otomatis saat tombol Generate ditekan.

    raw_score    : rata-rata nilai jawaban Likert (misal 3.67 dari skala 1-5)
    fuzzy_value  : hasil konversi ke derajat keanggotaan fuzzy (0.0000-1.0000)
    weighted_score: fuzzy_value × bobot_final (hasil kontribusi kriteria ini)
    """
    __tablename__ = 'criteria_scores'

    id                   = db.Column(db.Integer, primary_key=True, autoincrement=True)
    application_id       = db.Column(db.Integer, db.ForeignKey('candidate_applications.id', ondelete='CASCADE'), nullable=False)
    position_criteria_id = db.Column(db.Integer, db.ForeignKey('position_criteria.id'), nullable=False)
    raw_score            = db.Column(db.Numeric(10, 4), nullable=False, default=0)
    fuzzy_value          = db.Column(db.Numeric(10, 4), nullable=True)
    weighted_score       = db.Column(db.Numeric(10, 4), nullable=True)

    # Relasi
    position_criteria = db.relationship('PositionCriteria')

    def to_dict(self, exclude=None):
        data = super().to_dict(exclude=exclude or [])
        for f in ['raw_score', 'fuzzy_value', 'weighted_score']:
            data[f] = float(data[f]) if data[f] is not None else None
        return data

    def __repr__(self):
        return f"<CriteriaScore app={self.application_id} pc={self.position_criteria_id}>"


class MlWeightResult(BaseModel):
    """
    Hasil optimasi bobot dari proses ML (EWM + PSO) per kriteria per posisi.
    Ini adalah INTI NOVELTY thesis — menyimpan 3 versi bobot:

    weight_manual  : bobot subjektif admin (dinormalisasi, 0-1)
    weight_ewm     : bobot objektif dari Entropy Weight Method
    weight_final   : bobot optimal hasil PSO (kombinasi manual + EWM)
    weight_difference: selisih manual vs final (bahan analisis thesis)
    """
    __tablename__ = 'ml_weight_results'

    id                   = db.Column(db.Integer, primary_key=True, autoincrement=True)
    position_id          = db.Column(db.Integer, db.ForeignKey('recruitment_positions.id'), nullable=False)
    position_criteria_id = db.Column(db.Integer, db.ForeignKey('position_criteria.id'), nullable=False)
    weight_manual        = db.Column(db.Numeric(10, 6), nullable=False, default=0)
    weight_ewm           = db.Column(db.Numeric(10, 6), nullable=True)
    weight_final         = db.Column(db.Numeric(10, 6), nullable=True)
    weight_difference    = db.Column(db.Numeric(10, 6), nullable=True)
    generated_at         = db.Column(db.DateTime, nullable=False)
    pso_iterations       = db.Column(db.Integer, nullable=True)
    pso_best_fitness     = db.Column(db.Numeric(10, 6), nullable=True)

    # Relasi
    position_criteria = db.relationship('PositionCriteria')

    def to_dict(self, exclude=None):
        data = super().to_dict(exclude=exclude or [])
        for f in ['weight_manual', 'weight_ewm', 'weight_final', 'weight_difference', 'pso_best_fitness']:
            data[f] = float(data[f]) if data[f] is not None else None
        if self.position_criteria and self.position_criteria.criteria:
            data['criteria_name'] = self.position_criteria.criteria.name
            data['criteria_code'] = self.position_criteria.criteria.code
        # Alias agar konsisten dengan response generate_ranking yang dipakai frontend
        data['weight_ml'] = data.get('weight_final')
        data['difference'] = data.get('weight_difference')
        return data

    def __repr__(self):
        return f"<MlWeightResult pos={self.position_id} pc={self.position_criteria_id}>"


class ScoringResult(BaseModel):
    """
    Hasil kalkulasi skor akhir per aplikasi.
    Menyimpan DUA versi skor untuk mendukung Human-in-the-Loop:
      _manual : menggunakan bobot admin
      _ml     : menggunakan bobot hasil EWM+PSO

    Rumus skor final:
      final_score = (assessment_score × bobot_assessment%)
                  + (requirements_score × bobot_syarat%)
    """
    __tablename__ = 'scoring_results'

    id                        = db.Column(db.Integer, primary_key=True, autoincrement=True)
    application_id            = db.Column(db.Integer, db.ForeignKey('candidate_applications.id', ondelete='CASCADE'), nullable=False, unique=True)

    # Skor assessment (dari form Likert) — dua versi
    assessment_score_manual   = db.Column(db.Numeric(10, 4), nullable=True)
    assessment_score_ml       = db.Column(db.Numeric(10, 4), nullable=True)

    # Skor syarat tambahan (IPK, TOEFL, sertifikat — sama untuk keduanya)
    requirements_score        = db.Column(db.Numeric(10, 4), nullable=True)

    # Hasil ELECTRE — dua versi
    electre_concordance_manual  = db.Column(db.Numeric(10, 4), nullable=True)
    electre_discordance_manual  = db.Column(db.Numeric(10, 4), nullable=True)
    electre_net_manual          = db.Column(db.Numeric(10, 4), nullable=True)
    electre_concordance_ml      = db.Column(db.Numeric(10, 4), nullable=True)
    electre_discordance_ml      = db.Column(db.Numeric(10, 4), nullable=True)
    electre_net_ml              = db.Column(db.Numeric(10, 4), nullable=True)

    # Skor final gabungan — dua versi
    final_score_manual        = db.Column(db.Numeric(10, 4), nullable=True)
    final_score_ml            = db.Column(db.Numeric(10, 4), nullable=True)

    # Metadata
    generated_at              = db.Column(db.DateTime, nullable=True)
    generated_by              = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    # Relasi
    application = db.relationship('CandidateApplication', backref=db.backref('scoring_result', uselist=False))

    def to_dict(self, exclude=None):
        data = super().to_dict(exclude=exclude or [])
        numeric_fields = [
            'assessment_score_manual', 'assessment_score_ml', 'requirements_score',
            'electre_concordance_manual', 'electre_discordance_manual', 'electre_net_manual',
            'electre_concordance_ml', 'electre_discordance_ml', 'electre_net_ml',
            'final_score_manual', 'final_score_ml'
        ]
        for f in numeric_fields:
            data[f] = float(data[f]) if data[f] is not None else None
        return data

    def __repr__(self):
        return f"<ScoringResult app={self.application_id}>"


class RankingResult(BaseModel):
    """
    Peringkat akhir kandidat per posisi.
    Menyimpan DUA versi ranking untuk Human-in-the-Loop:
      rank_manual : berdasarkan bobot admin
      rank_ml     : berdasarkan bobot ML

    Admin memilih versi mana yang dipakai (admin_choice)
    lalu menetapkan final_rank dan final_status.
    """
    __tablename__ = 'ranking_results'

    id                = db.Column(db.Integer, primary_key=True, autoincrement=True)
    position_id       = db.Column(db.Integer, db.ForeignKey('recruitment_positions.id'), nullable=False)
    application_id    = db.Column(db.Integer, db.ForeignKey('candidate_applications.id'), nullable=False)

    rank_manual       = db.Column(db.Integer, nullable=True)
    final_score_manual= db.Column(db.Numeric(10, 4), nullable=True)
    rank_ml           = db.Column(db.Integer, nullable=True)
    final_score_ml    = db.Column(db.Numeric(10, 4), nullable=True)

    # Keputusan admin
    admin_choice      = db.Column(db.Enum('manual', 'ml'), nullable=True)
    final_rank        = db.Column(db.Integer, nullable=True)
    final_score       = db.Column(db.Numeric(10, 4), nullable=True)
    is_recommended    = db.Column(db.Boolean, nullable=False, default=False)
    final_status      = db.Column(
        db.Enum('pending', 'accepted', 'rejected'),
        nullable=False, default='pending'
    )
    generated_at      = db.Column(db.DateTime, nullable=True)

    # Relasi
    application = db.relationship('CandidateApplication', backref='ranking_result')

    def to_dict(self, exclude=None):
        data = super().to_dict(exclude=exclude or [])
        for f in ['final_score_manual', 'final_score_ml', 'final_score']:
            data[f] = float(data[f]) if data[f] is not None else None
        if self.application and self.application.user:
            data['candidate_name'] = self.application.user.name
            data['candidate_email'] = self.application.user.email
        return data

    def __repr__(self):
        return f"<RankingResult pos={self.position_id} app={self.application_id}>"


class MlProcessLog(BaseModel):
    """
    Log detail setiap kali proses Generate dijalankan.
    Menyimpan parameter, metrik, dan hasil EWM+PSO.
    Penting untuk bab analisis dan pembahasan thesis.
    """
    __tablename__ = 'ml_process_logs'

    id                   = db.Column(db.Integer, primary_key=True, autoincrement=True)
    position_id          = db.Column(db.Integer, db.ForeignKey('recruitment_positions.id'), nullable=False)
    triggered_by         = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    # EWM
    ewm_entropy_values   = db.Column(db.JSON, nullable=True)
    ewm_weights          = db.Column(db.JSON, nullable=True)

    # PSO
    pso_parameters       = db.Column(db.JSON, nullable=True)
    pso_best_weights     = db.Column(db.JSON, nullable=True)
    pso_best_fitness     = db.Column(db.Numeric(10, 6), nullable=True)
    pso_iterations_used  = db.Column(db.Integer, nullable=True)
    pso_converged        = db.Column(db.Boolean, nullable=True)

    # Metrik perbandingan
    spearman_correlation = db.Column(db.Numeric(6, 4), nullable=True)
    rank_changes_count   = db.Column(db.Integer, nullable=True)
    total_candidates     = db.Column(db.Integer, nullable=True)

    # Status
    status               = db.Column(
        db.Enum('processing', 'completed', 'failed'),
        nullable=False, default='processing'
    )
    error_message        = db.Column(db.Text, nullable=True)
    process_duration_ms  = db.Column(db.Integer, nullable=True)
    processed_at         = db.Column(db.DateTime, nullable=True)

    def to_dict(self, exclude=None):
        data = super().to_dict(exclude=exclude or [])
        for f in ['pso_best_fitness', 'spearman_correlation']:
            data[f] = float(data[f]) if data[f] is not None else None
        return data

    def __repr__(self):
        return f"<MlProcessLog pos={self.position_id} status={self.status}>"
