"""Study plans, adaptive resources, and smart reminders."""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema, auto_field

from lms_models import db, StudyPlan, StudyTask, AdaptiveResource, SmartReminder


bp = Blueprint("study_plans", __name__, url_prefix="/api/study-plans")


class StudyPlanSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = StudyPlan
        include_fk = True
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)


class StudyTaskSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = StudyTask
        include_fk = True
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)


class AdaptiveResourceSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = AdaptiveResource
        include_fk = True
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)


class SmartReminderSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = SmartReminder
        include_fk = True
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)


plan_schema = StudyPlanSchema()
plan_many = StudyPlanSchema(many=True)
task_schema = StudyTaskSchema()
task_many = StudyTaskSchema(many=True)
resource_schema = AdaptiveResourceSchema()
resource_many = AdaptiveResourceSchema(many=True)
reminder_schema = SmartReminderSchema()
reminder_many = SmartReminderSchema(many=True)


def _current_student() -> str | None:
    try:
        return get_jwt().get("sub")
    except Exception:
        return None


@bp.get("/")
@jwt_required(optional=True)
def list_plans():
    q = StudyPlan.query
    student_id = request.args.get("student_id") or _current_student()
    if student_id:
        q = q.filter_by(student_id=student_id)
    return jsonify(plan_many.dump(q.order_by(StudyPlan.id.desc()).all()))


@bp.post("/")
@jwt_required()
def create_plan():
    payload = request.get_json() or {}
    sub_id = _current_student()
    if sub_id and not payload.get("student_id"):
        payload["student_id"] = sub_id
    obj = plan_schema.load(payload)
    db.session.add(obj)
    db.session.commit()
    return jsonify(plan_schema.dump(obj)), 201


@bp.get("/<uuid:plan_id>/tasks")
@jwt_required(optional=True)
def list_tasks(plan_id):
    StudyPlan.query.get_or_404(plan_id)
    q = StudyTask.query.filter_by(plan_id=plan_id)
    status = request.args.get("status")
    if status:
        q = q.filter_by(status=status)
    return jsonify(task_many.dump(q.order_by(StudyTask.due_at).all()))


@bp.post("/<uuid:plan_id>/tasks")
@jwt_required()
def create_task(plan_id):
    StudyPlan.query.get_or_404(plan_id)
    payload = request.get_json() or {}
    payload["plan_id"] = str(plan_id)
    obj = task_schema.load(payload)
    db.session.add(obj)
    db.session.commit()
    return jsonify(task_schema.dump(obj)), 201


@bp.patch("/tasks/<uuid:task_id>")
@jwt_required()
def update_task(task_id):
    obj = StudyTask.query.get_or_404(task_id)
    obj = task_schema.load(request.get_json() or {}, instance=obj, partial=True)
    db.session.commit()
    return jsonify(task_schema.dump(obj))


@bp.get("/tasks/<uuid:task_id>/resources")
def list_resources_for_task(task_id):
    StudyTask.query.get_or_404(task_id)
    q = AdaptiveResource.query.filter_by(study_task_id=task_id)
    return jsonify(resource_many.dump(q.all()))


@bp.post("/tasks/<uuid:task_id>/resources")
@jwt_required()
def create_resource(task_id):
    StudyTask.query.get_or_404(task_id)
    payload = request.get_json() or {}
    payload["study_task_id"] = str(task_id)
    obj = resource_schema.load(payload)
    db.session.add(obj)
    db.session.commit()
    return jsonify(resource_schema.dump(obj)), 201


@bp.get("/reminders")
@jwt_required(optional=True)
def list_reminders():
    q = SmartReminder.query
    user_id = request.args.get("user_id") or _current_student()
    if user_id:
        q = q.filter_by(user_id=user_id)
    scope = request.args.get("scope")
    if scope:
        q = q.filter_by(scope=scope)
    return jsonify(reminder_many.dump(q.order_by(SmartReminder.send_at).all()))


@bp.post("/reminders")
@jwt_required()
def create_reminder():
    payload = request.get_json() or {}
    sub_id = _current_student()
    if sub_id and not payload.get("user_id"):
        payload["user_id"] = sub_id
    obj = reminder_schema.load(payload)
    db.session.add(obj)
    db.session.commit()
    return jsonify(reminder_schema.dump(obj)), 201

