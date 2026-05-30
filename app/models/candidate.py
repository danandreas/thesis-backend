"""
Model: CandidateProfile, CandidateEducation,
       CandidateApplication, AssessmentAnswer, CandidateRequirement

Hierarki untuk kandidat:
  User (role=candidate)
    └── CandidateProfile (data profil tambahan)
    └── CandidateEducation (riwayat pendidikan + IPK)
    └── CandidateApplication (pendaftaran ke posisi)
          └── AssessmentAnswer (jawaban pertanyaan Likert)
          └── CandidateRequirement (nilai IPK, TOEFL, sertifikat)
"""
from app import db
from app.models.base import BaseModel


class CandidateProfile(BaseModel):
    """
    Data profil tambahan khusus kandidat.
    Extend dari tabel users yang sudah ada.
    """
    __tablename__ = 'candidate_profiles'

    id           = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id      = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True)
    birth_date   = db.Column(db.Date, nullable=True)
    gender       = db.Column(db.Enum('male', 'female', 'other'), nullable=True)
    linkedin_url = db.Column(db.String(255), nullable=True)
    resume_url   = db.Column(db.String(255), nullable=True)

    # Relasi
    user = db.relationship('User', backref=db.backref('candidate_profile', uselist=False))

    def to_dict(self, exclude=None):
        data = super().to_dict(exclude=exclude or [])
        if self.user:
            data['user'] = {
                'id': self.user.id,
                'name': self.user.name,
                'email': self.user.email,
                'phone': self.user.phone,
            }
        return data

    def __repr__(self):
        return f"<CandidateProfile user={self.user_id}>"


class CandidateEducation(BaseModel):
    """
    Riwayat pendidikan kandidat.
    is_latest=True menandai pendidikan terakhir
    yang IPK-nya digunakan untuk penilaian.
    """
    __tablename__ = 'candidate_educations'

    id              = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id         = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    degree          = db.Column(db.Enum('SMA/SMK', 'D1', 'D2', 'D3', 'S1', 'S2', 'S3'), nullable=False)
    institution     = db.Column(db.String(200), nullable=False)
    major           = db.Column(db.String(200), nullable=True)
    gpa             = db.Column(db.Numeric(5, 2), nullable=True)
    gpa_scale       = db.Column(db.Numeric(5, 2), nullable=False, default=4.00)
    graduation_year = db.Column(db.Integer, nullable=True)
    is_latest       = db.Column(db.Boolean, nullable=False, default=False)

    user = db.relationship('User', backref='educations')

    def to_dict(self, exclude=None):
        data = super().to_dict(exclude=exclude or [])
        data['gpa'] = float(data['gpa']) if data['gpa'] else None
        data['gpa_scale'] = float(data['gpa_scale']) if data['gpa_scale'] else 4.0
        return data

    def __repr__(self):
        return f"<CandidateEducation {self.degree} {self.institution}>"


class CandidateApplication(BaseModel):
    """
    Pendaftaran kandidat ke posisi tertentu.
    Satu kandidat hanya boleh mendaftar satu kali per posisi.

    Alur status:
      registered → in_progress → submitted → verified → scored → accepted/rejected
    """
    __tablename__ = 'candidate_applications'

    id           = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id      = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    position_id  = db.Column(db.Integer, db.ForeignKey('recruitment_positions.id'), nullable=False)
    status       = db.Column(
        db.Enum('registered', 'in_progress', 'submitted', 'verified', 'scored', 'accepted', 'rejected'),
        nullable=False, default='registered'
    )
    submitted_at = db.Column(db.DateTime, nullable=True)
    verified_at  = db.Column(db.DateTime, nullable=True)
    verified_by  = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    notes        = db.Column(db.Text, nullable=True)

    # Relasi
    user         = db.relationship('User', foreign_keys=[user_id], backref='applications')
    verifier     = db.relationship('User', foreign_keys=[verified_by])
    answers      = db.relationship('AssessmentAnswer', backref='application', lazy='dynamic', cascade='all, delete-orphan')
    requirements = db.relationship('CandidateRequirement', backref='application', lazy='dynamic', cascade='all, delete-orphan')

    def to_dict(self, exclude=None):
        data = super().to_dict(exclude=exclude or [])
        if self.user:
            data['candidate_name'] = self.user.name
            data['candidate_email'] = self.user.email
        if self.position:
            data['position_title'] = self.position.title
        data['answer_count'] = self.answers.count()
        return data

    def __repr__(self):
        return f"<CandidateApplication user={self.user_id} pos={self.position_id}>"


class AssessmentAnswer(BaseModel):
    """
    Jawaban kandidat untuk setiap pertanyaan Likert.
    answer_value disalin dari option_value saat kandidat memilih
    agar tidak berubah jika admin edit option di kemudian hari.
    """
    __tablename__ = 'assessment_answers'

    id             = db.Column(db.Integer, primary_key=True, autoincrement=True)
    application_id = db.Column(db.Integer, db.ForeignKey('candidate_applications.id', ondelete='CASCADE'), nullable=False)
    question_id    = db.Column(db.Integer, db.ForeignKey('assessment_questions.id'), nullable=False)
    option_id      = db.Column(db.Integer, db.ForeignKey('assessment_options.id'), nullable=False)
    # Nilai disalin dari option saat submit agar immutable
    answer_value   = db.Column(db.Numeric(5, 2), nullable=False)

    # Relasi
    question = db.relationship('AssessmentQuestion')
    option   = db.relationship('AssessmentOption')

    def to_dict(self, exclude=None):
        data = super().to_dict(exclude=exclude or [])
        data['answer_value'] = float(data['answer_value']) if data['answer_value'] else 0
        return data

    def __repr__(self):
        return f"<AssessmentAnswer app={self.application_id} q={self.question_id}>"


class CandidateRequirement(BaseModel):
    """
    Nilai syarat tambahan yang diisi kandidat (IPK, TOEFL, sertifikat, dll).
    Admin bisa mengedit raw_value setelah verifikasi dokumen fisik.
    normalized_score dihitung otomatis saat Generate ditekan.
    """
    __tablename__ = 'candidate_requirements'

    id                         = db.Column(db.Integer, primary_key=True, autoincrement=True)
    application_id             = db.Column(db.Integer, db.ForeignKey('candidate_applications.id', ondelete='CASCADE'), nullable=False)
    recruitment_requirement_id = db.Column(db.Integer, db.ForeignKey('recruitment_requirements.id'), nullable=False)
    raw_value                  = db.Column(db.Numeric(10, 4), nullable=False, default=0)
    normalized_score           = db.Column(db.Numeric(10, 4), nullable=True)
    proof_file_url             = db.Column(db.String(255), nullable=True)

    # Relasi
    recruitment_requirement = db.relationship('RecruitmentRequirement')

    def to_dict(self, exclude=None):
        data = super().to_dict(exclude=exclude or [])
        data['raw_value'] = float(data['raw_value']) if data['raw_value'] else 0
        data['normalized_score'] = float(data['normalized_score']) if data['normalized_score'] else None
        if self.recruitment_requirement:
            data['requirement_info'] = self.recruitment_requirement.to_dict()
        return data

    def __repr__(self):
        return f"<CandidateRequirement app={self.application_id}>"
