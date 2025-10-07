"""Dining and cafeteria management endpoints."""
from datetime import datetime

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from marshmallow import fields
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema, auto_field

from lms_models import (
    db,
    CafMenuItem,
    CafOrder,
    CafOrderItem,
    UserDietaryPreference,
    DietaryTag,
    DeliveryOption,
    menuitem_dietary,
)
from .roles_guard import roles_required


bp = Blueprint("cafeteria", __name__, url_prefix="/api/cafeteria")


class CafMenuItemSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = CafMenuItem
        include_fk = True
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)


class CafOrderItemSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = CafOrderItem
        include_fk = True
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)


class CafOrderSchema(SQLAlchemyAutoSchema):
    delivery_option = fields.Method("_option", deserialize="load_option")

    class Meta:
        model = CafOrder
        include_fk = True
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)

    def _option(self, obj):
        return obj.delivery_option.value if isinstance(obj.delivery_option, DeliveryOption) else obj.delivery_option

    def load_option(self, value):  # pragma: no cover
        return DeliveryOption(value)


class UserDietaryPreferenceSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = UserDietaryPreference
        include_fk = True
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)


menu_schema = CafMenuItemSchema()
menu_many = CafMenuItemSchema(many=True)
order_schema = CafOrderSchema()
order_many = CafOrderSchema(many=True)
order_item_schema = CafOrderItemSchema()
order_item_many = CafOrderItemSchema(many=True)
diet_schema = UserDietaryPreferenceSchema()


def _current_user_id() -> str | None:
    try:
        return get_jwt().get("sub")
    except Exception:
        return None


@bp.get("/menu")
def list_menu():
    q = CafMenuItem.query
    school_id = request.args.get("school_id")
    if school_id:
        q = q.filter_by(school_id=school_id)
    active = request.args.get("active")
    if active is not None:
        q = q.filter_by(active=active.lower() == "true")
    tag = request.args.get("dietary")
    if tag:
        try:
            enum_tag = DietaryTag(tag)
        except Exception:
            return jsonify({"error": "invalid dietary tag"}), 400
        q = q.join(menuitem_dietary, menuitem_dietary.c.menu_item_id == CafMenuItem.id).filter(menuitem_dietary.c.tag == enum_tag)
    return jsonify(menu_many.dump(q.order_by(CafMenuItem.name).all()))


@bp.post("/menu")
@jwt_required()
@roles_required("admin", "staff")
def create_menu_item():
    obj = menu_schema.load(request.get_json())
    db.session.add(obj)
    db.session.commit()
    return jsonify(menu_schema.dump(obj)), 201


@bp.get("/orders")
@jwt_required(optional=True)
def list_orders():
    q = CafOrder.query
    user_id = request.args.get("user_id") or _current_user_id()
    if user_id:
        q = q.filter_by(user_id=user_id)
    status = request.args.get("status")
    if status:
        q = q.filter_by(status=status)
    return jsonify(order_many.dump(q.order_by(CafOrder.created_at.desc()).all()))


@bp.post("/orders")
@jwt_required()
def create_order():
    payload = request.get_json() or {}
    sub_id = _current_user_id()
    if sub_id and not payload.get("user_id"):
        payload["user_id"] = sub_id
    if payload.get("delivery_option"):
        try:
            DeliveryOption(payload["delivery_option"])
        except Exception:
            return jsonify({"error": "invalid delivery_option"}), 400
    obj = order_schema.load(payload)
    db.session.add(obj)
    db.session.commit()
    return jsonify(order_schema.dump(obj)), 201


@bp.post("/orders/<uuid:order_id>/items")
@jwt_required()
def add_order_item(order_id):
    CafOrder.query.get_or_404(order_id)
    payload = request.get_json() or {}
    payload["order_id"] = str(order_id)
    obj = order_item_schema.load(payload)
    db.session.add(obj)
    db.session.commit()
    return jsonify(order_item_schema.dump(obj)), 201


@bp.get("/orders/<uuid:order_id>/items")
@jwt_required(optional=True)
def list_order_items(order_id):
    CafOrder.query.get_or_404(order_id)
    q = CafOrderItem.query.filter_by(order_id=order_id)
    return jsonify(order_item_many.dump(q.all()))


@bp.patch("/orders/<uuid:order_id>")
@jwt_required()
def update_order(order_id):
    obj = CafOrder.query.get_or_404(order_id)
    data = request.get_json() or {}
    if "status" in data:
        obj.status = data["status"]
    if "scheduled_for" in data:
        obj.scheduled_for = datetime.fromisoformat(data["scheduled_for"])
    if "delivery_option" in data:
        try:
            obj.delivery_option = DeliveryOption(data["delivery_option"])
        except Exception:
            return jsonify({"error": "invalid delivery_option"}), 400
    if "delivery_location" in data:
        obj.delivery_location = data["delivery_location"]
    db.session.commit()
    return jsonify(order_schema.dump(obj))


@bp.get("/dietary")
@jwt_required(optional=True)
def get_dietary_preferences():
    user_id = request.args.get("user_id") or _current_user_id()
    if not user_id:
        return jsonify({"error": "user_id required"}), 400
    pref = UserDietaryPreference.query.filter_by(user_id=user_id).first()
    return jsonify(diet_schema.dump(pref) if pref else {})


@bp.post("/dietary")
@jwt_required()
def set_dietary_preferences():
    payload = request.get_json() or {}
    sub_id = _current_user_id()
    if sub_id and not payload.get("user_id"):
        payload["user_id"] = sub_id
    existing = UserDietaryPreference.query.filter_by(user_id=payload.get("user_id")).first()
    if existing:
        obj = diet_schema.load(payload, instance=existing, partial=True)
    else:
        obj = diet_schema.load(payload)
        db.session.add(obj)
    db.session.commit()
    return jsonify(diet_schema.dump(obj))

