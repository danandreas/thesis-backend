"""
Model: Recruitment, RecruitmentPosition, RecruitmentRequirement,
       PositionCriteria, AssessmentQuestion, AssessmentOption

Hierarki:
  Recruitment
    └── RecruitmentPosition (banyak posisi per rekrutmen)
          └── PositionCriteria (kriteria per posisi + bobot + fuzzy)
                └── AssessmentQuestion (pertanyaan Likert)
                      └── AssessmentOption (pilihan jawaban + nilai)
    └── RecruitmentRequirement (syarat tambahan: IPK, TOEFL, dll)
"""
from datetime import datetime
from app import db
from app.models.base import BaseModel


class Recruitment(BaseModel):
    """
    Header batch rekrutmen.
    Bobot assessment dihitung otomatis oleh sistem:
      bobot_assessment = 100 - SUM(weight syarat tambahan aktif)
    """
    __tablename__ = 'recruitments'

    id           = db.Column(db.Integer, primary_key=True, autoincrement=True)
    code         = db.Column(db.String(50), unique=True, nullable=False)
    title        = db.Column(db.String(200), nullable=False)
    description  = db.Column(db.Text, nullable=True)
    status       = db.Column(
        db.Enum('draft', 'active', 'closed', 'finished'),
        nullable=False, default='draft'
    )
    published_at = db.Column(db.DateTime, nullable=True)
    closed_at    = db.Column(db.DateTime, nullable=True)
    created_by   = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    # Relasi
    positions    = db.relationship('RecruitmentPosition', backref='recruitment', lazy='dynamic', cascade='all, delete-orphan')
    requirements = db.relationship('RecruitmentRequirement', backref='recruitment', lazy='dynamic', cascade='all, delete-orphan')
    creator      = db.relationship('User', foreign_keys=[created_by])

    def get_assessment_weight(self):
        """
        Hitung bobot assessment otomatis.
        bobot_assessment = 100 - total bobot syarat tambahan yang aktif (weight > 0)
        """
        total_req = db.session.query(
            db.func.sum(RecruitmentRequirement.weight)
        ).filter(
            RecruitmentRequirement.recruitment_id == self.id,
            RecruitmentRequirement.weight > 0
        ).scalar() or 0
        return float(100 - total_req)

    def publish(self):
        """Publish rekrutmen: ubah status ke active."""
        self.status       = 'active'
        self.published_at = datetime.utcnow()
        for pos in self.positions:
            pos.status = 'active'
        db.session.commit()

    def close(self):
        """Tutup rekrutmen."""
        self.status   = 'closed'
        self.closed_at = datetime.utcnow()
        for pos in self.positions:
            pos.status = 'closed'
        db.session.commit()

    def to_dict(self, exclude=None):
        data = super().to_dict(exclude=exclude or [])
        data['assessment_weight'] = self.get_assessment_weight()
        data['creator_name'] = self.creator.name if self.creator else None
        return data

    def __repr__(self):
        return f"<Recruitment {self.code}>"


class RecruitmentPosition(BaseModel):
    """
    Posisi jabatan yang dibuka dalam satu rekrutmen.
    Contoh: Backend Developer, Frontend Developer.
    """
    __tablename__ = 'recruitment_positions'

    id             = db.Column(db.Integer, primary_key=True, autoincrement=True)
    recruitment_id = db.Column(db.Integer, db.ForeignKey('recruitments.id', ondelete='CASCADE'), nullable=False)
    title          = db.Column(db.String(200), nullable=False)
    description    = db.Column(db.Text, nullable=True)
    quota          = db.Column(db.Integer, nullable=False, default=1)
    status         = db.Column(
        db.Enum('draft', 'active', 'closed'),
        nullable=False, default='draft'
    )

    # Relasi
    criteria_setup  = db.relationship('PositionCriteria', backref='position', lazy='dynamic', cascade='all, delete-orphan')
    applications    = db.relationship('CandidateApplication', backref='position', lazy='dynamic')

    def to_dict(self, exclude=None):
        data = super().to_dict(exclude=exclude or [])
        data['criteria_count'] = self.criteria_setup.count()
        data['applicant_count'] = self.applications.count()
        return data

    def __repr__(self):
        return f"<RecruitmentPosition {self.title}>"


class RecruitmentRequirement(BaseModel):
    """
    Syarat tambahan yang diaktifkan per rekrutmen.
    Berlaku sama untuk semua posisi dalam rekrutmen.
    weight = 0 berarti tidak aktif, tidak muncul di form kandidat.
    """
    __tablename__ = 'recruitment_requirements'

    id                  = db.Column(db.Integer, primary_key=True, autoincrement=True)
    recruitment_id      = db.Column(db.Integer, db.ForeignKey('recruitments.id', ondelete='CASCADE'), nullable=False)
    requirement_type_id = db.Column(db.Integer, db.ForeignKey('requirement_types.id'), nullable=False)
    weight              = db.Column(db.Numeric(5, 2), nullable=False, default=0)
    minimum_value       = db.Column(db.Numeric(10, 4), nullable=True)
    is_mandatory        = db.Column(db.Boolean, nullable=False, default=False)
    display_order       = db.Column(db.Integer, nullable=False, default=0)

    # Relasi
    requirement_type = db.relationship('RequirementType')

    def to_dict(self, exclude=None):
        data = super().to_dict(exclude=exclude or [])
        data['weight'] = float(data['weight']) if data['weight'] else 0
        data['minimum_value'] = float(data['minimum_value']) if data['minimum_value'] else None
        if self.requirement_type:
            data['requirement_type'] = self.requirement_type.to_dict()
        return data

    def __repr__(self):
        return f"<RecruitmentRequirement {self.recruitment_id}-{self.requirement_type_id}>"


