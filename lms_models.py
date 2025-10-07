"""
Flask + SQLAlchemy models for a School-only LMS platform.
Covers core entities across scheduling, courses, users/roles, documents,
appointments, notifications, cafeteria, tickets, events, consent, policies,
research, surveys, analytics, career, alumni, and more.

Notes:
- Cross-DB friendly (SQLite dev, PostgreSQL prod). Uses JSON (not JSONB) for portability.
- UUID PKs. Migrations: Flask-Migrate/Alembic recommended.
- Keep classic ML/BI outside these models.
"""
from __future__ import annotations
import enum
import uuid
from datetime import datetime, date, time  # ← use the class names directly
from werkzeug.security import generate_password_hash, check_password_hash
from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column, relationship

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import (
    Enum, ForeignKey, CheckConstraint, UniqueConstraint,
    Table, Column, Integer, String, DateTime, Date, Time, Boolean, Text, JSON,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column

# --- DB setup -----------------------------------------------------------------

db = SQLAlchemy()

# Helpers to pick UUID type cross-DB
try:
    UUIDType = PG_UUID(as_uuid=True)  # type: ignore
except Exception:  # pragma: no cover
    UUIDType = String(36)

import uuid
from sqlalchemy.types import TypeDecorator, CHAR
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

class GUID(TypeDecorator):
    """
    Platform-independent UUID type.

    Uses PostgreSQL UUID on Postgres, otherwise stores as CHAR(36) string.
    """
    impl = CHAR
    cache_ok = True  # SQLAlchemy 2.x requirement for TypeDecorator

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        else:
            return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, uuid.UUID):
            # postgres can take uuid directly, others need string
            return str(value) if dialect.name != "postgresql" else value
        # if value is a string, make sure it’s a UUID string
        return str(uuid.UUID(str(value)))

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        # for Postgres (as_uuid=True) value is already UUID; for others it's str
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))

def gen_uuid() -> uuid.UUID:
    return uuid.uuid4()


# --- Enums --------------------------------------------------------------------

class Role(enum.Enum):
    STUDENT = "student"
    TEACHER = "teacher"
    STAFF = "staff"
    ADMIN = "admin"
    PARENT = "parent"


