"""Plugin marketplace management endpoints."""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema, auto_field

from lms_models import db, PluginIntegration, PluginInstallation, PluginStatus
from .roles_guard import roles_required


bp = Blueprint("plugins", __name__, url_prefix="/api/plugins")


class PluginIntegrationSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = PluginIntegration
        include_fk = True
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)


class PluginInstallationSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = PluginInstallation
        include_fk = True
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)


integration_schema = PluginIntegrationSchema()
integration_many = PluginIntegrationSchema(many=True)
installation_schema = PluginInstallationSchema()
installation_many = PluginInstallationSchema(many=True)


@bp.get("/catalog")
def list_catalog():
    q = PluginIntegration.query
    category = request.args.get("category")
    if category:
        q = q.filter_by(category=category)
    return jsonify(integration_many.dump(q.order_by(PluginIntegration.name).all()))


@bp.post("/catalog")
@jwt_required()
@roles_required("admin")
def create_plugin():
    obj = integration_schema.load(request.get_json())
    db.session.add(obj)
    db.session.commit()
    return jsonify(integration_schema.dump(obj)), 201


@bp.get("/installations")
@jwt_required(optional=True)
def list_installations():
    q = PluginInstallation.query
    school_id = request.args.get("school_id")
    if school_id:
        q = q.filter_by(school_id=school_id)
    status = request.args.get("status")
    if status:
        try:
            q = q.filter(PluginInstallation.status == PluginStatus(status))
        except Exception:
            return jsonify({"error": "invalid status"}), 400
    return jsonify(installation_many.dump(q.all()))


@bp.post("/installations")
@jwt_required()
@roles_required("admin")
def install_plugin():
    obj = installation_schema.load(request.get_json())
    db.session.add(obj)
    db.session.commit()
    return jsonify(installation_schema.dump(obj)), 201


@bp.patch("/installations/<uuid:installation_id>")
@jwt_required()
@roles_required("admin")
def update_installation(installation_id):
    obj = PluginInstallation.query.get_or_404(installation_id)
    payload = request.get_json() or {}
    if "status" in payload:
        try:
            obj.status = PluginStatus(payload["status"])
        except Exception:
            return jsonify({"error": "invalid status"}), 400
    if "settings" in payload:
        obj.settings = payload["settings"]
    db.session.commit()
    return jsonify(installation_schema.dump(obj))

