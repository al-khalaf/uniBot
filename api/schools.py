from flask import Blueprint, request, jsonify
from lms_models import db, School
from schemas.core import SchoolSchema

bp = Blueprint("schools", __name__)
schema = SchoolSchema()
many = SchoolSchema(many=True)

@bp.get("/")
def list_schools():
    return jsonify(many.dump(School.query.order_by(School.name).all()))

@bp.post("/")
def create_school():
    obj = schema.load(request.get_json())
    db.session.add(obj)
    db.session.commit()
    return jsonify(schema.dump(obj)), 201

@bp.get("/<uuid:school_id>")
def get_school(school_id):
    s = School.query.get_or_404(school_id)
    return jsonify(schema.dump(s))
