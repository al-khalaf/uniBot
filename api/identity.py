"""Student identity and access management endpoints."""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema, auto_field

from lms_models import db, StudentIDCard, AccessPermission, ParkingPermit
from .roles_guard import roles_required


bp = Blueprint("identity", __name__, url_prefix="/api/identity")


class StudentIDCardSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = StudentIDCard
        include_fk = True
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)


class AccessPermissionSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = AccessPermission
        include_fk = True
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)


class ParkingPermitSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = ParkingPermit
        include_fk = True
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)


id_schema = StudentIDCardSchema()
id_many = StudentIDCardSchema(many=True)
access_schema = AccessPermissionSchema()
access_many = AccessPermissionSchema(many=True)
permit_schema = ParkingPermitSchema()
permit_many = ParkingPermitSchema(many=True)


@bp.get("/cards")
@jwt_required(optional=True)
def list_cards():
    q = StudentIDCard.query
    user_id = request.args.get("user_id")
    if user_id:
        q = q.filter_by(user_id=user_id)
    return jsonify(id_many.dump(q.order_by(StudentIDCard.issued_at.desc()).all()))


@bp.post("/cards")
@jwt_required()
@roles_required("admin", "staff")
def create_card():
    obj = id_schema.load(request.get_json())
    db.session.add(obj)
    db.session.commit()
    return jsonify(id_schema.dump(obj)), 201


@bp.patch("/cards/<uuid:card_id>")
@jwt_required()
@roles_required("admin", "staff")
def update_card(card_id):
    obj = StudentIDCard.query.get_or_404(card_id)
    obj = id_schema.load(request.get_json() or {}, instance=obj, partial=True)
    db.session.commit()
    return jsonify(id_schema.dump(obj))


@bp.get("/access")
@jwt_required(optional=True)
def list_access_permissions():
    q = AccessPermission.query
    user_id = request.args.get("user_id")
    if user_id:
        q = q.filter_by(user_id=user_id)
    area = request.args.get("area")
    if area:
        q = q.filter(AccessPermission.area.ilike(f"%{area}%"))
    return jsonify(access_many.dump(q.all()))


@bp.post("/access")
@jwt_required()
@roles_required("admin", "staff")
def grant_access():
    obj = access_schema.load(request.get_json())
    db.session.add(obj)
    db.session.commit()
    return jsonify(access_schema.dump(obj)), 201


@bp.delete("/access/<uuid:access_id>")
@jwt_required()
@roles_required("admin", "staff")
def revoke_access(access_id):
    obj = AccessPermission.query.get_or_404(access_id)
    db.session.delete(obj)
    db.session.commit()
    return jsonify({"deleted": True})


@bp.get("/parking")
@jwt_required(optional=True)
def list_parking_permits():
    q = ParkingPermit.query
    user_id = request.args.get("user_id")
    if user_id:
        q = q.filter_by(user_id=user_id)
    status = request.args.get("status")
    if status:
        q = q.filter_by(status=status)
    return jsonify(permit_many.dump(q.order_by(ParkingPermit.issued_at.desc()).all()))


@bp.post("/parking")
@jwt_required()
@roles_required("admin", "staff")
def create_parking_permit():
    obj = permit_schema.load(request.get_json())
    db.session.add(obj)
    db.session.commit()
    return jsonify(permit_schema.dump(obj)), 201


@bp.patch("/parking/<uuid:permit_id>")
@jwt_required()
@roles_required("admin", "staff")
def update_parking_permit(permit_id):
    obj = ParkingPermit.query.get_or_404(permit_id)
    obj = permit_schema.load(request.get_json() or {}, instance=obj, partial=True)
    db.session.commit()
    return jsonify(permit_schema.dump(obj))

