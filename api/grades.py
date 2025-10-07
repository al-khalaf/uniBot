# api/grades.py
from __future__ import annotations
from uuid import UUID

from flask import Blueprint, request, jsonify, abort
from flask_jwt_extended import jwt_required, get_jwt
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema, auto_field

from api.roles_guard import roles_required
from lms_models import db, Grade, Assignment, Enrollment

bp = Blueprint("grades", __name__, url_prefix="/api/grades")

# ---------- Schemas ----------
class GradeSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Grade
        load_instance = True
        include_fk = True
        sqla_session = db.session

    id = auto_field(dump_only=True)
    assignment_id = auto_field(required=True)
    student_id = auto_field(required=True)
    score = auto_field(required=True)
    feedback = auto_field()
    graded_at = auto_field(dump_only=True)
    extra = auto_field()

schema = GradeSchema()
many = GradeSchema(many=True)

def _uuid_or_400(v: str, field: str) -> UUID:
    try:
        return UUID(v)
    except Exception:
        abort(400, description=f"Invalid {field}: must be UUID")

# ---------- Routes ----------
@bp.get("/")
@jwt_required(optional=True)
def list_grades():
    q = Grade.query
    assignment_id = request.args.get("assignment_id")
    student_id = request.args.get("student_id")
    if assignment_id:
        _uuid_or_400(assignment_id, "assignment_id")
        q = q.filter_by(assignment_id=assignment_id)
    if student_id:
        _uuid_or_400(student_id, "student_id")
        q = q.filter_by(student_id=student_id)
    return jsonify(many.dump(q.order_by(Grade.graded_at.desc()).all()))

@bp.get("/mine")
@jwt_required()
def my_grades():
    sub = get_jwt().get("sub")
    q = Grade.query.filter_by(student_id=sub)
    return jsonify(many.dump(q.order_by(Grade.graded_at.desc()).all()))

@bp.post("/")
@jwt_required()
@roles_required("admin", "staff")
def set_grade():
    """
    Upsert a grade for (assignment_id, student_id).
    Enforces: enrollment and bounds 0..max_points
    """
    data = request.get_json() or {}
    for key in ["assignment_id", "student_id", "score"]:
        if key not in data:
            return jsonify({"error": f"{key} is required"}), 400

    _uuid_or_400(str(data["assignment_id"]), "assignment_id")
    _uuid_or_400(str(data["student_id"]), "student_id")

    a = Assignment.query.get(data["assignment_id"])
    if not a:
        return jsonify({"error": "assignment not found"}), 404

    # Enrollment check
    enrolled = Enrollment.query.filter_by(
        student_id=data["student_id"], course_offering_id=a.course_offering_id
    ).first()
    if not enrolled:
        return jsonify({"error": "student not enrolled in assignment's course offering"}), 400

    try:
        score_val = float(data["score"])
    except Exception:
        return jsonify({"error": "score must be a number"}), 400

    if score_val < 0 or (a.max_points is not None and score_val > float(a.max_points)):
        return jsonify({"error": f"score must be between 0 and {a.max_points}"}), 400

    # upsert
    g = Grade.query.filter_by(
        assignment_id=data["assignment_id"], student_id=data["student_id"]
    ).first()
    if not g:
        g = Grade(
            assignment_id=data["assignment_id"],
            student_id=data["student_id"],
            score=score_val,
            feedback=data.get("feedback"),
        )
        db.session.add(g)
    else:
        g.score = score_val
        if "feedback" in data:
            g.feedback = data["feedback"]

    db.session.commit()
    return jsonify(schema.dump(g)), 201

@bp.delete("/<uuid:grade_id>")
@jwt_required()
@roles_required("admin", "staff")
def delete_grade(grade_id):
    g = Grade.query.get_or_404(grade_id)
    db.session.delete(g)
    db.session.commit()
    return jsonify({"deleted": True})
