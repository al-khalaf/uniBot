"""Campus life and events endpoints."""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema, auto_field

from lms_models import db, Event, EventRegistration, Club, club_members
from .roles_guard import roles_required


bp = Blueprint("events", __name__, url_prefix="/api/events")


class EventSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Event
        include_fk = True
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)


class EventRegistrationSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = EventRegistration
        include_fk = True
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)


class ClubSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Club
        include_fk = True
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)


event_schema = EventSchema()
event_many = EventSchema(many=True)
registration_schema = EventRegistrationSchema()
registration_many = EventRegistrationSchema(many=True)
club_schema = ClubSchema()
club_many = ClubSchema(many=True)


def _current_user_id() -> str | None:
    try:
        return get_jwt().get("sub")
    except Exception:
        return None


@bp.get("/")
def list_events():
    q = Event.query
    school_id = request.args.get("school_id")
    if school_id:
        q = q.filter_by(school_id=school_id)
    return jsonify(event_many.dump(q.order_by(Event.starts_at).all()))


@bp.post("/")
@jwt_required()
@roles_required("admin", "staff")
def create_event():
    obj = event_schema.load(request.get_json())
    db.session.add(obj)
    db.session.commit()
    return jsonify(event_schema.dump(obj)), 201


@bp.get("/<uuid:event_id>/registrations")
@jwt_required(optional=True)
def list_registrations(event_id):
    Event.query.get_or_404(event_id)
    q = EventRegistration.query.filter_by(event_id=event_id)
    return jsonify(registration_many.dump(q.all()))


@bp.post("/<uuid:event_id>/registrations")
@jwt_required(optional=True)
def create_registration(event_id):
    Event.query.get_or_404(event_id)
    payload = request.get_json() or {}
    sub_id = _current_user_id()
    if sub_id and not payload.get("user_id"):
        payload["user_id"] = sub_id
    payload["event_id"] = str(event_id)
    obj = registration_schema.load(payload)
    db.session.add(obj)
    db.session.commit()
    return jsonify(registration_schema.dump(obj)), 201


@bp.get("/clubs")
def list_clubs():
    q = Club.query
    school_id = request.args.get("school_id")
    if school_id:
        q = q.filter_by(school_id=school_id)
    return jsonify(club_many.dump(q.order_by(Club.name).all()))


@bp.post("/clubs")
@jwt_required()
@roles_required("admin", "staff")
def create_club():
    obj = club_schema.load(request.get_json())
    db.session.add(obj)
    db.session.commit()
    return jsonify(club_schema.dump(obj)), 201


@bp.post("/clubs/<uuid:club_id>/join")
@jwt_required()
def join_club(club_id):
    Club.query.get_or_404(club_id)
    user_id = request.get_json(silent=True) or {}
    user = user_id.get("user_id") or _current_user_id()
    if not user:
        return jsonify({"error": "user_id required"}), 400
    db.session.execute(club_members.insert().values(club_id=club_id, user_id=user))
    db.session.commit()
    return jsonify({"joined": True})


@bp.delete("/clubs/<uuid:club_id>/leave")
@jwt_required()
def leave_club(club_id):
    Club.query.get_or_404(club_id)
    user_id = request.get_json(silent=True) or {}
    user = user_id.get("user_id") or _current_user_id()
    if not user:
        return jsonify({"error": "user_id required"}), 400
    db.session.execute(
        club_members.delete().where(
            (club_members.c.club_id == club_id) & (club_members.c.user_id == user)
        )
    )
    db.session.commit()
    return jsonify({"left": True})

