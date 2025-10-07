"""Lab equipment and resource booking endpoints."""
from datetime import datetime

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema, auto_field

from lms_models import db, Resource, ResourceBooking, BookingStatus
from .roles_guard import roles_required


bp = Blueprint("resources", __name__, url_prefix="/api/resources")


class ResourceSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Resource
        include_fk = True
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)


class ResourceBookingSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = ResourceBooking
        include_fk = True
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)


resource_schema = ResourceSchema()
resource_many = ResourceSchema(many=True)
booking_schema = ResourceBookingSchema()
booking_many = ResourceBookingSchema(many=True)


@bp.get("/")
def list_resources():
    q = Resource.query
    school_id = request.args.get("school_id")
    if school_id:
        q = q.filter_by(school_id=school_id)
    resource_type = request.args.get("type")
    if resource_type:
        q = q.filter_by(resource_type=resource_type)
    return jsonify(resource_many.dump(q.order_by(Resource.name).all()))


@bp.post("/")
@jwt_required()
@roles_required("admin", "staff")
def create_resource():
    obj = resource_schema.load(request.get_json())
    db.session.add(obj)
    db.session.commit()
    return jsonify(resource_schema.dump(obj)), 201


@bp.get("/<uuid:resource_id>/bookings")
@jwt_required(optional=True)
def list_bookings(resource_id):
    Resource.query.get_or_404(resource_id)
    q = ResourceBooking.query.filter_by(resource_id=resource_id)
    status = request.args.get("status")
    if status:
        try:
            q = q.filter(ResourceBooking.status == BookingStatus(status))
        except Exception:
            return jsonify({"error": "invalid status"}), 400
    return jsonify(booking_many.dump(q.order_by(ResourceBooking.starts_at).all()))


@bp.post("/<uuid:resource_id>/bookings")
@jwt_required()
def create_booking(resource_id):
    Resource.query.get_or_404(resource_id)
    payload = request.get_json() or {}
    payload["resource_id"] = str(resource_id)
    obj = booking_schema.load(payload)

    # quick overlap check
    overlaps = (
        ResourceBooking.query.filter_by(resource_id=resource_id)
        .filter(ResourceBooking.status != BookingStatus.CANCELLED)
        .filter(ResourceBooking.ends_at > obj.starts_at)
        .filter(ResourceBooking.starts_at < obj.ends_at)
        .first()
    )
    if overlaps:
        return jsonify({"error": "resource already booked during that window"}), 409

    db.session.add(obj)
    db.session.commit()
    return jsonify(booking_schema.dump(obj)), 201


@bp.patch("/bookings/<uuid:booking_id>")
@jwt_required()
def update_booking(booking_id):
    obj = ResourceBooking.query.get_or_404(booking_id)
    data = request.get_json() or {}
    if "status" in data:
        try:
            obj.status = BookingStatus(data["status"])
        except Exception:
            return jsonify({"error": "invalid status"}), 400
    if "starts_at" in data:
        obj.starts_at = datetime.fromisoformat(data["starts_at"])
    if "ends_at" in data:
        obj.ends_at = datetime.fromisoformat(data["ends_at"])
    if "notes" in data:
        obj.notes = data["notes"]
    db.session.commit()
    return jsonify(booking_schema.dump(obj))

