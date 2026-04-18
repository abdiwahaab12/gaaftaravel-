#!/usr/bin/env python3
"""
Database Initialization Script (legacy helper).

Uses the same DATABASE_URL / DB_* settings as App.py.
Prefer: `python create_db_tables.py` then start the app (or POST /api/init-database).

This script still creates core tables via raw SQL and the Super Admin user.
"""

from werkzeug.security import generate_password_hash
import logging
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_db_connection():
    """Same MySQL connection as the main app (Flask-SQLAlchemy engine)."""
    from App import get_db_connection as app_get_db_connection

    return app_get_db_connection()


# Default Super Admin credentials
DEFAULT_EMAIL = 'admin@wanaagtravel.com'
DEFAULT_USERNAME = 'admin'
DEFAULT_PASSWORD = 'Admin@123'

def create_users_table():
    """Create users table with proper MySQL syntax"""
    db = None
    cursor = None
    try:
        db = get_db_connection()
        cursor = db.cursor()
        
        # Create users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(255) NOT NULL,
                email VARCHAR(255) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                first_name VARCHAR(255) DEFAULT NULL,
                last_name VARCHAR(255) DEFAULT NULL,
                photo_url VARCHAR(500) DEFAULT NULL,
                role VARCHAR(50) DEFAULT 'user',
                is_active TINYINT(1) DEFAULT 1,
                dashboard_access TINYINT(1) DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """)
        
        # Create user module permissions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_module_permissions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                module_name VARCHAR(100) NOT NULL,
                has_access TINYINT(1) DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY unique_user_module (user_id, module_name)
            )
        """)
        
        db.commit()
        logger.info("✅ Tables created successfully!")
        
    except Exception as e:
        logger.error(f"Error creating tables: {e}")
        if db:
            db.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()

def create_super_admin():
    """Create Super Admin user"""
    db = None
    cursor = None
    try:
        db = get_db_connection()
        cursor = db.cursor()
        
        # Check if Super Admin already exists
        cursor.execute("SELECT id FROM users WHERE email = %s", (DEFAULT_EMAIL,))
        existing_user = cursor.fetchone()
        
        if existing_user:
            logger.info("✅ Super Admin user already exists!")
            user_id = existing_user['id']
        else:
            # Create Super Admin user
            hashed_password = generate_password_hash(DEFAULT_PASSWORD)
            cursor.execute("""
                INSERT INTO users (username, email, password_hash, first_name, last_name, role, is_active, dashboard_access)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (DEFAULT_USERNAME, DEFAULT_EMAIL, hashed_password, 'Super', 'Admin', 'super_admin', 1, 1))
            
            user_id = cursor.lastrowid
            logger.info("✅ Super Admin user created successfully!")
        
        # Set up module permissions for Super Admin
        cursor.execute("DELETE FROM user_module_permissions WHERE user_id=%s", (user_id,))
        modules = [
            ('tickets', True),
            ('visas', True),
            ('cargo', True),
            ('transport', True),
            ('financial', True)
        ]
        
        for module_name, has_access in modules:
            cursor.execute(
                "INSERT INTO user_module_permissions (user_id, module_name, has_access) VALUES (%s, %s, %s)",
                (user_id, module_name, has_access)
            )
        
        db.commit()
        logger.info("✅ Super Admin permissions set successfully!")
        
    except Exception as e:
        logger.error(f"Error creating Super Admin: {e}")
        if db:
            db.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()

def verify_setup():
    """Verify the setup is correct"""
    db = None
    cursor = None
    try:
        db = get_db_connection()
        cursor = db.cursor()
        
        # Check if Super Admin exists
        cursor.execute("""
            SELECT id, username, email, role, is_active, dashboard_access
            FROM users 
            WHERE email = %s AND role = 'super_admin'
        """, (DEFAULT_EMAIL,))
        super_admin = cursor.fetchone()
        
        if not super_admin:
            logger.error("❌ Super Admin account not found!")
            return False
        
        if not super_admin['is_active']:
            logger.error("❌ Super Admin account is inactive!")
            return False
        
        # Check module permissions
        cursor.execute("""
            SELECT module_name, has_access
            FROM user_module_permissions 
            WHERE user_id = %s
        """, (super_admin['id'],))
        permissions = cursor.fetchall()
        
        required_modules = ['tickets', 'visas', 'cargo', 'transport', 'financial']
        permission_dict = {p['module_name']: p['has_access'] for p in permissions}
        
        missing_permissions = []
        for module in required_modules:
            if module not in permission_dict or not permission_dict[module]:
                missing_permissions.append(module)
        
        if missing_permissions:
            logger.error(f"❌ Super Admin missing permissions for: {missing_permissions}")
            return False
        
        logger.info(f"✅ Super Admin verified: {super_admin['email']} with full permissions")
        return True
        
    except Exception as e:
        logger.error(f"Error verifying setup: {e}")
        return False
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()

def main():
    """Main initialization function"""
    try:
        logger.info("🚀 Starting database initialization...")
        
        # Step 1: Create tables
        logger.info("📋 Creating database tables...")
        create_users_table()
        
        # Step 2: Create Super Admin
        logger.info("👤 Creating Super Admin user...")
        create_super_admin()
        
        # Step 3: Verify setup
        logger.info("🔍 Verifying setup...")
        if verify_setup():
            logger.info("🎉 Database initialization completed successfully!")
            logger.info(f"📧 Super Admin Email: {DEFAULT_EMAIL}")
            logger.info(f"🔑 Super Admin Password: {DEFAULT_PASSWORD}")
            logger.info("🌐 You can now login to the admin dashboard!")
        else:
            logger.error("❌ Database initialization verification failed!")
            
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        logger.error("Please check your MySQL connection and try again.")

if __name__ == '__main__':
    main()
