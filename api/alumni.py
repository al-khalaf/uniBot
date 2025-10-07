"""Global alumni network endpoints."""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema, auto_field

from lms_models import db, AlumniProfile, AlumniEngagement, AlumniMentorship
from .roles_guard import roles_required


bp = Blueprint("alumni", __name__, url_prefix="/api/alumni")


class AlumniProfileSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = AlumniProfile
        include_fk = True
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)


class AlumniEngagementSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = AlumniEngagement
        include_fk = True
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)


class AlumniMentorshipSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = AlumniMentorship
        include_fk = True
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)


profile_schema = AlumniProfileSchema()
profile_many = AlumniProfileSchema(many=True)
engagement_schema = AlumniEngagementSchema()
engagement_many = AlumniEngagementSchema(many=True)
mentorship_schema = AlumniMentorshipSchema()
mentorship_many = AlumniMentorshipSchema(many=True)


@bp.get("/profiles")
def list_profiles():
    q = AlumniProfile.query
    year = request.args.get("graduation_year", type=int)
    if year:
        q = q.filter_by(graduation_year=year)
    interest = request.args.get("interest")
    if interest:
        q = q.filter(AlumniProfile.interests.contains([interest]))
    return jsonify(profile_many.dump(q.order_by(AlumniProfile.graduation_year.desc().nullslast()).all()))


@bp.post("/profiles")
@jwt_required()
def upsert_profile():
    payload = request.get_json() or {}
    existing = AlumniProfile.query.filter_by(user_id=payload.get("user_id")).first()
    if existing:
        obj = profile_schema.load(payload, instance=existing, partial=True)
    else:
        obj = profile_schema.load(payload)
        db.session.add(obj)
    db.session.commit()
    return jsonify(profile_schema.dump(obj))


@bp.get("/profiles/<uuid:alumni_id>/engagements")
def list_engagements(alumni_id):
    AlumniProfile.query.get_or_404(alumni_id)
    q = AlumniEngagement.query.filter_by(alumni_id=alumni_id)
    return jsonify(engagement_many.dump(q.order_by(AlumniEngagement.occurred_at.desc()).all()))


@bp.post("/profiles/<uuid:alumni_id>/engagements")
@jwt_required()
@roles_required("admin", "staff")
def create_engagement(alumni_id):
    AlumniProfile.query.get_or_404(alumni_id)
    payload = request.get_json() or {}
    payload["alumni_id"] = str(alumni_id)
    obj = engagement_schema.load(payload)
    db.session.add(obj)
    db.session.commit()
    return jsonify(engagement_schema.dump(obj)), 201


@bp.get("/mentorships")
def list_mentorships():
    q = AlumniMentorship.query
    mentor = request.args.get("mentor_id")
    if mentor:
        q = q.filter_by(mentor_id=mentor)
    mentee = request.args.get("mentee_student_id")
    if mentee:
        q = q.filter_by(mentee_student_id=mentee)
    return jsonify(mentorship_many.dump(q.order_by(AlumniMentorship.started_at.desc()).all()))


@bp.post("/mentorships")
@jwt_required()
@roles_required("admin", "staff")
def create_mentorship():
    obj = mentorship_schema.load(request.get_json())
    db.session.add(obj)
    db.session.commit()
    return jsonify(mentorship_schema.dump(obj)), 201

