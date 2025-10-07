"""Leaderboards and gamification endpoints."""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema, auto_field

from lms_models import db, Leaderboard, LeaderboardEntry
from .roles_guard import roles_required


bp = Blueprint("leaderboards", __name__, url_prefix="/api/leaderboards")


class LeaderboardSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Leaderboard
        include_fk = True
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)


class LeaderboardEntrySchema(SQLAlchemyAutoSchema):
    class Meta:
        model = LeaderboardEntry
        include_fk = True
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)


board_schema = LeaderboardSchema()
board_many = LeaderboardSchema(many=True)
entry_schema = LeaderboardEntrySchema()
entry_many = LeaderboardEntrySchema(many=True)


@bp.get("/")
def list_leaderboards():
    q = Leaderboard.query
    school_id = request.args.get("school_id")
    if school_id:
        q = q.filter_by(school_id=school_id)
    metric = request.args.get("metric")
    if metric:
        q = q.filter_by(metric=metric)
    return jsonify(board_many.dump(q.order_by(Leaderboard.name).all()))


@bp.post("/")
@jwt_required()
@roles_required("admin", "staff")
def create_leaderboard():
    obj = board_schema.load(request.get_json())
    db.session.add(obj)
    db.session.commit()
    return jsonify(board_schema.dump(obj)), 201


@bp.get("/<uuid:leaderboard_id>/entries")
def list_entries(leaderboard_id):
    Leaderboard.query.get_or_404(leaderboard_id)
    q = LeaderboardEntry.query.filter_by(leaderboard_id=leaderboard_id)
    return jsonify(entry_many.dump(q.order_by(LeaderboardEntry.rank.asc().nullslast(), LeaderboardEntry.score.desc()).all()))


@bp.post("/<uuid:leaderboard_id>/entries")
@jwt_required()
@roles_required("admin", "staff")
def create_entry(leaderboard_id):
    Leaderboard.query.get_or_404(leaderboard_id)
    payload = request.get_json() or {}
    payload["leaderboard_id"] = str(leaderboard_id)
    obj = entry_schema.load(payload)
    db.session.add(obj)
    db.session.commit()
    return jsonify(entry_schema.dump(obj)), 201


@bp.patch("/entries/<uuid:entry_id>")
@jwt_required()
@roles_required("admin", "staff")
def update_entry(entry_id):
    obj = LeaderboardEntry.query.get_or_404(entry_id)
    obj = entry_schema.load(request.get_json() or {}, instance=obj, partial=True)
    db.session.commit()
    return jsonify(entry_schema.dump(obj))

