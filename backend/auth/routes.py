from flask import Blueprint, request
from db import users_col
from .utils import hash_password, check_password, generate_token

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.post("/signup")
def signup():
    data = request.get_json(force=True)
    email = data.get("email", "").strip().lower()
    name = data.get("name", "").strip()
    password = data.get("password", "")

    if not email or not password:
        return {"error": "Email and password required"}, 400

    if users_col.find_one({"email": email}):
        return {"error": "User already exists"}, 400

    pwd_hash = hash_password(password)
    res = users_col.insert_one(
        {
            "email": email,
            "name": name,
            "password_hash": pwd_hash,
        }
    )
    token = generate_token(str(res.inserted_id))
    return {"message": "Signup successful", "token": token}, 201


@auth_bp.post("/login")
def login():
    data = request.get_json(force=True)
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    user = users_col.find_one({"email": email})
    if not user or not check_password(password, user["password_hash"]):
        return {"error": "Invalid credentials"}, 401

    token = generate_token(str(user["_id"]))
    return {"message": "Login ok", "token": token}, 200
