"""Document workflows: templates, submissions, and transcript requests."""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from marshmallow import fields
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema, auto_field

from lms_models import (
    db,
    DocumentTemplate,
    DocumentSubmission,
    CustomForm,
    CustomFormSubmission,
    FinancialAidDocument,
    DocStatus,
    FormStatus,
)
from .roles_guard import roles_required


bp = Blueprint("documents", __name__, url_prefix="/api/documents")


class DocumentTemplateSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = DocumentTemplate
        include_fk = True
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)


class DocumentSubmissionSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = DocumentSubmission
        include_fk = True
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)
    status = fields.Method("_status", deserialize="load_status")

    def _status(self, obj):
        return obj.status.value if isinstance(obj.status, DocStatus) else obj.status

    def load_status(self, value):  # pragma: no cover - marshmallow hook
        return DocStatus(value)


class CustomFormSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = CustomForm
        include_fk = True
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)


class CustomFormSubmissionSchema(SQLAlchemyAutoSchema):
    status = fields.Method("_status", deserialize="load_status")

    class Meta:
        model = CustomFormSubmission
        include_fk = True
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)

    def _status(self, obj):
        return obj.status.value if isinstance(obj.status, FormStatus) else obj.status

    def load_status(self, value):  # pragma: no cover
        return FormStatus(value)


class FinancialAidDocumentSchema(SQLAlchemyAutoSchema):
    status = fields.Method("_status", deserialize="load_status")

    class Meta:
        model = FinancialAidDocument
        include_fk = True
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)

    def _status(self, obj):
        return obj.status.value if isinstance(obj.status, DocStatus) else obj.status

    def load_status(self, value):  # pragma: no cover
        return DocStatus(value)


template_schema = DocumentTemplateSchema()
template_many = DocumentTemplateSchema(many=True)
submission_schema = DocumentSubmissionSchema()
submission_many = DocumentSubmissionSchema(many=True)
form_schema = CustomFormSchema()
form_many = CustomFormSchema(many=True)
form_submission_schema = CustomFormSubmissionSchema()
form_submission_many = CustomFormSubmissionSchema(many=True)
aid_schema = FinancialAidDocumentSchema()
aid_many = FinancialAidDocumentSchema(many=True)


def _current_user_id() -> str | None:
    try:
        return get_jwt().get("sub")
    except Exception:  # no token
        return None


@bp.get("/templates")
def list_templates():
    q = DocumentTemplate.query
    school_id = request.args.get("school_id")
    if school_id:
        q = q.filter_by(school_id=school_id)
    return jsonify(template_many.dump(q.order_by(DocumentTemplate.name).all()))


@bp.post("/templates")
@jwt_required()
@roles_required("admin", "staff")
def create_template():
    obj = template_schema.load(request.get_json())
    db.session.add(obj)
    db.session.commit()
    return jsonify(template_schema.dump(obj)), 201


@bp.post("/submissions")
@jwt_required()
def submit_document():
    payload = request.get_json() or {}
    sub_id = _current_user_id()
    if sub_id and not payload.get("user_id"):
        payload["user_id"] = sub_id
    obj = submission_schema.load(payload)
    db.session.add(obj)
    db.session.commit()
    return jsonify(submission_schema.dump(obj)), 201


@bp.get("/submissions")
@jwt_required(optional=True)
def list_submissions():
    q = DocumentSubmission.query
    template_id = request.args.get("template_id")
    user_id = request.args.get("user_id") or _current_user_id()
    status = request.args.get("status")

    if template_id:
        q = q.filter_by(template_id=template_id)
    if user_id:
        q = q.filter_by(user_id=user_id)
    if status:
        try:
            q = q.filter(DocumentSubmission.status == DocStatus(status))
        except Exception:
            return jsonify({"error": "invalid status"}), 400

    return jsonify(submission_many.dump(q.order_by(DocumentSubmission.submitted_at.desc()).all()))


@bp.patch("/submissions/<uuid:submission_id>/status")
@jwt_required()
@roles_required("admin", "staff")
def update_submission_status(submission_id):
    obj = DocumentSubmission.query.get_or_404(submission_id)
    status = request.json.get("status") if request.is_json else None
    if not status:
        return jsonify({"error": "status is required"}), 400
    try:
        obj.status = DocStatus(status)
    except Exception:
        return jsonify({"error": "invalid status"}), 400
    db.session.commit()
    return jsonify(submission_schema.dump(obj))


@bp.get("/forms")
def list_forms():
    q = CustomForm.query
    school_id = request.args.get("school_id")
    if school_id:
        q = q.filter_by(school_id=school_id)
    audience = request.args.get("audience")
    if audience:
        q = q.filter(CustomForm.audience.contains([audience]))
    return jsonify(form_many.dump(q.order_by(CustomForm.title).all()))


@bp.post("/forms")
@jwt_required()
@roles_required("admin", "staff")
def create_form():
    obj = form_schema.load(request.get_json())
    db.session.add(obj)
    db.session.commit()
    return jsonify(form_schema.dump(obj)), 201


@bp.post("/forms/<uuid:form_id>/submit")
@jwt_required()
def submit_form(form_id):
    CustomForm.query.get_or_404(form_id)
    payload = request.get_json() or {}
    sub_id = _current_user_id()
    if sub_id and not payload.get("user_id"):
        payload["user_id"] = sub_id
    payload["form_id"] = str(form_id)
    obj = form_submission_schema.load(payload)
    db.session.add(obj)
    db.session.commit()
    return jsonify(form_submission_schema.dump(obj)), 201


@bp.get("/forms/<uuid:form_id>/submissions")
@jwt_required(optional=True)
def list_form_submissions(form_id):
    CustomForm.query.get_or_404(form_id)
    q = CustomFormSubmission.query.filter_by(form_id=form_id)
    user_id = request.args.get("user_id") or _current_user_id()
    if user_id:
        q = q.filter_by(user_id=user_id)
    return jsonify(form_submission_many.dump(q.order_by(CustomFormSubmission.submitted_at.desc()).all()))


@bp.get("/financial-aid")
@jwt_required(optional=True)
def list_financial_aid_documents():
    q = FinancialAidDocument.query
    user_id = request.args.get("student_id") or _current_user_id()
    if user_id:
        q = q.filter_by(student_id=user_id)
    status = request.args.get("status")
    if status:
        try:
            q = q.filter(FinancialAidDocument.status == DocStatus(status))
        except Exception:
            return jsonify({"error": "invalid status"}), 400
    return jsonify(aid_many.dump(q.order_by(FinancialAidDocument.submitted_at.desc()).all()))


@bp.post("/financial-aid")
@jwt_required()
def upload_financial_aid_document():
    payload = request.get_json() or {}
    sub_id = _current_user_id()
    if sub_id and not payload.get("student_id"):
        payload["student_id"] = sub_id
    obj = aid_schema.load(payload)
    db.session.add(obj)
    db.session.commit()
    return jsonify(aid_schema.dump(obj)), 201

