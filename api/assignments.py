# api/assignments.py
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema, auto_field

from lms_models import db, Assignment
from .roles_guard import roles_required

bp = Blueprint("assignments", __name__, url_prefix="/api/assignments")

# ------------ Schemas ------------
class AssignmentSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Assignment
        include_fk = True
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)   # that's it, no "extra"

schema = AssignmentSchema()
many = AssignmentSchema(many=True)

# ------------ Routes ------------
@bp.get("/")
def list_assignments():
    q = Assignment.query
    offering_id = request.args.get("course_offering_id")
    if offering_id:
        q = q.filter_by(course_offering_id=offering_id)
    return jsonify(many.dump(q.order_by(Assignment.title).all()))

@bp.get("/<uuid:assignment_id>")
def get_assignment(assignment_id):
    obj = Assignment.query.get_or_404(assignment_id)
    return jsonify(schema.dump(obj))

@bp.post("/")
@jwt_required()
@roles_required("admin", "staff")
def create_assignment():
    obj = schema.load(request.get_json())
    db.session.add(obj)
    db.session.commit()
    return jsonify(schema.dump(obj)), 201

@bp.put("/<uuid:assignment_id>")
@jwt_required()
@roles_required("admin", "staff")
def update_assignment(assignment_id):
    obj = Assignment.query.get_or_404(assignment_id)
    data = request.get_json() or {}
    # Only set attributes that exist on the model
    for f in ["course_offering_id", "title", "description", "due_date", "max_points"]:
        if f in data:
            setattr(obj, f, data[f])
    db.session.commit()
    return jsonify(schema.dump(obj))

@bp.delete("/<uuid:assignment_id>")
@jwt_required()
@roles_required("admin", "staff")
def delete_assignment(assignment_id):
    obj = Assignment.query.get_or_404(assignment_id)
    db.session.delete(obj)
    db.session.commit()
    return jsonify({"deleted": True})
