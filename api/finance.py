"""Financial planning tools: scholarships, payment plans, and matching."""
from datetime import datetime

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from marshmallow import fields
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema, auto_field

from lms_models import (
    db,
    Scholarship,
    ScholarshipMatch,
    PaymentPlan,
    PaymentInstallment,
)
from .roles_guard import roles_required


bp = Blueprint("finance", __name__, url_prefix="/api/finance")


class ScholarshipSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Scholarship
        include_fk = True
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)


class ScholarshipMatchSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = ScholarshipMatch
        include_fk = True
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)
    match_score = fields.Float(allow_none=True)


class PaymentPlanSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = PaymentPlan
        include_fk = True
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)


class PaymentInstallmentSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = PaymentInstallment
        include_fk = True
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)


scholarship_schema = ScholarshipSchema()
scholarship_many = ScholarshipSchema(many=True)
match_schema = ScholarshipMatchSchema()
match_many = ScholarshipMatchSchema(many=True)
plan_schema = PaymentPlanSchema()
plan_many = PaymentPlanSchema(many=True)
installment_schema = PaymentInstallmentSchema()
installment_many = PaymentInstallmentSchema(many=True)


def _current_user_id() -> str | None:
    try:
        return get_jwt().get("sub")
    except Exception:
        return None


@bp.get("/scholarships")
def list_scholarships():
    q = Scholarship.query
    school_id = request.args.get("school_id")
    if school_id:
        q = q.filter_by(school_id=school_id)
    deadline = request.args.get("deadline_before")
    if deadline:
        try:
            parsed = datetime.fromisoformat(deadline).date()
        except ValueError:
            return jsonify({"error": "deadline_before must be ISO date"}), 400
        q = q.filter(Scholarship.deadline <= parsed)
    order_clause = Scholarship.deadline.asc().nullsfirst()
    return jsonify(scholarship_many.dump(q.order_by(order_clause).all()))


@bp.post("/scholarships")
@jwt_required()
@roles_required("admin", "staff")
def create_scholarship():
    obj = scholarship_schema.load(request.get_json())
    db.session.add(obj)
    db.session.commit()
    return jsonify(scholarship_schema.dump(obj)), 201


@bp.get("/scholarships/<uuid:scholarship_id>/matches")
@jwt_required(optional=True)
def list_matches_for_scholarship(scholarship_id):
    Scholarship.query.get_or_404(scholarship_id)
    q = ScholarshipMatch.query.filter_by(scholarship_id=scholarship_id)
    order_clause = ScholarshipMatch.match_score.desc().nullslast()
    return jsonify(match_many.dump(q.order_by(order_clause).all()))


@bp.get("/matches")
@jwt_required(optional=True)
def list_matches():
    q = ScholarshipMatch.query
    student_id = request.args.get("student_id") or _current_user_id()
    if student_id:
        q = q.filter_by(student_id=student_id)
    order_clause = ScholarshipMatch.match_score.desc().nullslast()
    return jsonify(match_many.dump(q.order_by(order_clause).all()))


@bp.post("/matches")
@jwt_required()
@roles_required("admin", "staff")
def create_match():
    obj = match_schema.load(request.get_json())
    db.session.add(obj)
    db.session.commit()
    return jsonify(match_schema.dump(obj)), 201


@bp.get("/payment-plans")
@jwt_required(optional=True)
def list_payment_plans():
    q = PaymentPlan.query
    student_id = request.args.get("student_id") or _current_user_id()
    if student_id:
        q = q.filter_by(student_id=student_id)
    status = request.args.get("status")
    if status:
        q = q.filter_by(status=status)
    return jsonify(plan_many.dump(q.order_by(PaymentPlan.start_date.desc()).all()))


@bp.post("/payment-plans")
@jwt_required()
@roles_required("admin", "staff")
def create_payment_plan():
    obj = plan_schema.load(request.get_json())
    db.session.add(obj)
    db.session.commit()
    return jsonify(plan_schema.dump(obj)), 201


@bp.get("/payment-plans/<uuid:plan_id>/installments")
@jwt_required(optional=True)
def list_installments(plan_id):
    PaymentPlan.query.get_or_404(plan_id)
    q = PaymentInstallment.query.filter_by(plan_id=plan_id)
    return jsonify(installment_many.dump(q.order_by(PaymentInstallment.due_date).all()))


@bp.post("/payment-plans/<uuid:plan_id>/installments")
@jwt_required()
@roles_required("admin", "staff")
def add_installment(plan_id):
    PaymentPlan.query.get_or_404(plan_id)
    payload = request.get_json() or {}
    payload["plan_id"] = str(plan_id)
    obj = installment_schema.load(payload)
    db.session.add(obj)
    db.session.commit()
    return jsonify(installment_schema.dump(obj)), 201


@bp.patch("/installments/<uuid:installment_id>")
@jwt_required()
@roles_required("admin", "staff")
def update_installment(installment_id):
    obj = PaymentInstallment.query.get_or_404(installment_id)
    obj = installment_schema.load(request.get_json() or {}, instance=obj, partial=True)
    db.session.commit()
    return jsonify(installment_schema.dump(obj))