class Gender(enum.Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    UNSPECIFIED = "unspecified"


class DocStatus(enum.Enum):
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class TicketStatus(enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class AppointmentStatus(enum.Enum):
    SCHEDULED = "scheduled"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class NotificationChannel(enum.Enum):
    EMAIL = "email"
    SMS = "sms"
    WHATSAPP = "whatsapp"
    TELEGRAM = "telegram"
    PUSH = "push"


class DietaryTag(enum.Enum):
    HALAL = "halal"
    VEGETARIAN = "vegetarian"
    VEGAN = "vegan"
    GLUTEN_FREE = "gluten_free"
    NUT_FREE = "nut_free"
    DAIRY_FREE = "dairy_free"


class DeliveryOption(enum.Enum):
    PICKUP = "pickup"
    DELIVERY = "delivery"


class ConsentDecision(enum.Enum):
    APPROVED = "approved"
    REJECTED = "rejected"


class RiskLevel(enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class FormStatus(enum.Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class BookingStatus(enum.Enum):
    RESERVED = "reserved"
    CHECKED_OUT = "checked_out"
    RETURNED = "returned"
    CANCELLED = "cancelled"


class PeerMatchStatus(enum.Enum):
    PENDING = "pending"
    MATCHED = "matched"
    DECLINED = "declined"


class GrantStatus(enum.Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ON_HOLD = "on_hold"


class DisciplinaryStatus(enum.Enum):
    OPEN = "open"
    UNDER_REVIEW = "under_review"
    RESOLVED = "resolved"


class PluginStatus(enum.Enum):
    ENABLED = "enabled"
    DISABLED = "disabled"

# --- Association tables --------------------------------------------------------

user_roles = Table(
    "user_roles", db.metadata,
    Column("user_id", UUIDType, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role", Enum(Role), nullable=False, primary_key=True),
)

course_teachers = Table(
    "course_teachers", db.metadata,
    Column("course_offering_id", UUIDType, ForeignKey("course_offerings.id", ondelete="CASCADE"), primary_key=True),
    Column("teacher_id", UUIDType, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
)

menuitem_dietary = Table(
    "menuitem_dietary", db.metadata,
    Column("menu_item_id", UUIDType, ForeignKey("caf_menu_items.id", ondelete="CASCADE"), primary_key=True),
    Column("tag", Enum(DietaryTag), primary_key=True),
)

user_dietary = Table(
    "user_dietary", db.metadata,
    Column("user_id", UUIDType, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("tag", Enum(DietaryTag), primary_key=True),
)

club_members = Table(
    "club_members", db.metadata,
    Column("club_id", UUIDType, ForeignKey("clubs.id", ondelete="CASCADE"), primary_key=True),
    Column("user_id", UUIDType, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
)

faq_topics = Table(
    "faq_topics", db.metadata,
    Column("faq_id", UUIDType, ForeignKey("faqs.id", ondelete="CASCADE"), primary_key=True),
    Column("topic_id", UUIDType, ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True),
)

# --- Core org structure --------------------------------------------------------

class School(db.Model):
    __tablename__ = "schools"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    country: Mapped[str | None] = mapped_column(String(64))
    timezone: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    campuses = relationship("Campus", back_populates="school", cascade="all, delete-orphan")


class Campus(db.Model):
    __tablename__ = "campuses"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    school_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str | None] = mapped_column(String(255))

    school = relationship("School", back_populates="campuses")
    buildings = relationship("Building", back_populates="campus", cascade="all, delete-orphan")


class Building(db.Model):
    __tablename__ = "buildings"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    campus_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("campuses.id", ondelete="CASCADE"), nullable=False)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    campus = relationship("Campus", back_populates="buildings")
    rooms = relationship("Room", back_populates="building", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("campus_id", "code", name="uq_building_code_per_campus"),)


class Room(db.Model):
    __tablename__ = "rooms"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    building_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("buildings.id", ondelete="CASCADE"), nullable=False)
    number: Mapped[str] = mapped_column(String(32), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, default=30)

    building = relationship("Building", back_populates="rooms")
    __table_args__ = (UniqueConstraint("building_id", "number", name="uq_room_per_building"),)


# --- Users & profiles ----------------------------------------------------------

class User(db.Model):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    school_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    gender: Mapped[Gender | None] = mapped_column(Enum(Gender))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    password_hash: Mapped[str | None] = mapped_column(String(255))   # <--- add this line
    extra: Mapped[dict | None] = mapped_column("metadata", JSON)

    school = relationship("School")
    student_profile = relationship("StudentProfile", uselist=False, back_populates="user", cascade="all, delete-orphan")
    teacher_profile = relationship("TeacherProfile", uselist=False, back_populates="user", cascade="all, delete-orphan")
    parent_profile = relationship("ParentProfile", uselist=False, back_populates="user", cascade="all, delete-orphan")

    # helpers (not columns)
    def set_password(self, raw: str):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw: str) -> bool:
        return bool(self.password_hash) and check_password_hash(self.password_hash, raw)


class StudentProfile(db.Model):
    __tablename__ = "student_profiles"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    grade_level: Mapped[str] = mapped_column(String(32))  # e.g., "Grade 10"
    homeroom: Mapped[str | None] = mapped_column(String(32))
    gpa: Mapped[float | None] = mapped_column(db.Float)

    user = relationship("User", back_populates="student_profile")


class TeacherProfile(db.Model):
    __tablename__ = "teacher_profiles"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    title: Mapped[str | None] = mapped_column(String(64))
    office_room_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("rooms.id"))

    user = relationship("User", back_populates="teacher_profile")
    office_room = relationship("Room")


class ParentProfile(db.Model):
    __tablename__ = "parent_profiles"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    daily_spend_limit: Mapped[int | None] = mapped_column(Integer)

    user = relationship("User", back_populates="parent_profile")


class ParentChildLink(db.Model):
    __tablename__ = "parent_child_links"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    parent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    child_student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    __table_args__ = (UniqueConstraint("parent_id", "child_student_id", name="uq_parent_child"),)


# --- Academic structure --------------------------------------------------------

class AcademicYear(db.Model):
    __tablename__ = "academic_years"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    school_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(32))  # e.g., 2025-2026
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    __table_args__ = (UniqueConstraint("school_id", "name", name="uq_year_per_school"),)


class Term(db.Model):
    __tablename__ = "terms"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    academic_year_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("academic_years.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(32))  # Fall, Spring, etc.
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)


class Subject(db.Model):
    __tablename__ = "subjects"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    school_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    prerequisites: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (UniqueConstraint("school_id", "code", name="uq_subject_code"),)


class CourseOffering(db.Model):
    __tablename__ = "course_offerings"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    subject_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"))
    term_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("terms.id", ondelete="CASCADE"))
    section: Mapped[str] = mapped_column(String(8), default="A")
    capacity: Mapped[int] = mapped_column(Integer, default=30)
    extra: Mapped[dict | None] = mapped_column("metadata", JSON)

    subject = relationship("Subject")
    term = relationship("Term")
    teachers = relationship("User", secondary=course_teachers)
    meetings = relationship("ClassMeeting", back_populates="offering", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("subject_id", "term_id", "section", name="uq_offering"),)


class ClassMeeting(db.Model):
    __tablename__ = "class_meetings"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    course_offering_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("course_offerings.id", ondelete="CASCADE"))
    room_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("rooms.id"))
    day_of_week: Mapped[int] = mapped_column(Integer)  # 0=Mon ... 6=Sun
    start_time: Mapped[time] = mapped_column(db.Time, nullable=False)
    end_time:   Mapped[time] = mapped_column(db.Time, nullable=False)


    offering = relationship("CourseOffering", back_populates="meetings")
    room = relationship("Room")

    __table_args__ = (
        CheckConstraint("day_of_week >= 0 AND day_of_week <= 6", name="ck_dow"),
    )



