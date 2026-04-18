"""
Flask-SQLAlchemy extension (shared app instance).
Import `db` from here so models and App.py use the same object.
"""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
