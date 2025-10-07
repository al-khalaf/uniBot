"""Academic risk alerts endpoints."""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema, auto_field

from lms_models import db, RiskAlert, RiskLevel
from .roles_guard import roles_required


bp = Blueprint("risks", __name__, url_prefix="/api/risks")


class RiskAlertSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = RiskAlert
        include_fk = True
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)


risk_schema = RiskAlertSchema()
risk_many = RiskAlertSchema(many=True)


@bp.get("/")
@jwt_required(optional=True)
def list_risks():
    q = RiskAlert.query
    student_id = request.args.get("student_id")
    if student_id:
        q = q.filter_by(student_id=student_id)
    level = request.args.get("level")
    if level:
        try:
            q = q.filter(RiskAlert.level == RiskLevel(level))
        except Exception:
            return jsonify({"error": "invalid level"}), 400
    return jsonify(risk_many.dump(q.order_by(RiskAlert.created_at.desc()).all()))


@bp.post("/")
@jwt_required()
@roles_required("admin", "staff", "advisor")
def create_risk():
    obj = risk_schema.load(request.get_json())
    db.session.add(obj)
    db.session.commit()
    return jsonify(risk_schema.dump(obj)), 201

