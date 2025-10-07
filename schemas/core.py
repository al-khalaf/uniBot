# schemas/core.py
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema, auto_field
from lms_models import db, School, AcademicYear, Term, Subject, CourseOffering, Enrollment, Assignment

from lms_models import (
    db, School, AcademicYear, Term, Subject, CourseOffering,
    Enrollment, Assignment, ClassMeeting, Attendance   # <-- add ClassMeeting
)

class ClassMeetingSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = ClassMeeting
        include_fk = True
        load_instance = True
        sqla_session = db.session
    id = auto_field(dump_only=True)


class SchoolSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = School
        include_fk = True
        load_instance = True
        sqla_session = db.session
    id = auto_field(dump_only=True)

class AcademicYearSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = AcademicYear
        include_fk = True
        load_instance = True
        sqla_session = db.session
    id = auto_field(dump_only=True)

class TermSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Term
        include_fk = True
        load_instance = True
        sqla_session = db.session
    id = auto_field(dump_only=True)

class SubjectSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Subject
        include_fk = True
        load_instance = True
        sqla_session = db.session
    id = auto_field(dump_only=True)

class OfferingSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = CourseOffering
        include_fk = True
        load_instance = True
        sqla_session = db.session
    id = auto_field(dump_only=True)

class EnrollmentSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Enrollment
        include_fk = True
        load_instance = True
        sqla_session = db.session
    id = auto_field(dump_only=True)

class AssignmentSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Assignment
        include_fk = True
        load_instance = True
        sqla_session = db.session
    id = auto_field(dump_only=True)

# Attendance schema
class AttendanceSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Attendance
        load_instance = True
        include_fk = True
        sqla_session = db.session

    id = auto_field(dump_only=True)
    class_date = auto_field(required=True)  # "YYYY-MM-DD"
    meeting_id = auto_field(required=True)
    student_id = auto_field(required=True)
    status = auto_field(required=True)      # present|late|absent|excused
    notes = auto_field()
