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
    id = db.Column(db.Uuid, primary_key=True, default=uuid.uuid4)
    # which occurrence of a recurring meeting?
    class_date = db.Column(db.Date, nullable=False, index=True)

    meeting_id = db.Column(db.Uuid, db.ForeignKey("class_meetings.id"), nullable=False, index=True)
    student_id = db.Column(db.Uuid, db.ForeignKey("users.id"), nullable=False, index=True)

    # present | late | absent | excused
    status = db.Column(db.String(16), nullable=False)
    notes = db.Column(db.String, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("class_date", "meeting_id", "student_id", name="uq_attendance_one_per_student_per_occurrence"),
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


# --- Dev utility ---------------------------------------------------------------
if __name__ == "__main__":  # pragma: no cover
    app = create_app()
    with app.app_context():
        db.create_all()
        print("Created all tables.")
