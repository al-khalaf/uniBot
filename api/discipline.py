"""Disciplinary record and conduct tracking endpoints."""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema, auto_field

from lms_models import db, DisciplinaryCase, DisciplinaryAction, DisciplinaryStatus
from .roles_guard import roles_required


bp = Blueprint("discipline", __name__, url_prefix="/api/discipline")


class DisciplinaryCaseSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = DisciplinaryCase
        include_fk = True
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)


class DisciplinaryActionSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = DisciplinaryAction
        include_fk = True
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)


case_schema = DisciplinaryCaseSchema()
case_many = DisciplinaryCaseSchema(many=True)
action_schema = DisciplinaryActionSchema()
action_many = DisciplinaryActionSchema(many=True)


def _current_user() -> str | None:
    try:
        return get_jwt().get("sub")
    except Exception:
        return None


@bp.get("/cases")
@jwt_required(optional=True)
def list_cases():
    q = DisciplinaryCase.query
    student_id = request.args.get("student_id") or _current_user()
    if student_id:
        q = q.filter_by(student_id=student_id)
    status = request.args.get("status")
    if status:
        try:
            q = q.filter(DisciplinaryCase.status == DisciplinaryStatus(status))
        except Exception:
            return jsonify({"error": "invalid status"}), 400
    return jsonify(case_many.dump(q.order_by(DisciplinaryCase.opened_at.desc()).all()))


@bp.post("/cases")
@jwt_required()
@roles_required("admin", "staff")
def create_case():
    obj = case_schema.load(request.get_json())
    db.session.add(obj)
    db.session.commit()
    return jsonify(case_schema.dump(obj)), 201


@bp.patch("/cases/<uuid:case_id>")
@jwt_required()
@roles_required("admin", "staff")
def update_case(case_id):
    obj = DisciplinaryCase.query.get_or_404(case_id)
    obj = case_schema.load(request.get_json() or {}, instance=obj, partial=True)
    db.session.commit()
    return jsonify(case_schema.dump(obj))


@bp.get("/cases/<uuid:case_id>/actions")
@jwt_required(optional=True)
def list_actions(case_id):
    DisciplinaryCase.query.get_or_404(case_id)
    q = DisciplinaryAction.query.filter_by(case_id=case_id)
    return jsonify(action_many.dump(q.order_by(DisciplinaryAction.taken_at).all()))


@bp.post("/cases/<uuid:case_id>/actions")
@jwt_required()
@roles_required("admin", "staff")
def create_action(case_id):
    DisciplinaryCase.query.get_or_404(case_id)
    payload = request.get_json() or {}
    payload["case_id"] = str(case_id)
    obj = action_schema.load(payload)
    db.session.add(obj)
    db.session.commit()
    return jsonify(action_schema.dump(obj)), 201

