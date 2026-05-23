import uuid
from enum import Enum as PyEnum
from datetime import datetime, date, timezone
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, Enum, Index

# --- 1. ENUM DEFINITIONS ---
# We define these explicitly so Postgres creates native ENUM types, 
# rather than loosely validating Strings.
class PlanType(str, PyEnum):
    FREE = "FREE"
    PRO = "PRO"

class UploadStatus(str, PyEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

# --- 2. SQLMODEL CLASSES ---

class User(SQLModel, table=True):
    __tablename__ = "users" # Force plural table names

    # Use UUIDv4 to prevent ID enumeration attacks (e.g., guessing user IDs)
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    email: str = Field(unique=True, index=True)
    clerk_id: str = Field(unique=True, index=True)
    stripe_customer_id: Optional[str] = Field(default=None, unique=True)
    stripe_subscription_id: Optional[str] = Field(default=None, unique=True)
    
    # Enforce Postgres native ENUM
    plan_type: PlanType = Field(sa_column=Column(Enum(PlanType)), default=PlanType.FREE)
    credits_remaining: int = Field(default=2)
    
    # Always enforce UTC at the application level
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Relationships (The Graph)
    uploads: List["Upload"] = Relationship(back_populates="user")
    schedules: List["Schedule"] = Relationship(back_populates="user")


class Upload(SQLModel, table=True):
    __tablename__ = "uploads"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    file_url: str
    file_hash: str = Field(index=True)
    
    status: UploadStatus = Field(
        sa_column=Column(Enum(UploadStatus)), default=UploadStatus.PENDING
    )
    error_message: Optional[str] = Field(default=None)
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Relationships
    user: User = Relationship(back_populates="uploads")
    schedule: Optional["Schedule"] = Relationship(
        back_populates="upload", sa_relationship_kwargs={"uselist": False}
    )


class Schedule(SQLModel, table=True):
    __tablename__ = "schedules"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    upload_id: uuid.UUID = Field(foreign_key="uploads.id", unique=True)
    
    title: str
    exam_date: date
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Relationships
    user: User = Relationship(back_populates="schedules")
    upload: Upload = Relationship(back_populates="schedule")
    
    # cascade="all, delete-orphan" ensures that if a schedule is deleted, 
    # the DB engine automatically wipes the associated tasks.
    tasks: List["StudyTask"] = Relationship(
        back_populates="schedule",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )


class StudyTask(SQLModel, table=True):
    __tablename__ = "study_tasks"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    schedule_id: uuid.UUID = Field(foreign_key="schedules.id")
    topic_name: str
    assigned_date: date
    order_index: int
    estimated_minutes: int
    is_completed: bool = Field(default=False)

    # Relationships
    schedule: Schedule = Relationship(back_populates="tasks")

    # The Composite Index
    __table_args__ = (
        Index("ix_schedule_date", "schedule_id", "assigned_date"),
    )