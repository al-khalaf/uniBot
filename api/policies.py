"""Policies, FAQs, and regulations search endpoints."""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema, auto_field

from lms_models import db, FAQ, Policy, Topic
from .roles_guard import roles_required


bp = Blueprint("policies", __name__, url_prefix="/api/policies")


class FAQSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = FAQ
        include_fk = True
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)


class PolicySchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Policy
        include_fk = True
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)


class TopicSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Topic
        include_fk = True
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)


faq_schema = FAQSchema()
faq_many = FAQSchema(many=True)
policy_schema = PolicySchema()
policy_many = PolicySchema(many=True)
topic_schema = TopicSchema()
topic_many = TopicSchema(many=True)


@bp.get("/faqs")
def list_faqs():
    q = FAQ.query
    school_id = request.args.get("school_id")
    if school_id:
        q = q.filter_by(school_id=school_id)
    language = request.args.get("language")
    if language:
        q = q.filter_by(language=language)
    q_text = request.args.get("q")
    if q_text:
        q = q.filter(FAQ.question.ilike(f"%{q_text}%"))
    return jsonify(faq_many.dump(q.order_by(FAQ.question).all()))


@bp.post("/faqs")
@jwt_required()
@roles_required("admin", "staff")
def create_faq():
    obj = faq_schema.load(request.get_json())
    db.session.add(obj)
    db.session.commit()
    return jsonify(faq_schema.dump(obj)), 201


@bp.get("/policies")
def list_policies():
    q = Policy.query
    school_id = request.args.get("school_id")
    if school_id:
        q = q.filter_by(school_id=school_id)
    language = request.args.get("language")
    if language:
        q = q.filter_by(language=language)
    return jsonify(policy_many.dump(q.order_by(Policy.effective_date.desc().nullslast()).all()))


@bp.post("/policies")
@jwt_required()
@roles_required("admin", "staff")
def create_policy():
    obj = policy_schema.load(request.get_json())
    db.session.add(obj)
    db.session.commit()
    return jsonify(policy_schema.dump(obj)), 201


@bp.get("/topics")
def list_topics():
    q = Topic.query
    school_id = request.args.get("school_id")
    if school_id:
        q = q.filter_by(school_id=school_id)
    return jsonify(topic_many.dump(q.order_by(Topic.name).all()))

