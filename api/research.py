"""Research grant tracking endpoints."""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema, auto_field

from lms_models import db, ResearchGrant, GrantMilestone, GrantStatus
from .roles_guard import roles_required


bp = Blueprint("research", __name__, url_prefix="/api/research")


class ResearchGrantSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = ResearchGrant
        include_fk = True
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)


class GrantMilestoneSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = GrantMilestone
        include_fk = True
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)


grant_schema = ResearchGrantSchema()
grant_many = ResearchGrantSchema(many=True)
milestone_schema = GrantMilestoneSchema()
milestone_many = GrantMilestoneSchema(many=True)


@bp.get("/")
@jwt_required(optional=True)
def list_grants():
    q = ResearchGrant.query
    status = request.args.get("status")
    if status:
        try:
            q = q.filter(ResearchGrant.status == GrantStatus(status))
        except Exception:
            return jsonify({"error": "invalid status"}), 400
    pi = request.args.get("principal_investigator")
    if pi:
        q = q.filter_by(principal_investigator=pi)
    return jsonify(grant_many.dump(q.order_by(ResearchGrant.start_date).all()))


@bp.post("/")
@jwt_required()
@roles_required("admin", "staff")
def create_grant():
    obj = grant_schema.load(request.get_json())
    db.session.add(obj)
    db.session.commit()
    return jsonify(grant_schema.dump(obj)), 201


@bp.get("/<uuid:grant_id>/milestones")
def list_milestones(grant_id):
    ResearchGrant.query.get_or_404(grant_id)
    q = GrantMilestone.query.filter_by(grant_id=grant_id)
    return jsonify(milestone_many.dump(q.order_by(GrantMilestone.due_date).all()))


@bp.post("/<uuid:grant_id>/milestones")
@jwt_required()
@roles_required("admin", "staff")
def create_milestone(grant_id):
    ResearchGrant.query.get_or_404(grant_id)
    payload = request.get_json() or {}
    payload["grant_id"] = str(grant_id)
    obj = milestone_schema.load(payload)
    db.session.add(obj)
    db.session.commit()
    return jsonify(milestone_schema.dump(obj)), 201


@bp.patch("/milestones/<uuid:milestone_id>")
@jwt_required()
@roles_required("admin", "staff")
def update_milestone(milestone_id):
    obj = GrantMilestone.query.get_or_404(milestone_id)
    obj = milestone_schema.load(request.get_json() or {}, instance=obj, partial=True)
    db.session.commit()
    return jsonify(milestone_schema.dump(obj))

