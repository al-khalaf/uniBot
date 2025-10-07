"""Graduation readiness tracker endpoints."""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema, auto_field

from lms_models import db, DegreeRequirement, StudentRequirementStatus
from .roles_guard import roles_required


bp = Blueprint("graduation", __name__, url_prefix="/api/graduation")


class DegreeRequirementSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = DegreeRequirement
        include_fk = True
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)


class StudentRequirementStatusSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = StudentRequirementStatus
        include_fk = True
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)


req_schema = DegreeRequirementSchema()
req_many = DegreeRequirementSchema(many=True)
status_schema = StudentRequirementStatusSchema()
status_many = StudentRequirementStatusSchema(many=True)


def _current_student() -> str | None:
    try:
        return get_jwt().get("sub")
    except Exception:
        return None


@bp.get("/requirements")
def list_requirements():
    program = request.args.get("program_code")
    q = DegreeRequirement.query
    if program:
        q = q.filter_by(program_code=program)
    return jsonify(req_many.dump(q.order_by(DegreeRequirement.name).all()))


@bp.post("/requirements")
@jwt_required()
@roles_required("admin", "staff")
def create_requirement():
    obj = req_schema.load(request.get_json())
    db.session.add(obj)
    db.session.commit()
    return jsonify(req_schema.dump(obj)), 201


@bp.get("/statuses")
@jwt_required(optional=True)
def list_statuses():
    q = StudentRequirementStatus.query
    student_id = request.args.get("student_id") or _current_student()
    if student_id:
        q = q.filter_by(student_id=student_id)
    requirement_id = request.args.get("requirement_id")
    if requirement_id:
        q = q.filter_by(requirement_id=requirement_id)
    return jsonify(status_many.dump(q.all()))


@bp.post("/statuses")
@jwt_required()
@roles_required("admin", "staff", "advisor")
def create_status():
    obj = status_schema.load(request.get_json())
    db.session.add(obj)
    db.session.commit()
    return jsonify(status_schema.dump(obj)), 201


@bp.patch("/statuses/<uuid:status_id>")
@jwt_required()
@roles_required("admin", "staff", "advisor")
def update_status(status_id):
    obj = StudentRequirementStatus.query.get_or_404(status_id)
    obj = status_schema.load(request.get_json() or {}, instance=obj, partial=True)
    db.session.commit()
    return jsonify(status_schema.dump(obj))

