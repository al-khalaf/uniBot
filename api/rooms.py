# api/rooms.py
from __future__ import annotations
from uuid import UUID

from flask import Blueprint, request, jsonify, abort
from flask_jwt_extended import jwt_required
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema, auto_field

from api.roles_guard import roles_required
from lms_models import db, Room, ClassMeeting

bp = Blueprint("rooms", __name__, url_prefix="/api/rooms")

# --------- Schemas ----------
class RoomSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Room
        load_instance = True
        include_fk = True
        sqla_session = db.session

    id = auto_field(dump_only=True)
    school_id = auto_field(required=True)
    name = auto_field(required=True)
    capacity = auto_field()
    extra = auto_field()

schema = RoomSchema()
many = RoomSchema(many=True)

def _uuid_or_400(v: str, field: str) -> UUID:
    try:
        return UUID(v)
    except Exception:
        abort(400, description=f"Invalid {field}: must be UUID")

def _overlaps(a_start, a_end, b_start, b_end) -> bool:
    return a_start < b_end and b_start < a_end

# --------- CRUD ----------
@bp.get("/")
def list_rooms():
    q = Room.query
    school_id = request.args.get("school_id")
    if school_id:
        _uuid_or_400(school_id, "school_id")
        q = q.filter_by(school_id=school_id)
    return jsonify(many.dump(q.order_by(Room.name).all()))

@bp.get("/<uuid:room_id>")
def get_room(room_id):
    r = Room.query.get_or_404(room_id)
    return jsonify(schema.dump(r))

@bp.post("/")
@jwt_required()
@roles_required("admin", "staff")
def create_room():
    data = request.get_json() or {}
    if "school_id" not in data or "name" not in data:
        return jsonify({"error": "school_id and name are required"}), 400
    _uuid_or_400(str(data["school_id"]), "school_id")
    obj = schema.load(data, session=db.session)
    db.session.add(obj)
    db.session.commit()
    return jsonify(schema.dump(obj)), 201

@bp.put("/<uuid:room_id>")
@jwt_required()
@roles_required("admin", "staff")
def update_room(room_id):
    r = Room.query.get_or_404(room_id)
    data = request.get_json() or {}
    for k in ["name", "capacity", "extra"]:
        if k in data:
            setattr(r, k, data[k])
    db.session.commit()
    return jsonify(schema.dump(r))

@bp.delete("/<uuid:room_id>")
@jwt_required()
@roles_required("admin", "staff")
def delete_room(room_id):
    r = Room.query.get_or_404(room_id)
    db.session.delete(r)
    db.session.commit()
    return jsonify({"deleted": True})

# --------- Availability ----------
@bp.get("/available")
def available_rooms():
    """
    Query params:
      - school_id (required)
      - day (0..6, required)
      - start_time (HH:MM, required)
      - end_time   (HH:MM, required)
      - min_capacity (optional)
    """
    school_id = request.args.get("school_id")
    day = request.args.get("day")
    start = request.args.get("start_time")
    end = request.args.get("end_time")
    min_cap = request.args.get("min_capacity")

    if not school_id or day is None or not start or not end:
        return jsonify({"error": "school_id, day, start_time, end_time required"}), 400

    _uuid_or_400(school_id, "school_id")
    try:
        day = int(day)
        assert 0 <= day <= 6
    except Exception:
        return jsonify({"error": "day must be 0..6"}), 400

    # parse times by letting SQLAlchemy convert strings via model
    from datetime import time
    try:
        sh, sm = map(int, start.split(":"))
        eh, em = map(int, end.split(":"))
        start_t = time(sh, sm)
        end_t = time(eh, em)
        if start_t >= end_t:
            return jsonify({"error": "start_time must be before end_time"}), 400
    except Exception:
        return jsonify({"error": "invalid time format; use HH:MM"}), 400

    room_q = Room.query.filter_by(school_id=school_id)
    if min_cap:
        try:
            room_q = room_q.filter(Room.capacity >= int(min_cap))
        except Exception:
            return jsonify({"error": "min_capacity must be integer"}), 400

    rooms = room_q.all()
    if not rooms:
        return jsonify([])

    # pull meetings that clash
    busy = (
        ClassMeeting.query
        .filter(ClassMeeting.day_of_week == day, ClassMeeting.room_id.isnot(None))
        .all()
    )

    free = []
    for r in rooms:
        # meetings in this room that overlap
        clashes = [
            m for m in busy if m.room_id == r.id and _overlaps(start_t, end_t, m.start_time, m.end_time)
        ]
        if not clashes:
            free.append(r)

    return jsonify(many.dump(free))

# --------- Quick seed (optional) ----------
@bp.post("/seed_demo")
@jwt_required()
@roles_required("admin")
def seed_demo():
    """
    Makes a couple of rooms for the current school quickly.
    Body: { "school_id": "<uuid>" }
    """
    data = request.get_json() or {}
    if "school_id" not in data:
        return jsonify({"error": "school_id required"}), 400
    _uuid_or_400(str(data["school_id"]), "school_id")

    existing = Room.query.filter_by(school_id=data["school_id"]).count()
    if existing == 0:
        rooms = [
            Room(school_id=data["school_id"], name="A-101", capacity=40),
            Room(school_id=data["school_id"], name="A-102", capacity=30),
            Room(school_id=data["school_id"], name="Lab-1", capacity=25),
        ]
        db.session.add_all(rooms)
        db.session.commit()

    return jsonify(many.dump(Room.query.filter_by(school_id=data["school_id"]).order_by(Room.name).all()))
