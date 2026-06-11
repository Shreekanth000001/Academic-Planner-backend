from typing import List
from typing import Optional
from sqlalchemy import ForeignKey
from datetime import datetime
from sqlalchemy import func, DateTime
from sqlalchemy import String
import enum
import uuid
from sqlalchemy import Enum
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

class Base(DeclarativeBase):
    pass

class PlanType(str, enum.Enum):
    FREE = "FREE"
    PRO = "PRO"

class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255),unique=True)
    clerk_id: Mapped[str] = mapped_column(String(255), unique=True)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    plan_type: Mapped[PlanType] = mapped_column(Enum(PlanType, name="PlanType"), default=PlanType.FREE)
    credits_remaining : Mapped[int] = mapped_column(default=2)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), 
        onupdate=func.now())
    
    # uploads: Mapped[list["Upload"]] = relationship(back_populates="user")

    # def __repr__(self) -> str:
    #     return f"User(id={self.id!r}, name={self.name!r}, fullname={self.fullname!r})"

