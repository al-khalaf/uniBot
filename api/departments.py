"""Directory, departments, and campus services endpoints."""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from marshmallow import fields
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema, auto_field

from lms_models import (
    db,
    Department,
    DepartmentService,
    DepartmentLocation,
)
from .roles_guard import roles_required


bp = Blueprint("departments", __name__, url_prefix="/api/departments")


class DepartmentLocationSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = DepartmentLocation
        include_fk = True
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)


class DepartmentServiceSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = DepartmentService
        include_fk = True
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)


class DepartmentSchema(SQLAlchemyAutoSchema):
    services = fields.Nested(DepartmentServiceSchema, many=True, dump_only=True)
    locations = fields.Nested(DepartmentLocationSchema, many=True, dump_only=True)

    class Meta:
        model = Department
        include_fk = True
        include_relationships = True
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)


department_schema = DepartmentSchema()
department_many = DepartmentSchema(many=True)
service_schema = DepartmentServiceSchema()
service_many = DepartmentServiceSchema(many=True)
location_schema = DepartmentLocationSchema()
location_many = DepartmentLocationSchema(many=True)


@bp.get("/")
def list_departments():
    q = Department.query
    school_id = request.args.get("school_id")
    if school_id:
        q = q.filter_by(school_id=school_id)
    return jsonify(department_many.dump(q.order_by(Department.name).all()))


@bp.post("/")
@jwt_required()
@roles_required("admin", "staff")
def create_department():
    obj = department_schema.load(request.get_json())
    db.session.add(obj)
    db.session.commit()
    return jsonify(department_schema.dump(obj)), 201


@bp.get("/<uuid:department_id>")
def get_department(department_id):
    obj = Department.query.get_or_404(department_id)
    return jsonify(department_schema.dump(obj))


@bp.put("/<uuid:department_id>")
@jwt_required()
@roles_required("admin", "staff")
def update_department(department_id):
    obj = Department.query.get_or_404(department_id)
    obj = department_schema.load(request.get_json() or {}, instance=obj, partial=True)
    db.session.commit()
    return jsonify(department_schema.dump(obj))


@bp.delete("/<uuid:department_id>")
@jwt_required()
@roles_required("admin", "staff")
def delete_department(department_id):
    obj = Department.query.get_or_404(department_id)
    db.session.delete(obj)
    db.session.commit()
    return jsonify({"deleted": True})


@bp.post("/<uuid:department_id>/services")
@jwt_required()
@roles_required("admin", "staff")
def add_service(department_id):
    Department.query.get_or_404(department_id)
    payload = request.get_json() or {}
    payload["department_id"] = str(department_id)
    obj = service_schema.load(payload)
    db.session.add(obj)
    db.session.commit()
    return jsonify(service_schema.dump(obj)), 201


@bp.get("/<uuid:department_id>/services")
def list_services(department_id):
    Department.query.get_or_404(department_id)
    services = DepartmentService.query.filter_by(department_id=department_id).all()
    return jsonify(service_many.dump(services))


@bp.post("/<uuid:department_id>/locations")
@jwt_required()
@roles_required("admin", "staff")
def add_location(department_id):
    Department.query.get_or_404(department_id)
    payload = request.get_json() or {}
    payload["department_id"] = str(department_id)
    obj = location_schema.load(payload)
    db.session.add(obj)
    db.session.commit()
    return jsonify(location_schema.dump(obj)), 201


@bp.get("/<uuid:department_id>/locations")
def list_locations(department_id):
    Department.query.get_or_404(department_id)
    items = DepartmentLocation.query.filter_by(department_id=department_id).all()
    return jsonify(location_many.dump(items))