class Enrollment(db.Model):
    __tablename__ = "enrollments"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    course_offering_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("course_offerings.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(16), default="enrolled")  # waitlisted, dropped
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("student_id", "course_offering_id", name="uq_enrollment"),)


class Assignment(db.Model):
    __tablename__ = "assignments"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    course_offering_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("course_offerings.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    due_at: Mapped[datetime | None] = mapped_column(DateTime)
    max_points: Mapped[int] = mapped_column(Integer, default=100)
    attachments: Mapped[dict | None] = mapped_column(JSON)



class AssignmentSubmission(db.Model):
    __tablename__ = "assignment_submissions"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    assignment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assignments.id", ondelete="CASCADE"))
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime)
    url: Mapped[str | None] = mapped_column(String(512))
    grade_points: Mapped[int | None] = mapped_column(Integer)
    feedback: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (UniqueConstraint("assignment_id", "student_id", name="uq_submission"),)


class Exam(db.Model):
    __tablename__ = "exams"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    course_offering_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("course_offerings.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime)
    room_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("rooms.id"))
    max_points: Mapped[int] = mapped_column(Integer, default=100)


class ExamGrade(db.Model):
    __tablename__ = "exam_grades"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    exam_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("exams.id", ondelete="CASCADE"))
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    points: Mapped[int] = mapped_column(Integer)
    __table_args__ = (UniqueConstraint("exam_id", "student_id", name="uq_exam_grade"),)


# --- Documents & templates -----------------------------------------------------

class DocumentTemplate(db.Model):
    __tablename__ = "document_templates"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    school_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    file_url: Mapped[str] = mapped_column(String(512))
    __table_args__ = (UniqueConstraint("school_id", "name", name="uq_template_name"),)


class DocumentSubmission(db.Model):
    __tablename__ = "document_submissions"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    template_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("document_templates.id"))
    title: Mapped[str] = mapped_column(String(255))
    status: Mapped[DocStatus] = mapped_column(Enum(DocStatus), default=DocStatus.SUBMITTED)
    data: Mapped[dict | None] = mapped_column(JSON)  # dynamic fields
    file_url: Mapped[str | None] = mapped_column(String(512))
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# --- Appointments & office hours ----------------------------------------------

