from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from api.roles_guard import roles_required
from lms_models import db, Subject
from schemas.core import SubjectSchema

bp = Blueprint("subjects", __name__)
schema = SubjectSchema()
many = SubjectSchema(many=True)

@bp.get("/")
def list_subjects():
    q = Subject.query
    school_id = request.args.get("school_id")
    if school_id:
        q = q.filter_by(school_id=school_id)
    data = many.dump(q.order_by(Subject.code).all())
    return jsonify(data)

@bp.post("/")
@jwt_required()
@roles_required("admin", "staff")   # only admin/staff can create
def create_subject():
    obj = schema.load(request.get_json())
    db.session.add(obj)
    db.session.commit()
    return jsonify(schema.dump(obj)), 201
