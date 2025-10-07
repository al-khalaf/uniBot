from flask import Blueprint, request, jsonify
from lms_models import db, Term
from schemas.core import TermSchema

bp = Blueprint("terms", __name__)
schema = TermSchema()
many = TermSchema(many=True)

@bp.get("/")
def list_terms():
    q = Term.query
    year_id = request.args.get("academic_year_id")
    if year_id:
        q = q.filter_by(academic_year_id=year_id)
    return jsonify(many.dump(q.all()))

@bp.post("/")
def create_term():
    obj = schema.load(request.get_json())
    db.session.add(obj)
    db.session.commit()
    return jsonify(schema.dump(obj)), 201
