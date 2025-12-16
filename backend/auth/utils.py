import bcrypt
import jwt
from datetime import datetime, timedelta
from flask import current_app, request
from functools import wraps
from bson import ObjectId
from db import users_col


def hash_password(plain: str) -> bytes:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt())


def check_password(plain: str, hashed: bytes) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed)


def generate_token(user_id: str) -> str:
    payload = {
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(hours=12),
    }
    return jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm="HS256")


def decode_token(token: str):
    return jwt.decode(
        token, current_app.config["SECRET_KEY"], algorithms=["HS256"]
    )


def auth_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return {"error": "Missing token"}, 401

        token = auth_header.split(" ", 1)[1]
        try:
            data = decode_token(token)
            user = users_col.find_one({"_id": ObjectId(data["user_id"])})
            if not user:
                return {"error": "User not found"}, 401
            request.user = user
        except Exception as e:
            return {"error": f"Invalid token: {str(e)}"}, 401

        return fn(*args, **kwargs)

    return wrapper
