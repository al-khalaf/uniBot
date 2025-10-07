"""Operational analytics and dashboards."""
from datetime import date

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from sqlalchemy import func

from lms_models import (
    db,
    DashboardMetric,
    UsageTrend,
    FAQ,
    Ticket,
    Notification,
    Enrollment,
    CourseOffering,
    Subject,
)
from .roles_guard import roles_required


bp = Blueprint("analytics", __name__, url_prefix="/api/analytics")


@bp.get("/metrics")
@jwt_required(optional=True)
def list_metrics():
    q = DashboardMetric.query
    school_id = request.args.get("school_id")
    if school_id:
        q = q.filter_by(school_id=school_id)
    metric = request.args.get("metric")
    if metric:
        q = q.filter_by(name=metric)
    return jsonify([m for m in map(lambda row: row.to_dict() if hasattr(row, "to_dict") else {
        "id": str(row.id),
        "name": row.name,
        "value": row.value,
        "captured_at": row.captured_at.isoformat(),
        "dimensions": row.dimensions,
    }, q.order_by(DashboardMetric.captured_at.desc()).all())])


@bp.post("/metrics")
@jwt_required()
@roles_required("admin", "staff")
def create_metric():
    payload = request.get_json() or {}
    metric = DashboardMetric(**payload)
    db.session.add(metric)
    db.session.commit()
    return jsonify({
        "id": str(metric.id),
        "name": metric.name,
        "value": metric.value,
        "captured_at": metric.captured_at.isoformat(),
        "dimensions": metric.dimensions,
    }), 201


@bp.get("/usage-trends")
@jwt_required(optional=True)
def list_usage_trends():
    q = UsageTrend.query
    school_id = request.args.get("school_id")
    if school_id:
        q = q.filter_by(school_id=school_id)
    metric = request.args.get("metric")
    if metric:
        q = q.filter_by(metric=metric)
    return jsonify([
        {
            "id": str(row.id),
            "metric": row.metric,
            "period_start": row.period_start.isoformat(),
            "period_end": row.period_end.isoformat(),
            "value": row.value,
            "notes": row.notes,
        }
        for row in q.order_by(UsageTrend.period_start.desc()).all()
    ])


@bp.get("/insights/faq-topics")
@jwt_required(optional=True)
def faq_frequency():
    school_id = request.args.get("school_id")
    q = db.session.query(FAQ.language, func.count(FAQ.id)).group_by(FAQ.language)
    if school_id:
        q = q.filter(FAQ.school_id == school_id)
    data = [{"language": lang, "count": count} for lang, count in q.all()]
    return jsonify(data)


@bp.get("/insights/open-tickets")
@jwt_required(optional=True)
def ticket_backlog():
    school_id = request.args.get("school_id")
    q = db.session.query(Ticket.status, func.count(Ticket.id)).group_by(Ticket.status)
    if school_id:
        q = q.filter(Ticket.school_id == school_id)
    data = [{"status": status.value if hasattr(status, "value") else status, "count": count} for status, count in q.all()]
    return jsonify(data)


@bp.get("/insights/notification-volume")
@jwt_required(optional=True)
def notification_volume():
    school_id = request.args.get("school_id")
    start = request.args.get("start")
    q = db.session.query(func.date(Notification.sent_at), func.count(Notification.id)).group_by(func.date(Notification.sent_at))
    if school_id:
        q = q.filter(Notification.school_id == school_id)
    if start:
        q = q.filter(Notification.sent_at >= start)
    rows = q.order_by(func.date(Notification.sent_at)).all()
    data = [{"date": (d.isoformat() if isinstance(d, date) else str(d)), "count": count} for d, count in rows]
    return jsonify(data)


@bp.get("/insights/enrollment-summary")
@jwt_required(optional=True)
def enrollment_summary():
    school_id = request.args.get("school_id")
    q = db.session.query(func.count(Enrollment.id))
    if school_id:
        q = (
            q.join(CourseOffering, CourseOffering.id == Enrollment.course_offering_id)
            .join(Subject, Subject.id == CourseOffering.subject_id)
            .filter(Subject.school_id == school_id)
        )
    total = q.scalar() or 0
    return jsonify({"total_enrollments": total})

