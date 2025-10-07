"""Notifications, broadcasts, and subscriptions endpoints."""
from datetime import datetime

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from marshmallow import fields
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema, auto_field

from lms_models import (
    db,
    Notification,
    NotificationSubscription,
    NotificationChannel,
)
from .roles_guard import roles_required


bp = Blueprint("notifications", __name__, url_prefix="/api/notifications")


class NotificationSchema(SQLAlchemyAutoSchema):
    channel = fields.Method("_channel", deserialize="load_channel")

    class Meta:
        model = Notification
        include_fk = True
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)

    def _channel(self, obj):
        return obj.channel.value if isinstance(obj.channel, NotificationChannel) else obj.channel

    def load_channel(self, value):  # pragma: no cover
        return NotificationChannel(value)


class NotificationSubscriptionSchema(SQLAlchemyAutoSchema):
    channel = fields.Method("_channel", deserialize="load_channel")

    class Meta:
        model = NotificationSubscription
        include_fk = True
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)

    def _channel(self, obj):
        return obj.channel.value if isinstance(obj.channel, NotificationChannel) else obj.channel

    def load_channel(self, value):  # pragma: no cover
        return NotificationChannel(value)


notif_schema = NotificationSchema()
notif_many = NotificationSchema(many=True)
sub_schema = NotificationSubscriptionSchema()
sub_many = NotificationSubscriptionSchema(many=True)


def _current_user_id() -> str | None:
    try:
        return get_jwt().get("sub")
    except Exception:
        return None


@bp.get("/")
@jwt_required(optional=True)
def list_notifications():
    q = Notification.query
    school_id = request.args.get("school_id")
    if school_id:
        q = q.filter_by(school_id=school_id)
    user_id = request.args.get("user_id") or _current_user_id()
    if user_id:
        q = q.filter((Notification.user_id == user_id) | (Notification.user_id == None))  # noqa: E711
    channel = request.args.get("channel")
    if channel:
        try:
            q = q.filter(Notification.channel == NotificationChannel(channel))
        except Exception:
            return jsonify({"error": "invalid channel"}), 400
    return jsonify(notif_many.dump(q.order_by(Notification.sent_at.desc().nullslast()).all()))


@bp.post("/")
@jwt_required()
@roles_required("admin", "staff")
def create_notification():
    payload = request.get_json() or {}
    if payload.get("sent_at") is None:
        payload["sent_at"] = datetime.utcnow().isoformat()
    obj = notif_schema.load(payload)
    db.session.add(obj)
    db.session.commit()
    return jsonify(notif_schema.dump(obj)), 201


@bp.get("/subscriptions")
@jwt_required(optional=True)
def list_subscriptions():
    q = NotificationSubscription.query
    user_id = request.args.get("user_id") or _current_user_id()
    if user_id:
        q = q.filter_by(user_id=user_id)
    channel = request.args.get("channel")
    if channel:
        try:
            q = q.filter(NotificationSubscription.channel == NotificationChannel(channel))
        except Exception:
            return jsonify({"error": "invalid channel"}), 400
    return jsonify(sub_many.dump(q.all()))


@bp.post("/subscriptions")
@jwt_required(optional=True)
def create_subscription():
    payload = request.get_json() or {}
    sub_id = _current_user_id()
    if sub_id and not payload.get("user_id"):
        payload["user_id"] = sub_id
    obj = sub_schema.load(payload)
    db.session.add(obj)
    db.session.commit()
    return jsonify(sub_schema.dump(obj)), 201


@bp.delete("/subscriptions/<uuid:subscription_id>")
@jwt_required(optional=True)
def delete_subscription(subscription_id):
    obj = NotificationSubscription.query.get_or_404(subscription_id)
    db.session.delete(obj)
    db.session.commit()
    return jsonify({"deleted": True})

