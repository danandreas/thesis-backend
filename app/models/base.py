from datetime import datetime
from app import db


class BaseModel(db.Model):
    """
    Base model dengan Eloquent-like methods.
    Semua model inherit dari sini.
    """
    __abstract__ = True

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # -------------------------
    # Eloquent-like query methods
    # -------------------------

    @classmethod
    def all(cls):
        """Get all records."""
        return cls.query.all()

    @classmethod
    def find(cls, id):
        """Find by primary key."""
        return cls.query.get(id)

    @classmethod
    def find_or_fail(cls, id):
        """Find by primary key or raise 404."""
        return cls.query.get_or_404(id)

    @classmethod
    def where(cls, **kwargs):
        """Filter by keyword arguments (exact match)."""
        return cls.query.filter_by(**kwargs)

    @classmethod
    def first_where(cls, **kwargs):
        """Get first record matching kwargs."""
        return cls.query.filter_by(**kwargs).first()

    @classmethod
    def create(cls, **kwargs):
        """Create and save a new record."""
        instance = cls(**kwargs)
        db.session.add(instance)
        db.session.commit()
        return instance

    @classmethod
    def paginate(cls, page: int = 1, per_page: int = 10, query=None):
        """Paginate records."""
        q = query if query is not None else cls.query
        return q.paginate(page=page, per_page=per_page, error_out=False)

    def update(self, **kwargs):
        """Update current instance with kwargs."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.updated_at = datetime.utcnow()
        db.session.commit()
        return self

    def delete(self):
        """Delete current instance."""
        db.session.delete(self)
        db.session.commit()

    def save(self):
        """Save current instance."""
        db.session.add(self)
        db.session.commit()
        return self

    def to_dict(self, exclude: list = None):
        """Convert model to dictionary."""
        exclude = exclude or []
        result = {}
        for column in self.__table__.columns:
            if column.name not in exclude:
                value = getattr(self, column.name)
                if isinstance(value, datetime):
                    value = value.isoformat()
                result[column.name] = value
        return result
