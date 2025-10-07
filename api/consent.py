"""Consent and approval endpoints."""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from marshmallow import fields
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema, auto_field

from lms_models import db, ConsentForm, ConsentRecord, ConsentDecision
from .roles_guard import roles_required


bp = Blueprint("consent", __name__, url_prefix="/api/consent")


class ConsentFormSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = ConsentForm
        include_fk = True
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)


class ConsentRecordSchema(SQLAlchemyAutoSchema):
    decision = fields.Method("_decision", deserialize="load_decision")

    class Meta:
        model = ConsentRecord
        include_fk = True
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)

    def _decision(self, obj):
        return obj.decision.value if isinstance(obj.decision, ConsentDecision) else obj.decision

    def load_decision(self, value):  # pragma: no cover
        return ConsentDecision(value)


form_schema = ConsentFormSchema()
form_many = ConsentFormSchema(many=True)
record_schema = ConsentRecordSchema()
record_many = ConsentRecordSchema(many=True)


def _current_user_id() -> str | None:
    try:
        return get_jwt().get("sub")
    except Exception:
        return None


@bp.get("/forms")
@jwt_required(optional=True)
def list_forms():
    q = ConsentForm.query
    school_id = request.args.get("school_id")
    if school_id:
        q = q.filter_by(school_id=school_id)
    return jsonify(form_many.dump(q.order_by(ConsentForm.title).all()))


@bp.post("/forms")
@jwt_required()
@roles_required("admin", "staff")
def create_form():
    obj = form_schema.load(request.get_json())
    db.session.add(obj)
    db.session.commit()
    return jsonify(form_schema.dump(obj)), 201


@bp.get("/forms/<uuid:form_id>/records")
@jwt_required(optional=True)
def list_records(form_id):
    ConsentForm.query.get_or_404(form_id)
    q = ConsentRecord.query.filter_by(form_id=form_id)
    return jsonify(record_many.dump(q.order_by(ConsentRecord.decided_at.desc()).all()))


@bp.post("/forms/<uuid:form_id>/records")
@jwt_required(optional=True)
def create_record(form_id):
    ConsentForm.query.get_or_404(form_id)
    payload = request.get_json() or {}
    sub_id = _current_user_id()
    if sub_id and not payload.get("user_id"):
        payload["user_id"] = sub_id
    payload["form_id"] = str(form_id)
    obj = record_schema.load(payload)
    db.session.add(obj)
    db.session.commit()
    return jsonify(record_schema.dump(obj)), 201

