from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema, auto_field

from lms_models import db, Submission
from .roles_guard import roles_required

bp = Blueprint("submissions", __name__, url_prefix="/api/submissions")

# --------- Schemas ----------
class SubmissionSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Submission
        include_fk = True
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)

schema = SubmissionSchema()
many = SubmissionSchema(many=True)

def _is_admin_or_staff():
    claims = get_jwt()
    roles = set(claims.get("roles", []))
    return bool({"admin", "staff"} & roles)

def _user_sub():
    claims = get_jwt()
    return claims.get("sub")

# --------- Routes ----------
@bp.get("/")
@jwt_required(optional=True)
def list_submissions():
    """
    Admin/staff see all. Students only see their own, unless they pass ?assignment_id and still limited to themselves.
    """
    q = Submission.query
    assignment_id = request.args.get("assignment_id")
    student_id = request.args.get("student_id")
    if assignment_id:
        q = q.filter_by(assignment_id=assignment_id)
    if student_id:
        q = q.filter_by(student_id=student_id)

    claims_sub = _user_sub()
    if not _is_admin_or_staff():
        # students only see their own subs
        q = q.filter_by(student_id=claims_sub)

    return jsonify(many.dump(q.order_by(Submission.submitted_at.desc()).all()))

@bp.get("/<uuid:submission_id>")
@jwt_required(optional=True)
def get_submission(submission_id):
    s = Submission.query.get_or_404(submission_id)
    if not _is_admin_or_staff() and str(s.student_id) != (_user_sub() or ""):
        return jsonify({"error": "not allowed"}), 403
    return jsonify(schema.dump(s))

@bp.post("/")
@jwt_required()
def create_submission():
    """
    Students: can only create their own submission (student_id must match token sub).
    Admin/staff: can create for any student.
    Body: assignment_id, [text_answer|content_url], [student_id]
    """
    payload = request.get_json() or {}

    if not _is_admin_or_staff():
        # force student_id to be token sub
        payload["student_id"] = _user_sub()

    obj = schema.load(payload)
    db.session.add(obj)
    db.session.commit()
    return jsonify(schema.dump(obj)), 201

@bp.put("/<uuid:submission_id>")
@jwt_required()
def update_submission(submission_id):
    """
    Students: can edit their own before grading (e.g., update text/content); cannot set score/feedback.
    Admin/staff: can edit anything, incl. grading fields.
    """
    s = Submission.query.get_or_404(submission_id)
    is_staff = _is_admin_or_staff()
    is_self = str(s.student_id) == _user_sub()

    if not (is_staff or is_self):
        return jsonify({"error": "not allowed"}), 403

    data = request.get_json() or {}
    editable_self = {"text_answer", "content_url"}  # students can update these
    editable_staff = {"text_answer", "content_url", "score", "feedback", "status"}

    for f in (editable_staff if is_staff else editable_self):
        if f in data:
            setattr(s, f, data[f])

    # grade timestamp
    if is_staff and ("score" in data or "feedback" in data or data.get("status") == "graded"):
        from datetime import datetime
        s.graded_at = datetime.utcnow()
        if "status" not in data:
            s.status = "graded"

    db.session.commit()
    return jsonify(schema.dump(s))

@bp.delete("/<uuid:submission_id>")
@jwt_required()
def delete_submission(submission_id):
    s = Submission.query.get_or_404(submission_id)
    if not (_is_admin_or_staff() or str(s.student_id) == _user_sub()):
        return jsonify({"error": "not allowed"}), 403
    db.session.delete(s)
    db.session.commit()
    return jsonify({"deleted": True})