class OfficeHour(db.Model):
    __tablename__ = "office_hours"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    teacher_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    day_of_week: Mapped[int] = mapped_column(Integer)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)

    __table_args__ = (
        CheckConstraint("day_of_week >= 0 AND day_of_week <= 6", name="ck_oh_dow"),
    )


class Appointment(db.Model):
    __tablename__ = "appointments"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    school_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"))
    organizer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(255))
    starts_at: Mapped[datetime] = mapped_column(DateTime)
    ends_at: Mapped[datetime] = mapped_column(DateTime)
    location: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[AppointmentStatus] = mapped_column(Enum(AppointmentStatus), default=AppointmentStatus.SCHEDULED)
    extra: Mapped[dict | None] = mapped_column("metadata", JSON)


class AppointmentAttendee(db.Model):
    __tablename__ = "appointment_attendees"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    appointment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("appointments.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(32))  # student/teacher/advisor
    __table_args__ = (UniqueConstraint("appointment_id", "user_id", name="uq_appt_user"),)


# --- Notifications -------------------------------------------------------------

class Notification(db.Model):
    __tablename__ = "notifications"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    school_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    channel: Mapped[NotificationChannel] = mapped_column(Enum(NotificationChannel))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime)
    payload: Mapped[dict | None] = mapped_column(JSON)


class NotificationSubscription(db.Model):
    __tablename__ = "notification_subscriptions"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    channel: Mapped[NotificationChannel] = mapped_column(Enum(NotificationChannel))
    address: Mapped[str] = mapped_column(String(255))  # email/phone/token
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (UniqueConstraint("user_id", "channel", "address", name="uq_sub"),)


# --- Cafeteria & orders --------------------------------------------------------

class CafMenuItem(db.Model):
    __tablename__ = "caf_menu_items"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    school_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    price_cents: Mapped[int] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class CafOrder(db.Model):
    __tablename__ = "caf_orders"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    school_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime)
    delivery_option: Mapped[DeliveryOption] = mapped_column(Enum(DeliveryOption), default=DeliveryOption.PICKUP)
    delivery_location: Mapped[str | None] = mapped_column(String(255))  # room like "2C"
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending, preparing, out, delivered, cancelled
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CafOrderItem(db.Model):
    __tablename__ = "caf_order_items"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("caf_orders.id", ondelete="CASCADE"))
    menu_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("caf_menu_items.id"))
    qty: Mapped[int] = mapped_column(Integer, default=1)


class UserDietaryPreference(db.Model):
    __tablename__ = "user_dietary_prefs"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    tags: Mapped[list[str] | None] = mapped_column(JSON)  # store enum names


# --- Tickets (IT/Facilities) ---------------------------------------------------

class Ticket(db.Model):
    __tablename__ = "tickets"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    school_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    category: Mapped[str] = mapped_column(String(64))  # it, facility
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[TicketStatus] = mapped_column(Enum(TicketStatus), default=TicketStatus.OPEN)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# --- Events & clubs ------------------------------------------------------------

class Event(db.Model):
    __tablename__ = "events"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    school_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    starts_at: Mapped[datetime] = mapped_column(DateTime)
    ends_at: Mapped[datetime] = mapped_column(DateTime)
    location: Mapped[str | None] = mapped_column(String(255))


class EventRegistration(db.Model):
    __tablename__ = "event_registrations"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    __table_args__ = (UniqueConstraint("event_id", "user_id", name="uq_event_user"),)


class Club(db.Model):
    __tablename__ = "clubs"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    school_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)


# --- FAQ / Policies / Searchable KB -------------------------------------------

class Topic(db.Model):
    __tablename__ = "topics"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    school_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(128))
    __table_args__ = (UniqueConstraint("school_id", "name", name="uq_topic"),)


class FAQ(db.Model):
    __tablename__ = "faqs"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    school_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"))
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(16), default="en")
    tags: Mapped[list[str] | None] = mapped_column(JSON)


class Policy(db.Model):
    __tablename__ = "policies"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    school_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    effective_date: Mapped[date | None] = mapped_column(Date)
    language: Mapped[str] = mapped_column(String(16), default="en")


