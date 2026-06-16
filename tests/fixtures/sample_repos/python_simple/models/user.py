"""User model fixture."""

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    """SQLAlchemy model fixture."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]

    def to_dict(self) -> dict[str, object]:
        return {"id": self.id, "name": self.name}
