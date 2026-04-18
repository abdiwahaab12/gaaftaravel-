"""
SQLAlchemy models for tables managed with db.create_all().

The rest of the app still uses raw SQL via PyMySQL connections for many features.
These models cover core auth tables so Flask-SQLAlchemy can create them on a fresh DB.
Additional tables are created by ensure_* helpers in App.py (CREATE TABLE IF NOT EXISTS).
"""
from extensions import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(255))
    last_name = db.Column(db.String(255))
    photo_url = db.Column(db.String(500))
    role = db.Column(db.String(50), default="user")
    is_active = db.Column(db.Boolean, default=True)
    dashboard_access = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, server_default=db.func.current_timestamp())
    updated_at = db.Column(
        db.DateTime,
        server_default=db.func.current_timestamp(),
        onupdate=db.func.current_timestamp(),
    )


class PasswordResetCode(db.Model):
    __tablename__ = "password_reset_codes"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, nullable=False)
    email = db.Column(db.String(255), nullable=False)
    reset_code = db.Column(db.String(255), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.current_timestamp())


class UserModulePermission(db.Model):
    __tablename__ = "user_module_permissions"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, nullable=False)
    module_name = db.Column(db.String(100), nullable=False)
    has_access = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, server_default=db.func.current_timestamp())
    updated_at = db.Column(
        db.DateTime,
        server_default=db.func.current_timestamp(),
        onupdate=db.func.current_timestamp(),
    )

    __table_args__ = (db.UniqueConstraint("user_id", "module_name", name="unique_user_module"),)
