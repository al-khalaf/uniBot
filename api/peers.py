"""Peer finder and group matchmaking endpoints."""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema, auto_field

from lms_models import db, PeerMatchProfile, PeerMatch, PeerMatchStatus


bp = Blueprint("peers", __name__, url_prefix="/api/peers")


class PeerMatchProfileSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = PeerMatchProfile
        include_fk = True
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)


class PeerMatchSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = PeerMatch
        include_fk = True
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)


profile_schema = PeerMatchProfileSchema()
profile_many = PeerMatchProfileSchema(many=True)
match_schema = PeerMatchSchema()
match_many = PeerMatchSchema(many=True)


def _current_student_id() -> str | None:
    try:
        return get_jwt().get("sub")
    except Exception:
        return None


@bp.get("/profiles")
@jwt_required(optional=True)
def list_profiles():
    q = PeerMatchProfile.query
    course = request.args.get("course")
    if course:
        q = q.filter(PeerMatchProfile.courses.contains([course]))
    interest = request.args.get("interest")
    if interest:
        q = q.filter(PeerMatchProfile.interests.contains([interest]))
    return jsonify(profile_many.dump(q.all()))


@bp.post("/profiles")
@jwt_required()
def upsert_profile():
    payload = request.get_json() or {}
    sub_id = _current_student_id()
    if sub_id and not payload.get("student_id"):
        payload["student_id"] = sub_id
    existing = PeerMatchProfile.query.filter_by(student_id=payload.get("student_id")).first()
    if existing:
        obj = profile_schema.load(payload, instance=existing, partial=True)
    else:
        obj = profile_schema.load(payload)
        db.session.add(obj)
    db.session.commit()
    return jsonify(profile_schema.dump(obj))


@bp.get("/matches")
@jwt_required(optional=True)
def list_matches():
    q = PeerMatch.query
    sub_id = _current_student_id()
    student_id = request.args.get("student_id") or sub_id
    if student_id:
        q = q.filter((PeerMatch.requester_id == student_id) | (PeerMatch.partner_id == student_id))
    status = request.args.get("status")
    if status:
        try:
            q = q.filter(PeerMatch.status == PeerMatchStatus(status))
        except Exception:
            return jsonify({"error": "invalid status"}), 400
    return jsonify(match_many.dump(q.order_by(PeerMatch.created_at.desc()).all()))


@bp.post("/matches")
@jwt_required()
def request_match():
    payload = request.get_json() or {}
    sub_id = _current_student_id()
    if sub_id and not payload.get("requester_id"):
        payload["requester_id"] = sub_id
    obj = match_schema.load(payload)
    db.session.add(obj)
    db.session.commit()
    return jsonify(match_schema.dump(obj)), 201


@bp.patch("/matches/<uuid:match_id>")
@jwt_required()
def update_match(match_id):
    obj = PeerMatch.query.get_or_404(match_id)
    data = request.get_json() or {}
    if "status" in data:
        try:
            obj.status = PeerMatchStatus(data["status"])
        except Exception:
            return jsonify({"error": "invalid status"}), 400
    if "partner_id" in data:
        obj.partner_id = data["partner_id"]
    if "reason" in data:
        obj.reason = data["reason"]
    db.session.commit()
    return jsonify(match_schema.dump(obj))

