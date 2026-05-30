"""
Model: Criteria
Menyimpan master data kriteria penilaian kandidat.
Contoh: Logical Thinking, Creativity, Communication, dll.
"""
from app import db
from app.models.base import BaseModel


class Criteria(BaseModel):
    __tablename__ = 'criteria'

    id          = db.Column(db.Integer, primary_key=True, autoincrement=True)
    code        = db.Column(db.String(50), unique=True, nullable=False)
    name        = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    is_active   = db.Column(db.Boolean, nullable=False, default=True)

    # Relasi ke position_criteria
    position_criteria = db.relationship('PositionCriteria', backref='criteria', lazy='dynamic')

    def to_dict(self, exclude=None):
        return super().to_dict(exclude=exclude or [])

    def __repr__(self):
        return f"<Criteria {self.code}>"


class RequirementType(BaseModel):
    """
    Master jenis syarat tambahan di luar form assessment.
    Contoh: IPK, TOEFL, Sertifikat, Pengalaman Kerja.
    value_type menentukan cara input dan normalisasi nilai.
    """
    __tablename__ = 'requirement_types'

    id          = db.Column(db.Integer, primary_key=True, autoincrement=True)
    code        = db.Column(db.String(50), unique=True, nullable=False)
    name        = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    value_type  = db.Column(
        db.Enum('scale', 'numeric', 'count', 'boolean'),
        nullable=False, default='numeric'
    )
    min_value   = db.Column(db.Numeric(10, 4), nullable=False, default=0)
    max_value   = db.Column(db.Numeric(10, 4), nullable=False, default=100)
    unit        = db.Column(db.String(50), nullable=True)
    is_active   = db.Column(db.Boolean, nullable=False, default=True)

    def to_dict(self, exclude=None):
        data = super().to_dict(exclude=exclude or [])
        # Konversi Decimal ke float agar JSON serializable
        data['min_value'] = float(data['min_value']) if data['min_value'] else 0
        data['max_value'] = float(data['max_value']) if data['max_value'] else 100
        return data

    def __repr__(self):
        return f"<RequirementType {self.code}>"