class PositionCriteria(BaseModel):
    """
    Setup kriteria penilaian per posisi.

    weight_manual : bobot kepentingan dari admin (1-100, bebas)
                    Ini adalah input SUBJEKTIF admin yang akan
                    dinormalisasi dan dibandingkan dengan hasil ML.

    fuzzy_low/mid/high : parameter fungsi keanggotaan fuzzy segitiga.
                    Untuk skala Likert 1-5: low=1, mid=3, high=5.
                    Admin bisa ubah jika skala jawaban berbeda.

    criteria_type : 'benefit' = makin tinggi makin baik (default)
                    'cost'    = makin rendah makin baik
    """
    __tablename__ = 'position_criteria'

    id                   = db.Column(db.Integer, primary_key=True, autoincrement=True)
    position_id          = db.Column(db.Integer, db.ForeignKey('recruitment_positions.id', ondelete='CASCADE'), nullable=False)
    criteria_id          = db.Column(db.Integer, db.ForeignKey('criteria.id'), nullable=False)
    weight_manual        = db.Column(db.Numeric(5, 2), nullable=False, default=50)
    fuzzy_low            = db.Column(db.Numeric(5, 2), nullable=False, default=1)
    fuzzy_mid            = db.Column(db.Numeric(5, 2), nullable=False, default=3)
    fuzzy_high           = db.Column(db.Numeric(5, 2), nullable=False, default=5)
    criteria_type        = db.Column(db.Enum('benefit', 'cost'), nullable=False, default='benefit')
    display_order        = db.Column(db.Integer, nullable=False, default=0)

    # Relasi
    questions = db.relationship('AssessmentQuestion', backref='position_criteria', lazy='dynamic', cascade='all, delete-orphan')

    def to_dict(self, exclude=None):
        data = super().to_dict(exclude=exclude or [])
        for f in ['weight_manual', 'fuzzy_low', 'fuzzy_mid', 'fuzzy_high']:
            data[f] = float(data[f]) if data[f] is not None else 0
        if self.criteria:
            data['criteria'] = self.criteria.to_dict()
        data['question_count'] = self.questions.count()
        return data

    def __repr__(self):
        return f"<PositionCriteria pos={self.position_id} crit={self.criteria_id}>"


class AssessmentQuestion(BaseModel):
    """
    Pertanyaan Likert tersamar per kriteria per posisi.
    Kandidat tidak tahu pertanyaan ini mengukur kriteria apa.
    Admin yang membuat pertanyaan saat setup posisi.
    """
    __tablename__ = 'assessment_questions'

    id                   = db.Column(db.Integer, primary_key=True, autoincrement=True)
    position_criteria_id = db.Column(db.Integer, db.ForeignKey('position_criteria.id', ondelete='CASCADE'), nullable=False)
    question_text        = db.Column(db.Text, nullable=False)
    display_order        = db.Column(db.Integer, nullable=False, default=0)
    is_active            = db.Column(db.Boolean, nullable=False, default=True)

    # Relasi
    options = db.relationship('AssessmentOption', backref='question', lazy='dynamic', cascade='all, delete-orphan')

    def to_dict(self, exclude=None):
        data = super().to_dict(exclude=exclude or [])
        data['options'] = [o.to_dict() for o in self.options.order_by(AssessmentOption.display_order)]
        return data

    def __repr__(self):
        return f"<AssessmentQuestion {self.id}>"


class AssessmentOption(BaseModel):
    """
    Pilihan jawaban per pertanyaan.
    option_value adalah nilai TERSEMBUNYI (tidak ditampilkan ke kandidat).
    Kandidat hanya melihat option_text.
    """
    __tablename__ = 'assessment_options'

    id            = db.Column(db.Integer, primary_key=True, autoincrement=True)
    question_id   = db.Column(db.Integer, db.ForeignKey('assessment_questions.id', ondelete='CASCADE'), nullable=False)
    option_text   = db.Column(db.Text, nullable=False)
    option_value  = db.Column(db.Numeric(5, 2), nullable=False, default=1)
    display_order = db.Column(db.Integer, nullable=False, default=0)

    def to_dict(self, exclude=None):
        data = super().to_dict(exclude=exclude or [])
        # PENTING: option_value tidak dikirim ke kandidat
        # Hanya dikirim ke admin
        data['option_value'] = float(data['option_value']) if data['option_value'] else 1
        return data

    def to_candidate_dict(self):
        """Versi dict tanpa option_value untuk ditampilkan ke kandidat."""
        return {
            'id': self.id,
            'option_text': self.option_text,
            'display_order': self.display_order,
        }

    def __repr__(self):
        return f"<AssessmentOption {self.id} val={self.option_value}>"
