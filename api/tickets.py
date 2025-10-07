"""Facility and IT ticketing endpoints."""
from datetime import datetime

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from marshmallow import fields
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema, auto_field

from lms_models import db, Ticket, TicketStatus


bp = Blueprint("tickets", __name__, url_prefix="/api/tickets")


class TicketSchema(SQLAlchemyAutoSchema):
    status = fields.Method("_status", deserialize="load_status")

    class Meta:
        model = Ticket
        include_fk = True
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)

    def _status(self, obj):
        return obj.status.value if isinstance(obj.status, TicketStatus) else obj.status

    def load_status(self, value):  # pragma: no cover
        return TicketStatus(value)


ticket_schema = TicketSchema()
ticket_many = TicketSchema(many=True)


def _current_user_id() -> str | None:
    try:
        return get_jwt().get("sub")
    except Exception:
        return None


@bp.get("/")
@jwt_required(optional=True)
def list_tickets():
    q = Ticket.query
    school_id = request.args.get("school_id")
    if school_id:
        q = q.filter_by(school_id=school_id)
    status = request.args.get("status")
    if status:
        try:
            q = q.filter(Ticket.status == TicketStatus(status))
        except Exception:
            return jsonify({"error": "invalid status"}), 400
    created_by = request.args.get("created_by") or _current_user_id()
    if created_by:
        q = q.filter_by(created_by=created_by)
    return jsonify(ticket_many.dump(q.order_by(Ticket.created_at.desc()).all()))


@bp.post("/")
@jwt_required(optional=True)
def create_ticket():
    payload = request.get_json() or {}
    sub_id = _current_user_id()
    if sub_id and not payload.get("created_by"):
        payload["created_by"] = sub_id
    obj = ticket_schema.load(payload)
    if not obj.school_id:
        return jsonify({"error": "school_id required"}), 400
    db.session.add(obj)
    db.session.commit()
    return jsonify(ticket_schema.dump(obj)), 201


@bp.patch("/<uuid:ticket_id>")
@jwt_required()
def update_ticket(ticket_id):
    obj = Ticket.query.get_or_404(ticket_id)
    data = request.get_json() or {}
    if "status" in data:
        try:
            obj.status = TicketStatus(data["status"])
        except Exception:
            return jsonify({"error": "invalid status"}), 400
    for field in ["title", "description", "location"]:
        if field in data:
            setattr(obj, field, data[field])
    db.session.commit()
    return jsonify(ticket_schema.dump(obj))

