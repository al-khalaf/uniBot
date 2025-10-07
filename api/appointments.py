"""Appointments, advising, and office hours endpoints."""
from datetime import datetime

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from marshmallow import fields
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema, auto_field

from lms_models import (
    db,
    Appointment,
    AppointmentAttendee,
    AppointmentStatus,
    OfficeHour,
)
from .roles_guard import roles_required


bp = Blueprint("appointments", __name__, url_prefix="/api/appointments")


class AppointmentSchema(SQLAlchemyAutoSchema):
    status = fields.Method("_status", deserialize="load_status")

    class Meta:
        model = Appointment
        include_fk = True
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)

    def _status(self, obj):
        return obj.status.value if isinstance(obj.status, AppointmentStatus) else obj.status

    def load_status(self, value):  # pragma: no cover
        return AppointmentStatus(value)


class AppointmentAttendeeSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = AppointmentAttendee
        include_fk = True
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)


class OfficeHourSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = OfficeHour
        include_fk = True
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)


appt_schema = AppointmentSchema()
appt_many = AppointmentSchema(many=True)
attendee_schema = AppointmentAttendeeSchema()
attendee_many = AppointmentAttendeeSchema(many=True)
office_schema = OfficeHourSchema()
office_many = OfficeHourSchema(many=True)


def _current_user_id() -> str | None:
    try:
        return get_jwt().get("sub")
    except Exception:
        return None


@bp.get("/")
@jwt_required(optional=True)
def list_appointments():
    q = Appointment.query
    school_id = request.args.get("school_id")
    if school_id:
        q = q.filter_by(school_id=school_id)
    organizer_id = request.args.get("organizer_id") or _current_user_id()
    if organizer_id:
        q = q.filter_by(organizer_id=organizer_id)
    status = request.args.get("status")
    if status:
        try:
            q = q.filter(Appointment.status == AppointmentStatus(status))
        except Exception:
            return jsonify({"error": "invalid status"}), 400
    return jsonify(appt_many.dump(q.order_by(Appointment.starts_at).all()))


@bp.post("/")
@jwt_required()
def create_appointment():
    payload = request.get_json() or {}
    sub_id = _current_user_id()
    if sub_id and not payload.get("organizer_id"):
        payload["organizer_id"] = sub_id
    obj = appt_schema.load(payload)
    if obj.ends_at and obj.ends_at <= obj.starts_at:
        return jsonify({"error": "ends_at must be after starts_at"}), 400
    db.session.add(obj)
    db.session.commit()
    return jsonify(appt_schema.dump(obj)), 201


@bp.patch("/<uuid:appointment_id>")
@jwt_required()
def update_appointment(appointment_id):
    obj = Appointment.query.get_or_404(appointment_id)
    data = request.get_json() or {}
    if "status" in data:
        try:
            obj.status = AppointmentStatus(data["status"])
        except Exception:
            return jsonify({"error": "invalid status"}), 400
    if "starts_at" in data:
        obj.starts_at = datetime.fromisoformat(data["starts_at"])
    if "ends_at" in data:
        obj.ends_at = datetime.fromisoformat(data["ends_at"])
    if "title" in data:
        obj.title = data["title"]
    if "location" in data:
        obj.location = data["location"]
    db.session.commit()
    return jsonify(appt_schema.dump(obj))


@bp.get("/<uuid:appointment_id>/attendees")
@jwt_required(optional=True)
def list_attendees(appointment_id):
    Appointment.query.get_or_404(appointment_id)
    q = AppointmentAttendee.query.filter_by(appointment_id=appointment_id)
    return jsonify(attendee_many.dump(q.all()))


@bp.post("/<uuid:appointment_id>/attendees")
@jwt_required()
def add_attendee(appointment_id):
    Appointment.query.get_or_404(appointment_id)
    payload = request.get_json() or {}
    payload["appointment_id"] = str(appointment_id)
    obj = attendee_schema.load(payload)
    db.session.add(obj)
    db.session.commit()
    return jsonify(attendee_schema.dump(obj)), 201


@bp.delete("/attendees/<uuid:attendee_id>")
@jwt_required()
def remove_attendee(attendee_id):
    obj = AppointmentAttendee.query.get_or_404(attendee_id)
    db.session.delete(obj)
    db.session.commit()
    return jsonify({"deleted": True})


@bp.get("/office-hours")
def list_office_hours():
    q = OfficeHour.query
    teacher_id = request.args.get("teacher_id")
    if teacher_id:
        q = q.filter_by(teacher_id=teacher_id)
    day = request.args.get("day", type=int)
    if day is not None:
        q = q.filter_by(day_of_week=day)
    return jsonify(office_many.dump(q.order_by(OfficeHour.day_of_week, OfficeHour.start_time).all()))


@bp.post("/office-hours")
@jwt_required()
@roles_required("teacher", "staff", "admin")
def create_office_hour():
    obj = office_schema.load(request.get_json())
    db.session.add(obj)
    db.session.commit()
    return jsonify(office_schema.dump(obj)), 201


@bp.patch("/office-hours/<uuid:office_hour_id>")
@jwt_required()
@roles_required("teacher", "staff", "admin")
def update_office_hour(office_hour_id):
    obj = OfficeHour.query.get_or_404(office_hour_id)
    obj = office_schema.load(request.get_json() or {}, instance=obj, partial=True)
    db.session.commit()
    return jsonify(office_schema.dump(obj))

