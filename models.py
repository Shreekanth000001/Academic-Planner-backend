from typing import List
from typing import Optional
import enum
import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import Text
from sqlalchemy import ForeignKey
from datetime import datetime
from sqlalchemy import func, DateTime
from sqlalchemy import String
from sqlalchemy import Enum
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship
from sqlalchemy import Index

class Base(DeclarativeBase):
    pass

class PlanType(str, enum.Enum):
    FREE = "FREE"
    PRO = "PRO"

class UploadStatus(str, enum.Enum):
    PENDING="PENDING"
    PROCESSING="PROCESSING"
    COMPLETED="COMPLETED"
    FAILED="FAILED"

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
    
    uploads: Mapped[list["Upload"]] = relationship(back_populates="user")
    schedules: Mapped[list["Schedule"]] = relationship(back_populates="user")

    # def __repr__(self) -> str:
    #     return f"User(id={self.id!r}, name={self.name!r}, fullname={self.fullname!r})"

class Upload(Base):
    __tablename__ = "uploads"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id",ondelete="CASCADE"), index=True)
    file_url: Mapped[str] = mapped_column(String(255))
    file_hash: Mapped[str] = mapped_column(String(255), index=True)
    status: Mapped[UploadStatus] = mapped_column(Enum(UploadStatus,name="UploadStatus"), default=UploadStatus.PENDING)
    error_message:Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),server_default=func.now())
    
    user: Mapped["User"] = relationship(back_populates="uploads")
    schedule:Mapped["Schedule"] = relationship(back_populates="upload")
    syllabus_chunks: Mapped["SyllabusChunks"] = relationship(back_populates="uploads")


class Schedule(Base):
    __tablename__="schedules"
    id: Mapped[uuid.UUID]= mapped_column(UUID(as_uuid=True),primary_key=True,default=uuid.uuid4)
    user_id:Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True)
    upload_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("uploads.id",ondelete="CASCADE"),unique=True)
    title: Mapped[str] = mapped_column(String(255))
    exam_date:Mapped[datetime] = mapped_column(DateTime(timezone=True),server_default=func.now())
    is_active:Mapped[bool] = mapped_column(default=True)
    created_at:Mapped[datetime] = mapped_column(DateTime(timezone=True),server_default=func.now())

    user:Mapped["User"] = relationship(back_populates="schedules")
    upload:Mapped["Upload"] = relationship(back_populates="schedule")
    study_tasks:Mapped[List["StudyTask"]] = relationship(back_populates="schedule")

class StudyTask(Base):
    __tablename__= "study_tasks"

    __table_args__ = (
        Index("idx_schedule_assigned_date", "schedule_id", "assigned_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),primary_key=True,default=uuid.uuid4)
    schedule_id:Mapped[uuid.UUID] = mapped_column(ForeignKey("schedules.id",ondelete="CASCADE"))
    topic_name: Mapped[str] = mapped_column(String(255))
    assigned_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    order_index: Mapped[int] 
    estimated_minutes: Mapped[int]
    is_completed: Mapped[bool] = mapped_column(default=False)

    schedule: Mapped["Schedule"] = relationship(back_populates="study_tasks")

class SyllabusChunks(Base):
    __tablename__ = "syllabus_chunks"

    id : Mapped[int] = mapped_column(primary_key=True,autoincrement=True)
    upload_id: Mapped[uuid.UUID] =  mapped_column(ForeignKey("uploads.id",ondelete="CASCADE"))
    text_content: Mapped[str] = mapped_column(Text,nullable=False)
    embedding : Mapped[Vector] = mapped_column(Vector(1536))

    uploads: Mapped["Upload"] = relationship(back_populates="syllabus_chunks")