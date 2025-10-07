from functools import wraps
from flask import jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt

def roles_required(*roles):
    def outer(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()
            user_roles = set(claims.get("roles", []))
            needed = set(roles)
            if not (user_roles & needed):
                return jsonify({"error": f"requires one of roles: {', '.join(roles)}"}), 403
            return fn(*args, **kwargs)
        return wrapper
    return outer
