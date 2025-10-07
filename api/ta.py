"""Teaching assistant dashboards: queues and student requests."""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema, auto_field

from lms_models import db, TeachingAssistantQueue, TeachingAssistantTicket
from .roles_guard import roles_required


bp = Blueprint("ta", __name__, url_prefix="/api/ta")


class TeachingAssistantQueueSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = TeachingAssistantQueue
        include_fk = True
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)


class TeachingAssistantTicketSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = TeachingAssistantTicket
        include_fk = True
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)


queue_schema = TeachingAssistantQueueSchema()
queue_many = TeachingAssistantQueueSchema(many=True)
ticket_schema = TeachingAssistantTicketSchema()
ticket_many = TeachingAssistantTicketSchema(many=True)


@bp.get("/queues")
@jwt_required(optional=True)
def list_queues():
    q = TeachingAssistantQueue.query
    course_id = request.args.get("course_offering_id")
    if course_id:
        q = q.filter_by(course_offering_id=course_id)
    return jsonify(queue_many.dump(q.all()))


@bp.post("/queues")
@jwt_required()
@roles_required("admin", "staff", "teacher")
def create_queue():
    obj = queue_schema.load(request.get_json())
    db.session.add(obj)
    db.session.commit()
    return jsonify(queue_schema.dump(obj)), 201


@bp.get("/queues/<uuid:queue_id>/tickets")
@jwt_required(optional=True)
def list_tickets(queue_id):
    TeachingAssistantQueue.query.get_or_404(queue_id)
    q = TeachingAssistantTicket.query.filter_by(queue_id=queue_id)
    status = request.args.get("status")
    if status:
        q = q.filter_by(status=status)
    return jsonify(ticket_many.dump(q.order_by(TeachingAssistantTicket.created_at).all()))


@bp.post("/queues/<uuid:queue_id>/tickets")
@jwt_required()
def create_ticket(queue_id):
    TeachingAssistantQueue.query.get_or_404(queue_id)
    payload = request.get_json() or {}
    payload["queue_id"] = str(queue_id)
    obj = ticket_schema.load(payload)
    db.session.add(obj)
    db.session.commit()
    return jsonify(ticket_schema.dump(obj)), 201


@bp.patch("/tickets/<uuid:ticket_id>")
@jwt_required()
def update_ticket(ticket_id):
    obj = TeachingAssistantTicket.query.get_or_404(ticket_id)
    obj = ticket_schema.load(request.get_json() or {}, instance=obj, partial=True)
    db.session.commit()
    return jsonify(ticket_schema.dump(obj))

