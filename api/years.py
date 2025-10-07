from flask import Blueprint, request, jsonify
from lms_models import db, AcademicYear
from schemas.core import AcademicYearSchema

bp = Blueprint("years", __name__)
schema = AcademicYearSchema()
many = AcademicYearSchema(many=True)

@bp.get("/")
def list_years():
    q = AcademicYear.query
    school_id = request.args.get("school_id")
    if school_id:
        q = q.filter_by(school_id=school_id)
    return jsonify(many.dump(q.all()))

@bp.post("/")
def create_year():
    obj = schema.load(request.get_json())
    db.session.add(obj)
    db.session.commit()
    return jsonify(schema.dump(obj)), 201