# --- Consent & signatures ------------------------------------------------------

class ConsentForm(db.Model):
    __tablename__ = "consent_forms"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    school_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)


class ConsentRecord(db.Model):
    __tablename__ = "consent_records"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    form_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("consent_forms.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    decision: Mapped[ConsentDecision] = mapped_column(Enum(ConsentDecision))
    decided_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    signature_url: Mapped[str | None] = mapped_column(String(512))
    __table_args__ = (UniqueConstraint("form_id", "user_id", name="uq_consent_once"),)


# --- Risk & alerts -------------------------------------------------------------

class RiskAlert(db.Model):
    __tablename__ = "risk_alerts"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    level: Mapped[RiskLevel] = mapped_column(Enum(RiskLevel), default=RiskLevel.LOW)
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# --- Career / internships ------------------------------------------------------

class Opportunity(db.Model):
    __tablename__ = "opportunities"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    school_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(255))
    company: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    skills: Mapped[list[str] | None] = mapped_column(JSON)
    deadline: Mapped[date | None] = mapped_column(Date)


class OpportunityApplication(db.Model):
    __tablename__ = "opportunity_applications"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    opportunity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("opportunities.id", ondelete="CASCADE"))
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(32), default="draft")  # submitted, accepted, rejected
    resume_url: Mapped[str | None] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint("opportunity_id", "student_id", name="uq_opp_app"),)


# --- Surveys -------------------------------------------------------------------

class Survey(db.Model):
    __tablename__ = "surveys"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    school_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(255))
    spec: Mapped[dict | None] = mapped_column(JSON)  # questions schema


class SurveyResponse(db.Model):
    __tablename__ = "survey_responses"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    survey_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("surveys.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    answers: Mapped[dict | None] = mapped_column(JSON)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint("survey_id", "user_id", name="uq_survey_once"),)


# --- Library (lightweight hooks) ----------------------------------------------

class LibraryAction(db.Model):
    __tablename__ = "library_actions"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    school_id: Mapped[uuid.UUID] = mapped_column(UUIDType)
    user_id: Mapped[uuid.UUID] = mapped_column(UUIDType)
    action: Mapped[str] = mapped_column(String(64))  # renew, late_fee_info, search
    payload: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# --- Audit & logs --------------------------------------------------------------

class AuditLog(db.Model):
    __tablename__ = "audit_logs"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUIDType, nullable=True)
    school_id: Mapped[uuid.UUID | None] = mapped_column(UUIDType, nullable=True)
    action: Mapped[str] = mapped_column(String(64))
    entity: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[str | None] = mapped_column(String(64))
    details: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# --- Minimal Flask app factory -------------------------------------------------

def create_app(db_url: str = "sqlite:///lms.db") -> Flask:
    app = Flask(__name__)
    app.config.update(
        SQLALCHEMY_DATABASE_URI=db_url,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    db.init_app(app)

    @app.route("/health")
    def health():  # pragma: no cover
        return {"ok": True}

    return app

# --- Attendance (per meeting occurrence) ---
class Attendance(db.Model):
    __tablename__ = "attendance"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    # which occurrence of a recurring meeting?
    class_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    meeting_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("class_meetings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # present | late | absent | excused
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("class_date", "meeting_id", "student_id", name="uq_attendance_one_per_student_per_occurrence"),
    )

# --- Submission model ---
# --- Submission model ---
class Submission(db.Model):
    __tablename__ = "submissions"
    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)

    assignment_id: Mapped[uuid.UUID] = mapped_column(GUID(), db.ForeignKey("assignments.id"), nullable=False)
    student_id: Mapped[uuid.UUID] = mapped_column(GUID(), db.ForeignKey("users.id"), nullable=False)

    text_answer: Mapped[Optional[str]] = mapped_column(db.Text, nullable=True)
    content_url: Mapped[Optional[str]] = mapped_column(db.String(500), nullable=True)

    submitted_at: Mapped[datetime] = mapped_column(db.DateTime, default=datetime.utcnow, nullable=False)

    score: Mapped[Optional[float]] = mapped_column(db.Float, nullable=True)
    feedback: Mapped[Optional[str]] = mapped_column(db.Text, nullable=True)
    graded_at: Mapped[Optional[datetime]] = mapped_column(db.DateTime, nullable=True)

    status: Mapped[str] = mapped_column(db.String(20), default="submitted", nullable=False)

    assignment = relationship("Assignment", backref="submissions")
    student = relationship("User", backref="submissions")


