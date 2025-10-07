"""Internship and employer portal endpoints."""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema, auto_field

from lms_models import db, Opportunity, OpportunityApplication
from .roles_guard import roles_required


bp = Blueprint("opportunities", __name__, url_prefix="/api/opportunities")


class OpportunitySchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Opportunity
        include_fk = True
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)


class OpportunityApplicationSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = OpportunityApplication
        include_fk = True
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)


opp_schema = OpportunitySchema()
opp_many = OpportunitySchema(many=True)
app_schema = OpportunityApplicationSchema()
app_many = OpportunityApplicationSchema(many=True)


def _current_user_id() -> str | None:
    try:
        return get_jwt().get("sub")
    except Exception:
        return None


@bp.get("/")
def list_opportunities():
    q = Opportunity.query
    school_id = request.args.get("school_id")
    if school_id:
        q = q.filter_by(school_id=school_id)
    skill = request.args.get("skill")
    if skill:
        q = q.filter(Opportunity.skills.contains([skill]))
    return jsonify(opp_many.dump(q.order_by(Opportunity.deadline).all()))


@bp.post("/")
@jwt_required()
@roles_required("admin", "staff")
def create_opportunity():
    obj = opp_schema.load(request.get_json())
    db.session.add(obj)
    db.session.commit()
    return jsonify(opp_schema.dump(obj)), 201


@bp.get("/<uuid:opportunity_id>/applications")
@jwt_required(optional=True)
def list_applications(opportunity_id):
    Opportunity.query.get_or_404(opportunity_id)
    q = OpportunityApplication.query.filter_by(opportunity_id=opportunity_id)
    return jsonify(app_many.dump(q.order_by(OpportunityApplication.created_at.desc()).all()))


@bp.post("/<uuid:opportunity_id>/applications")
@jwt_required(optional=True)
def apply(opportunity_id):
    Opportunity.query.get_or_404(opportunity_id)
    payload = request.get_json() or {}
    sub_id = _current_user_id()
    if sub_id and not payload.get("student_id"):
        payload["student_id"] = sub_id
    payload["opportunity_id"] = str(opportunity_id)
    obj = app_schema.load(payload)
    db.session.add(obj)
    db.session.commit()
    return jsonify(app_schema.dump(obj)), 201

