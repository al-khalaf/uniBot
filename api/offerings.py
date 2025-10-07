from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from api.roles_guard import roles_required
from lms_models import db, CourseOffering
from schemas.core import OfferingSchema

bp = Blueprint("offerings", __name__)
schema = OfferingSchema()
many = OfferingSchema(many=True)

@bp.get("/")
def list_offerings():
    q = CourseOffering.query
    subject_id = request.args.get("subject_id")
    term_id = request.args.get("term_id")
    if subject_id:
        q = q.filter_by(subject_id=subject_id)
    if term_id:
        q = q.filter_by(term_id=term_id)
    return jsonify(many.dump(q.all()))

@bp.post("/")
@jwt_required()
@roles_required("admin", "staff")
def create_offering():
    obj = schema.load(request.get_json())
    db.session.add(obj)
    db.session.commit()
    return jsonify(schema.dump(obj)), 201

@bp.put("/<uuid:offering_id>")
@jwt_required()
@roles_required("admin", "staff")
def update_offering(offering_id):
    o = CourseOffering.query.get_or_404(offering_id)
    obj = schema.load(request.get_json(), instance=o, partial=True)
    db.session.commit()
    return jsonify(schema.dump(obj))

@bp.delete("/<uuid:offering_id>")
@jwt_required()
@roles_required("admin", "staff")
def delete_offering(offering_id):
    o = CourseOffering.query.get_or_404(offering_id)
    db.session.delete(o)
    db.session.commit()
    return jsonify({"deleted": True})
