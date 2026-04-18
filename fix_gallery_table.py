#!/usr/bin/env python3
"""
Script to fix the gallery_images table structure
"""

import mysql.connector
from mysql.connector import Error

def get_db_connection():
    """Get database connection"""
    try:
        connection = mysql.connector.connect(
            host='localhost',
            database='wanaag_travel',
            user='root',
            password=''
        )
        return connection
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        return None

def fix_gallery_table():
    """Fix the gallery_images table structure"""
    connection = get_db_connection()
    if not connection:
        print("❌ Could not connect to database")
        return False
    
    try:
        cursor = connection.cursor()
        
        # Check if table exists
        cursor.execute("SHOW TABLES LIKE 'gallery_images'")
        table_exists = cursor.fetchone()
        
        if table_exists:
            print("✅ gallery_images table exists")
            
            # Check current structure
            cursor.execute("DESCRIBE gallery_images")
            columns = cursor.fetchall()
            column_names = [col[0] for col in columns]
            print(f"Current columns: {column_names}")
            
            # Add missing columns if they don't exist
            if 'category' not in column_names:
                print("Adding category column...")
                cursor.execute("ALTER TABLE gallery_images ADD COLUMN category VARCHAR(100) DEFAULT 'travel'")
                print("✅ Added category column")
            
            if 'featured' not in column_names:
                print("Adding featured column...")
                cursor.execute("ALTER TABLE gallery_images ADD COLUMN featured TINYINT(1) DEFAULT 0")
                print("✅ Added featured column")
            
            connection.commit()
            print("✅ Gallery table structure updated successfully")
            
        else:
            print("❌ gallery_images table does not exist")
            # Create the table
            cursor.execute("""
                CREATE TABLE gallery_images (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    filename VARCHAR(255) NOT NULL,
                    original_name VARCHAR(255) NOT NULL,
                    file_path VARCHAR(500) NOT NULL,
                    alt_text VARCHAR(255) DEFAULT '',
                    description TEXT DEFAULT '',
                    uploaded_by INT,
                    category VARCHAR(100) DEFAULT 'travel',
                    featured TINYINT(1) DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            connection.commit()
            print("✅ Created gallery_images table")
        
        cursor.close()
        connection.close()
        return True
        
    except Error as e:
        print(f"❌ Error fixing gallery table: {e}")
        return False

if __name__ == "__main__":
    print("🔧 Fixing gallery_images table structure...")
    success = fix_gallery_table()
    if success:
        print("✅ Gallery table fix completed successfully!")
    else:
        print("❌ Gallery table fix failed!")