# --- Directory & departments ---------------------------------------------------

class Department(db.Model):
    __tablename__ = "departments"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    school_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(32))
    website: Mapped[str | None] = mapped_column(String(255))
    hours: Mapped[dict | None] = mapped_column(JSON)

    services = relationship("DepartmentService", back_populates="department", cascade="all, delete-orphan")
    locations = relationship("DepartmentLocation", back_populates="department", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("school_id", "name", name="uq_department"),)


class DepartmentService(db.Model):
    __tablename__ = "department_services"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    department_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("departments.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    delivery_channels: Mapped[list[str] | None] = mapped_column(JSON)  # walk-in, email, portal

    department = relationship("Department", back_populates="services")


class DepartmentLocation(db.Model):
    __tablename__ = "department_locations"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    department_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("departments.id", ondelete="CASCADE"), nullable=False)
    building: Mapped[str | None] = mapped_column(String(128))
    room: Mapped[str | None] = mapped_column(String(64))
    latitude: Mapped[float | None] = mapped_column(db.Float)
    longitude: Mapped[float | None] = mapped_column(db.Float)

    department = relationship("Department", back_populates="locations")


# --- Identity & access ---------------------------------------------------------

class StudentIDCard(db.Model):
    __tablename__ = "student_id_cards"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    card_number: Mapped[str] = mapped_column(String(64), unique=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(32), default="active")


class AccessPermission(db.Model):
    __tablename__ = "access_permissions"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    area: Mapped[str] = mapped_column(String(128))  # e.g., "Science Lab", "Dorm A"
    granted_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    starts_at: Mapped[datetime | None] = mapped_column(DateTime)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime)


class ParkingPermit(db.Model):
    __tablename__ = "parking_permits"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    vehicle_plate: Mapped[str] = mapped_column(String(32))
    zone: Mapped[str | None] = mapped_column(String(32))
    issued_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(32), default="active")


# --- Financial planning --------------------------------------------------------

class Scholarship(db.Model):
    __tablename__ = "scholarships"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    school_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    amount: Mapped[int | None] = mapped_column(Integer)
    eligibility: Mapped[dict | None] = mapped_column(JSON)  # structured rules
    deadline: Mapped[date | None] = mapped_column(Date)


class ScholarshipMatch(db.Model):
    __tablename__ = "scholarship_matches"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    scholarship_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scholarships.id", ondelete="CASCADE"), nullable=False)
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    match_score: Mapped[float | None] = mapped_column(db.Float)
    reason: Mapped[str | None] = mapped_column(Text)
    notified_at: Mapped[datetime | None] = mapped_column(DateTime)

    __table_args__ = (UniqueConstraint("scholarship_id", "student_id", name="uq_scholarship_match"),)


class PaymentPlan(db.Model):
    __tablename__ = "payment_plans"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    total_amount: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(32), default="active")

    installments = relationship("PaymentInstallment", back_populates="plan", cascade="all, delete-orphan")


class PaymentInstallment(db.Model):
    __tablename__ = "payment_installments"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("payment_plans.id", ondelete="CASCADE"), nullable=False)
    due_date: Mapped[date] = mapped_column(Date)
    amount: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default="pending")

    plan = relationship("PaymentPlan", back_populates="installments")


class FinancialAidDocument(db.Model):
    __tablename__ = "financial_aid_documents"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    doc_type: Mapped[str] = mapped_column(String(64))
    status: Mapped[DocStatus] = mapped_column(Enum(DocStatus), default=DocStatus.SUBMITTED)
    file_url: Mapped[str | None] = mapped_column(String(512))
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# --- Custom forms & workflow ---------------------------------------------------

class CustomForm(db.Model):
    __tablename__ = "custom_forms"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    school_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    schema: Mapped[dict | None] = mapped_column(JSON)  # structured questions/fields
    audience: Mapped[list[str] | None] = mapped_column(JSON)


