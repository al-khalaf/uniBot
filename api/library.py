"""Library system integration endpoints."""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema, auto_field

from lms_models import db, LibraryAction


bp = Blueprint("library", __name__, url_prefix="/api/library")


class LibraryActionSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = LibraryAction
        include_fk = True
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)


action_schema = LibraryActionSchema()
action_many = LibraryActionSchema(many=True)


def _current_user_id() -> str | None:
    try:
        return get_jwt().get("sub")
    except Exception:
        return None


@bp.get("/")
@jwt_required(optional=True)
def list_actions():
    q = LibraryAction.query
    user_id = request.args.get("user_id") or _current_user_id()
    if user_id:
        q = q.filter_by(user_id=user_id)
    action = request.args.get("action")
    if action:
        q = q.filter_by(action=action)
    return jsonify(action_many.dump(q.order_by(LibraryAction.created_at.desc()).all()))


@bp.post("/")
@jwt_required(optional=True)
def log_action():
    payload = request.get_json() or {}
    sub_id = _current_user_id()
    if sub_id and not payload.get("user_id"):
        payload["user_id"] = sub_id
    obj = action_schema.load(payload)
    db.session.add(obj)
    db.session.commit()
    return jsonify(action_schema.dump(obj)), 201
