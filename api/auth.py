from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt
from lms_models import db, User, School, Role, user_roles
from uuid import UUID

bp = Blueprint("auth", __name__)

def _user_to_claims(u: User):
    # load role list from association table
    rows = db.session.execute(
        user_roles.select().where(user_roles.c.user_id == u.id)
    ).mappings().all()
    roles = [r["role"].value if hasattr(r["role"], "value") else r["role"] for r in rows]
    return {"sub": str(u.id), "school_id": str(u.school_id), "email": u.email, "roles": roles}

@bp.post("/register")
def register():
    data = request.get_json() or {}
    required = ["school_id", "email", "full_name", "password"]
    missing = [k for k in required if not data.get(k)]
    if missing:
        return jsonify({"error": f"Missing: {', '.join(missing)}"}), 400

    try:
        school_id = UUID(data["school_id"])
    except Exception:
        return jsonify({"error": "Invalid school_id"}), 400

    if not School.query.get(school_id):
        return jsonify({"error": "School not found"}), 404

    if User.query.filter_by(email=data["email"]).first():
        return jsonify({"error": "Email already registered"}), 409

    u = User(school_id=school_id, email=data["email"], full_name=data["full_name"], is_active=True)
    u.set_password(data["password"])
    db.session.add(u); db.session.flush()

    # optional initial role
    role = data.get("role")
    if role:
        try:
            role_enum = Role(role)
            db.session.execute(user_roles.insert().values(user_id=u.id, role=role_enum))
        except Exception:
            return jsonify({"error": "Invalid role"}), 400

    db.session.commit()
    return jsonify({"id": str(u.id)}), 201

@bp.post("/login")
def login():
    data = request.get_json() or {}
    email = data.get("email"); password = data.get("password")
    if not email or not password:
        return jsonify({"error": "email and password required"}), 400

    u = User.query.filter_by(email=email, is_active=True).first()
    if not u or not u.check_password(password):
        return jsonify({"error": "invalid credentials"}), 401

    claims = _user_to_claims(u)
    token = create_access_token(identity=str(u.id), additional_claims=claims)
    return jsonify({"access_token": token, "user": claims})

@bp.post("/assign-role")
@jwt_required()
def assign_role():
    claims = get_jwt()
    if "admin" not in claims.get("roles", []):
        return jsonify({"error": "admin role required"}), 403

    data = request.get_json() or {}
    try:
        user_id = UUID(data.get("user_id", ""))
        role_enum = Role(data.get("role"))
    except Exception:
        return jsonify({"error": "invalid user_id or role"}), 400

    if not User.query.get(user_id):
        return jsonify({"error": "user not found"}), 404

    exists = db.session.execute(
        user_roles.select().where(user_roles.c.user_id == user_id, user_roles.c.role == role_enum)
    ).first()
    if not exists:
        db.session.execute(user_roles.insert().values(user_id=user_id, role=role_enum))
        db.session.commit()

    return jsonify({"ok": True})