class CustomFormSubmission(db.Model):
    __tablename__ = "custom_form_submissions"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    form_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("custom_forms.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[FormStatus] = mapped_column(Enum(FormStatus), default=FormStatus.SUBMITTED)
    data: Mapped[dict | None] = mapped_column(JSON)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("form_id", "user_id", name="uq_form_submission_once"),)


# --- Smart reminders -----------------------------------------------------------

class SmartReminder(db.Model):
    __tablename__ = "smart_reminders"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    scope: Mapped[str] = mapped_column(String(64))  # course/assignment/exam
    target_id: Mapped[uuid.UUID | None] = mapped_column(UUIDType)
    channel: Mapped[NotificationChannel] = mapped_column(Enum(NotificationChannel))
    message: Mapped[str] = mapped_column(Text)
    send_at: Mapped[datetime] = mapped_column(DateTime)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime)


# --- Resource & lab booking ----------------------------------------------------

class Resource(db.Model):
    __tablename__ = "resources"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    school_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255))
    resource_type: Mapped[str] = mapped_column(String(64))  # lab_room, equipment
    capacity: Mapped[int | None] = mapped_column(Integer)
    details: Mapped[dict | None] = mapped_column("metadata", JSON)


class ResourceBooking(db.Model):
    __tablename__ = "resource_bookings"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    resource_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("resources.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime)
    ends_at: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[BookingStatus] = mapped_column(Enum(BookingStatus), default=BookingStatus.RESERVED)
    notes: Mapped[str | None] = mapped_column(Text)


# --- Peer finder ----------------------------------------------------------------

class PeerMatchProfile(db.Model):
    __tablename__ = "peer_match_profiles"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    courses: Mapped[list[str] | None] = mapped_column(JSON)
    interests: Mapped[list[str] | None] = mapped_column(JSON)
    availability: Mapped[dict | None] = mapped_column(JSON)


class PeerMatch(db.Model):
    __tablename__ = "peer_matches"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    requester_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    partner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    status: Mapped[PeerMatchStatus] = mapped_column(Enum(PeerMatchStatus), default=PeerMatchStatus.PENDING)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# --- Teaching assistant queue --------------------------------------------------

class TeachingAssistantQueue(db.Model):
    __tablename__ = "ta_queues"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    course_offering_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("course_offerings.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), default="Default Queue")
    description: Mapped[str | None] = mapped_column(Text)


class TeachingAssistantTicket(db.Model):
    __tablename__ = "ta_tickets"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    queue_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ta_queues.id", ondelete="CASCADE"), nullable=False)
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    topic: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)


# --- Leaderboards & gamification ----------------------------------------------

class Leaderboard(db.Model):
    __tablename__ = "leaderboards"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    school_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255))
    metric: Mapped[str] = mapped_column(String(64))  # attendance, volunteering
    period: Mapped[str | None] = mapped_column(String(32))


