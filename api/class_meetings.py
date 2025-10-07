# api/class_meetings.py
from flask import Blueprint, request, jsonify, abort
from flask_jwt_extended import jwt_required
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema, auto_field

from lms_models import db, ClassMeeting
from .roles_guard import roles_required

bp = Blueprint("meetings", __name__, url_prefix="/api/meetings")

# ---------- Schemas ----------
class ClassMeetingSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = ClassMeeting
        include_fk = True
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)
    # DO NOT declare `extra` here — ClassMeeting doesn’t have it

schema = ClassMeetingSchema()
many = ClassMeetingSchema(many=True)

# ---------- Routes ----------
@bp.get("/")
def list_meetings():
    q = ClassMeeting.query
    offering_id = request.args.get("course_offering_id")
    room_id = request.args.get("room_id")
    day = request.args.get("day", type=int)

    if offering_id:
        q = q.filter_by(course_offering_id=offering_id)
    if room_id:
        q = q.filter_by(room_id=room_id)
    if day is not None:
        q = q.filter_by(day_of_week=day)

    items = q.order_by(ClassMeeting.day_of_week, ClassMeeting.start_time).all()
    return jsonify(many.dump(items))

@bp.post("/")
@jwt_required()
@roles_required("admin", "staff")
def create_meeting():
    obj = schema.load(request.get_json())
    db.session.add(obj)
    db.session.commit()
    return jsonify(schema.dump(obj)), 201

@bp.put("/<uuid:meeting_id>")
@jwt_required()
@roles_required("admin", "staff")
def update_meeting(meeting_id):
    m = ClassMeeting.query.get_or_404(meeting_id)
    data = request.get_json() or {}
    for f in ["course_offering_id", "room_id", "day_of_week", "start_time", "end_time"]:
        if f in data:
            setattr(m, f, data[f])
    db.session.commit()
    return jsonify(schema.dump(m))

@bp.delete("/<uuid:meeting_id>")
@jwt_required()
@roles_required("admin", "staff")
def delete_meeting(meeting_id):
    m = ClassMeeting.query.get_or_404(meeting_id)
    db.session.delete(m)
    db.session.commit()
    return jsonify({"deleted": True})
