#!/usr/bin/env python3
"""
Create SQLAlchemy-managed tables (db.create_all).

Run once after setting DATABASE_URL (or DB_* variables), e.g. on Namecheap via SSH:

  cd /path/to/your/app
  source venv/bin/activate   # if you use a virtualenv
  python create_db_tables.py

Then run the app (or call /api/init-database) so ensure_default_user() can add data.
"""
from dotenv import load_dotenv

load_dotenv()

from App import app, db  # noqa: E402


def main():
    with app.app_context():
        db.create_all()
    print("Done: db.create_all() finished (tables created if they did not exist).")


if __name__ == "__main__":
    main()