class LeaderboardEntry(db.Model):
    __tablename__ = "leaderboard_entries"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    leaderboard_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("leaderboards.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    score: Mapped[float] = mapped_column(db.Float)
    rank: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (UniqueConstraint("leaderboard_id", "user_id", name="uq_leaderboard_user"),)


# --- Graduation readiness ------------------------------------------------------

class DegreeRequirement(db.Model):
    __tablename__ = "degree_requirements"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    program_code: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    credit_hours: Mapped[int | None] = mapped_column(Integer)


class StudentRequirementStatus(db.Model):
    __tablename__ = "student_requirement_statuses"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    requirement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("degree_requirements.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    progress_detail: Mapped[dict | None] = mapped_column(JSON)

    __table_args__ = (UniqueConstraint("student_id", "requirement_id", name="uq_student_requirement"),)


# --- Study plans & adaptive learning ------------------------------------------

class StudyPlan(db.Model):
    __tablename__ = "study_plans"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    term_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("terms.id", ondelete="SET NULL"))
    goal: Mapped[str | None] = mapped_column(Text)
    strategy: Mapped[dict | None] = mapped_column(JSON)


class StudyTask(db.Model):
    __tablename__ = "study_tasks"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("study_plans.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255))
    due_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    metadata: Mapped[dict | None] = mapped_column(JSON)


class AdaptiveResource(db.Model):
    __tablename__ = "adaptive_resources"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    study_task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("study_tasks.id", ondelete="CASCADE"), nullable=False)
    modality: Mapped[str] = mapped_column(String(32))  # video, visual, textual
    content_url: Mapped[str | None] = mapped_column(String(512))
    notes: Mapped[str | None] = mapped_column(Text)


# --- Research & grants ---------------------------------------------------------

class ResearchGrant(db.Model):
    __tablename__ = "research_grants"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    title: Mapped[str] = mapped_column(String(255))
    principal_investigator: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    budget: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[GrantStatus] = mapped_column(Enum(GrantStatus), default=GrantStatus.ACTIVE)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    metadata: Mapped[dict | None] = mapped_column(JSON)


class GrantMilestone(db.Model):
    __tablename__ = "grant_milestones"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    grant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research_grants.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255))
    due_date: Mapped[date | None] = mapped_column(Date)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    notes: Mapped[str | None] = mapped_column(Text)


# --- Conduct & discipline ------------------------------------------------------

class DisciplinaryCase(db.Model):
    __tablename__ = "disciplinary_cases"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[DisciplinaryStatus] = mapped_column(Enum(DisciplinaryStatus), default=DisciplinaryStatus.OPEN)
    opened_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DisciplinaryAction(db.Model):
    __tablename__ = "disciplinary_actions"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("disciplinary_cases.id", ondelete="CASCADE"), nullable=False)
    action: Mapped[str] = mapped_column(String(255))
    taken_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    notes: Mapped[str | None] = mapped_column(Text)


# --- Alumni network ------------------------------------------------------------

class AlumniProfile(db.Model):
    __tablename__ = "alumni_profiles"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    graduation_year: Mapped[int | None] = mapped_column(Integer)
    current_role: Mapped[str | None] = mapped_column(String(255))
    location: Mapped[str | None] = mapped_column(String(255))
    interests: Mapped[list[str] | None] = mapped_column(JSON)


class AlumniEngagement(db.Model):
    __tablename__ = "alumni_engagements"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    alumni_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("alumni_profiles.id", ondelete="CASCADE"))
    activity: Mapped[str] = mapped_column(String(255))  # donation, mentorship, event
    detail: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AlumniMentorship(db.Model):
    __tablename__ = "alumni_mentorships"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    mentor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("alumni_profiles.id", ondelete="CASCADE"), nullable=False)
    mentee_student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    status: Mapped[str] = mapped_column(String(32), default="active")


# --- Plugin ecosystem ----------------------------------------------------------

class PluginIntegration(db.Model):
    __tablename__ = "plugin_integrations"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(64))
    metadata: Mapped[dict | None] = mapped_column(JSON)


class PluginInstallation(db.Model):
    __tablename__ = "plugin_installations"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    plugin_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("plugin_integrations.id", ondelete="CASCADE"), nullable=False)
    school_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[PluginStatus] = mapped_column(Enum(PluginStatus), default=PluginStatus.ENABLED)
    settings: Mapped[dict | None] = mapped_column(JSON)

    __table_args__ = (UniqueConstraint("plugin_id", "school_id", name="uq_plugin_school"),)


# --- Analytics -----------------------------------------------------------------

class DashboardMetric(db.Model):
    __tablename__ = "dashboard_metrics"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    school_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255))
    value: Mapped[float] = mapped_column(db.Float)
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    dimensions: Mapped[dict | None] = mapped_column(JSON)


class UsageTrend(db.Model):
    __tablename__ = "usage_trends"
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    school_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    metric: Mapped[str] = mapped_column(String(64))
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    value: Mapped[float] = mapped_column(db.Float)
    notes: Mapped[str | None] = mapped_column(Text)


# --- Dev utility ---------------------------------------------------------------
if __name__ == "__main__":  # pragma: no cover
    app = create_app()
    with app.app_context():
        db.create_all()
        print("Created all tables.")
