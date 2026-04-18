from flask import Flask, request, jsonify, render_template, redirect, send_file, send_from_directory, url_for
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import JWTManager, jwt_required, get_jwt_identity, create_access_token, set_access_cookies, unset_access_cookies
import jwt
from werkzeug.utils import secure_filename
import os
from datetime import timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ---------------- FLASK CONFIG ----------------
app = Flask(__name__, static_folder='static', template_folder='templates')

# Debug: Print static folder path
print(f"Flask static folder: {app.static_folder}")
print(f"Current working directory: {os.getcwd()}")
print(f"Static folder exists: {os.path.exists(app.static_folder)}")
if os.path.exists(app.static_folder):
    print(f"Static folder contents: {os.listdir(app.static_folder)}")
    uploads_path = os.path.join(app.static_folder, 'uploads')
    print(f"Uploads folder exists: {os.path.exists(uploads_path)}")
    if os.path.exists(uploads_path):
        print(f"Uploads folder contents: {os.listdir(uploads_path)}")
CORS(app, supports_credentials=True, resources={r"/*": {"origins": "*"}}, allow_headers=["Content-Type", "Authorization"], expose_headers=["Authorization"]) 

# JWT configuration
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'wanaagtravel123')  # Use environment variable
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=12)  # Extend session validity
app.config['JWT_TOKEN_LOCATION'] = ['cookies', 'headers']
app.config['JWT_HEADER_NAME'] = 'Authorization'
app.config['JWT_HEADER_TYPE'] = 'Bearer'
app.config['JWT_COOKIE_SECURE'] = os.getenv('FLASK_ENV') == 'production'  # Secure cookies in production
app.config['JWT_COOKIE_CSRF_PROTECT'] = os.getenv('FLASK_ENV') == 'production'  # CSRF protection in production
app.config['JWT_ACCESS_COOKIE_NAME'] = 'token'
app.config['JWT_COOKIE_DOMAIN'] = None  # Allow cookies for all domains
app.config['JWT_COOKIE_PATH'] = '/'  # Set cookie path to root
app.config['JWT_COOKIE_SAMESITE'] = 'Lax'  # Allow cross-site requests
jwt = JWTManager(app)

# Token blacklist for logout
blacklisted_tokens = set()

# ---------------- AUTHENTICATION HELPERS ----------------
def get_jwt_token_from_request():
    """Extract JWT token from request cookies or headers"""
    token = None
    
    # Check cookies first
    if 'token' in request.cookies:
        token = request.cookies['token']
    # Check Authorization header
    elif 'Authorization' in request.headers:
        auth_header = request.headers['Authorization']
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]  # Remove 'Bearer ' prefix
    
    return token

def verify_jwt_token(token):
    """Verify JWT token and return user_id if valid"""
    if not token:
        return None
    
    # Check if token is blacklisted
    if token in blacklisted_tokens:
        print("Token is blacklisted")
        return None
    
    try:
        from flask_jwt_extended import decode_token
        decoded_token = decode_token(token)
        user_id = decoded_token.get('sub')
        return user_id
    except Exception as e:
        print(f"Token verification failed: {e}")
        return None

# ---------------- AUTOMATIC RECEIVABLE LOAN RECORDING ----------------
@app.route('/api/test-db', methods=['GET'])
@jwt_required()
def test_database():
    """Test database connection and table structure"""
    try:
        db = get_db_connection()
        cursor = db.cursor()
        
        # Test tickets table
        cursor.execute("SELECT COUNT(*) as count FROM tickets")
        ticket_count = cursor.fetchone()['count']
        
        # Test receivable_loans table
        cursor.execute("SELECT COUNT(*) as count FROM receivable_loans")
        receivable_count = cursor.fetchone()['count']
        
        # Test receivable_loans table structure
        cursor.execute("DESCRIBE receivable_loans")
        receivable_structure = cursor.fetchall()
        
        # Test a simple insert to receivable_loans table
        test_insert_success = False
        try:
            cursor.execute("""
                INSERT INTO receivable_loans (issued_date, borrower, amount, due_date, status, notes, created_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, ('2024-01-01', 'Test Customer', 100.00, '2024-01-01', 'Unpaid', 'Test entry', 1))
            cursor.execute("DELETE FROM receivable_loans WHERE notes = 'Test entry'")
            test_insert_success = True
        except Exception as insert_error:
            print(f"Test insert failed: {insert_error}")
        
        cursor.close()
        db.close()
        
        return jsonify({
            'success': True,
            'ticket_count': ticket_count,
            'receivable_count': receivable_count,
            'receivable_structure': receivable_structure,
            'test_insert_success': test_insert_success
        })
    except Exception as e:
        return jsonify({'error': 'Database test failed', 'details': str(e)}), 500

@app.route('/api/test-ticket-update/<int:ticket_id>', methods=['GET'])
@jwt_required()
def test_ticket_update(ticket_id):
    """Test ticket update functionality"""
    try:
        db = get_db_connection()
        cursor = db.cursor()
        
        # Get current ticket data
        cursor.execute("SELECT * FROM tickets WHERE id = %s", (ticket_id,))
        ticket = cursor.fetchone()
        
        if not ticket:
            return jsonify({'error': 'Ticket not found'}), 404
        
        # Test receivable loan creation
        test_success = False
        try:
            create_receivable_loan_for_unpaid_transaction(
                db, cursor, 1, 'Ticket', ticket_id, 'Test Customer', 100.00, 
                '2024-01-01', 'Test notes'
            )
            test_success = True
        except Exception as e:
            print(f"Receivable loan test failed: {e}")
        
        cursor.close()
        db.close()
        
        return jsonify({
            'success': True,
            'ticket_found': True,
            'receivable_loan_test': test_success
        })
    except Exception as e:
        return jsonify({'error': 'Test failed', 'details': str(e)}), 500

@app.route('/api/debug-ticket-update', methods=['POST'])
@jwt_required()
def debug_ticket_update():
    """Debug ticket update with minimal data"""
    try:
        data = request.get_json()
        ticket_id = data.get('ticket_id')
        status = data.get('status', 'Unpaid')
        
        print(f"DEBUG: Updating ticket {ticket_id} to status {status}")
        
        db = get_db_connection()
        cursor = db.cursor()
        
        # Simple update without receivable loan logic
        cursor.execute("""
            UPDATE tickets SET payment_status = %s, updated_at = NOW()
            WHERE id = %s
        """, (status, ticket_id))
        
        db.commit()
        cursor.close()
        db.close()
        
        return jsonify({'message': 'Debug update successful'})
        
    except Exception as e:
        print(f"DEBUG ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Debug update failed', 'details': str(e)}), 500

@app.route('/api/test-simple-update/<int:ticket_id>', methods=['GET'])
@jwt_required()
def test_simple_update(ticket_id):
    """Test simple ticket update without any complex logic"""
    try:
        print(f"TEST: Simple update for ticket {ticket_id}")
        
        db = get_db_connection()
        cursor = db.cursor()
        
        # Check if ticket exists
        cursor.execute("SELECT id, payment_status FROM tickets WHERE id = %s", (ticket_id,))
        ticket = cursor.fetchone()
        
        if not ticket:
            return jsonify({'error': 'Ticket not found'}), 404
        
        print(f"TEST: Found ticket {ticket_id} with status {ticket[1]}")
        
        # Simple status update
        cursor.execute("""
            UPDATE tickets SET payment_status = 'Unpaid', updated_at = NOW()
            WHERE id = %s
        """, (ticket_id,))
        
        db.commit()
        cursor.close()
        db.close()
        
        return jsonify({'message': 'Simple update successful', 'ticket_id': ticket_id})
        
    except Exception as e:
        print(f"TEST ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Test failed', 'details': str(e)}), 500

@app.route('/api/test-db-connection', methods=['GET'])
@jwt_required()
def test_db_connection():
    """Test basic database connection and operations"""
    try:
        print("TEST: Testing database connection")
        
        db = get_db_connection()
        cursor = db.cursor()
        
        # Test basic query
        cursor.execute("SELECT 1 as test")
        result = cursor.fetchone()
        print(f"TEST: Basic query result: {result}")
        
        # Test tickets table
        cursor.execute("SELECT COUNT(*) as count FROM tickets")
        count = cursor.fetchone()['count']
        print(f"TEST: Tickets count: {count}")
        
        # Test specific ticket
        cursor.execute("SELECT id, payment_status FROM tickets WHERE id = 15")
        ticket = cursor.fetchone()
        print(f"TEST: Ticket 15: {ticket}")
        
        cursor.close()
        db.close()
        
        return jsonify({
            'success': True,
            'basic_query': result[0] if result else None,
            'tickets_count': count,
            'ticket_15': ticket
        })
        
    except Exception as e:
        print(f"DB CONNECTION TEST ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Database connection test failed', 'details': str(e)}), 500

def test_payment_statuses():
    """Test function to verify payment status logic works correctly"""
    print("Testing payment status logic:")
    
    # Test cases
    test_cases = [
        {"total_paid": 0, "net_cost": 1000, "expected": "Unpaid"},
        {"total_paid": 500, "net_cost": 1000, "expected": "Partially Paid"},
        {"total_paid": 1000, "net_cost": 1000, "expected": "Paid"},
        {"total_paid": 1200, "net_cost": 1000, "expected": "Paid"},
    ]
    
    for case in test_cases:
        total_paid = case["total_paid"]
        net_cost = case["net_cost"]
        expected = case["expected"]
        
        if total_paid >= net_cost:
            result = "Paid"
        elif total_paid > 0:
            result = "Partially Paid"
        else:
            result = "Unpaid"
            
        status = "✓" if result == expected else "✗"
        print(f"{status} Paid: {total_paid}, Net: {net_cost} → {result} (expected: {expected})")
    
    print("Payment status logic test completed.")

def ensure_receivable_loans_table_exists(db, cursor):
    """Ensure the receivable_loans table exists with correct structure"""
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS receivable_loans (
                id INT AUTO_INCREMENT PRIMARY KEY,
                issued_date DATE,
                borrower VARCHAR(255),
                amount DECIMAL(10,2),
                paid DECIMAL(10,2) DEFAULT 0.00,
                commission DECIMAL(10,2) DEFAULT 0.00,
                remaining_payment DECIMAL(10,2) DEFAULT 0.00,
                source VARCHAR(50) DEFAULT NULL,
                source_id INT DEFAULT NULL,
                due_date DATE,
                status VARCHAR(50),
                notes TEXT,
                created_by INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """)
        # Backfill columns for older schemas.
        for ddl in [
            "ALTER TABLE receivable_loans ADD COLUMN paid DECIMAL(10,2) DEFAULT 0.00",
            "ALTER TABLE receivable_loans ADD COLUMN commission DECIMAL(10,2) DEFAULT 0.00",
            "ALTER TABLE receivable_loans ADD COLUMN remaining_payment DECIMAL(10,2) DEFAULT 0.00",
            "ALTER TABLE receivable_loans ADD COLUMN source VARCHAR(50) DEFAULT NULL",
            "ALTER TABLE receivable_loans ADD COLUMN source_id INT DEFAULT NULL",
        ]:
            try:
                cursor.execute(ddl)
            except Exception:
                pass
        print("Receivable loans table ensured to exist")
        return True
    except Exception as e:
        print(f"Error ensuring receivable_loans table exists: {e}")
        return False

def create_receivable_loan_for_unpaid_transaction(
    db,
    cursor,
    user_id,
    transaction_type,
    transaction_id,
    customer_name,
    amount,
    due_date=None,
    notes="",
    commission=0.0,
    paid=0.0,
    source=None,
    source_id=None,
):
    """Automatically create a receivable loan entry for unpaid transactions"""
    try:
        print(f"Creating receivable loan: Type={transaction_type}, ID={transaction_id}, Customer={customer_name}, Amount={amount}")
        
        # Ensure table exists first
        if not ensure_receivable_loans_table_exists(db, cursor):
            print("Failed to ensure receivable_loans table exists")
            return False
        
        # Check what columns actually exist in receivable_loans table
        cursor.execute("DESCRIBE receivable_loans")
        columns = [row['Field'] for row in cursor.fetchall()]
        print(f"DEBUG: receivable_loans table columns: {columns}")
        
        # Check if receivable loan already exists for this transaction
        cursor.execute("SELECT id FROM receivable_loans WHERE notes LIKE %s", (f"%{transaction_type} ID {transaction_id}%",))
        existing_loan = cursor.fetchone()
        
        if not existing_loan:
            # Create receivable loan for unpaid amount - use appropriate columns
            print(f"Inserting receivable loan with values: due_date={due_date}, customer_name={customer_name}, amount={amount}")
            
            try:
                borrower_col = 'borrower_name' if 'borrower_name' in columns else 'borrower'
                normalized_source = (source or str(transaction_type).lower()).lower()
                normalized_source_id = source_id if source_id is not None else transaction_id
                amount_value = float(amount or 0)
                paid_value = float(paid or 0)
                commission_value = float(commission or 0)
                remaining_value = round(amount_value - paid_value - commission_value, 2)
                if remaining_value < 0:
                    remaining_value = 0.0

                insert_cols = ['issued_date', borrower_col, 'amount', 'due_date', 'status', 'notes', 'created_by']
                insert_vals = [due_date, customer_name, amount_value, due_date, 'Unpaid', f"{transaction_type} ID {transaction_id}. {notes}", user_id]

                if 'source' in columns:
                    insert_cols.append('source')
                    insert_vals.append(normalized_source)
                if 'source_id' in columns:
                    insert_cols.append('source_id')
                    insert_vals.append(normalized_source_id)
                if 'commission' in columns:
                    insert_cols.append('commission')
                    insert_vals.append(commission_value)
                if 'paid' in columns:
                    insert_cols.append('paid')
                    insert_vals.append(paid_value)
                if 'remaining_payment' in columns:
                    insert_cols.append('remaining_payment')
                    insert_vals.append(remaining_value)

                placeholders = ', '.join(['%s'] * len(insert_cols))
                sql = f"INSERT INTO receivable_loans ({', '.join(insert_cols)}) VALUES ({placeholders})"
                cursor.execute(sql, tuple(insert_vals))
                print(f"Receivable loan created successfully for {transaction_type} ID {transaction_id}")
                return True
            except Exception as insert_error:
                print(f"Failed to insert receivable loan: {insert_error}")
                # Try minimal structure
                cursor.execute(
                    """
                    INSERT INTO receivable_loans (borrower, amount, status, notes)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (customer_name, amount, 'Unpaid', f"{transaction_type} ID {transaction_id}. {notes}")
                )
                print(f"Receivable loan created successfully with minimal structure for {transaction_type} ID {transaction_id}")
                return True
        else:
            print(f"Receivable loan already exists for {transaction_type} ID {transaction_id}")
            return False
    except Exception as e:
        print(f"Error creating receivable loan: {e}")
        import traceback
        traceback.print_exc()
        return False

def sync_receivable_loan_for_transaction(
    db,
    cursor,
    user_id,
    transaction_type,
    transaction_id,
    customer_name,
    total_amount,
    amount_paid,
    due_date=None,
    notes="",
):
    """
    Keep receivable_loans in sync with booking transaction payment state.
    - Paid (remaining <= 0): remove from receivable_loans
    - Partial/Unpaid: upsert receivable row with current remaining amount
    """
    try:
        if not ensure_receivable_loans_table_exists(db, cursor):
            return False

        cursor.execute("DESCRIBE receivable_loans")
        columns = [row['Field'] if isinstance(row, dict) else row[0] for row in cursor.fetchall()]
        borrower_col = 'borrower_name' if 'borrower_name' in columns else 'borrower'
        has_source = 'source' in columns and 'source_id' in columns

        normalized_source = str(transaction_type or '').lower()
        total_value = float(total_amount or 0)
        paid_value = float(amount_paid or 0)
        remaining_value = round(max(total_value - paid_value, 0), 2)

        if has_source:
            cursor.execute(
                "SELECT id FROM receivable_loans WHERE source = %s AND source_id = %s ORDER BY id DESC LIMIT 1",
                (normalized_source, transaction_id),
            )
            existing = cursor.fetchone()
        else:
            cursor.execute(
                "SELECT id FROM receivable_loans WHERE notes LIKE %s ORDER BY id DESC LIMIT 1",
                (f"%{transaction_type} ID {transaction_id}%",),
            )
            existing = cursor.fetchone()

        existing_id = None
        if existing:
            if isinstance(existing, dict):
                existing_id = existing.get('id')
            elif isinstance(existing, (list, tuple)) and existing:
                existing_id = existing[0]

        # Fully paid: remove from receivable list immediately
        if remaining_value <= 0:
            if has_source:
                cursor.execute(
                    "DELETE FROM receivable_loans WHERE source = %s AND source_id = %s",
                    (normalized_source, transaction_id),
                )
            else:
                cursor.execute(
                    "DELETE FROM receivable_loans WHERE notes LIKE %s",
                    (f"%{transaction_type} ID {transaction_id}%",),
                )
            return True

        status_value = 'Partially Paid' if paid_value > 0 else 'Unpaid'
        notes_value = f"{transaction_type} ID {transaction_id}. {notes or ''}".strip()
        issued_value = due_date

        if existing_id:
            update_parts = [
                f"{borrower_col} = %s",
                "amount = %s",
                "due_date = %s",
                "status = %s",
                "notes = %s",
            ]
            update_vals = [customer_name, remaining_value, due_date, status_value, notes_value]

            if 'paid' in columns:
                update_parts.append("paid = %s")
                update_vals.append(paid_value)
            if 'remaining_payment' in columns:
                update_parts.append("remaining_payment = %s")
                update_vals.append(remaining_value)
            if has_source:
                update_parts.append("source = %s")
                update_parts.append("source_id = %s")
                update_vals.extend([normalized_source, transaction_id])

            update_vals.append(existing_id)
            cursor.execute(
                f"UPDATE receivable_loans SET {', '.join(update_parts)} WHERE id = %s",
                tuple(update_vals),
            )
        else:
            insert_cols = ['issued_date', borrower_col, 'amount', 'due_date', 'status', 'notes', 'created_by']
            insert_vals = [issued_value, customer_name, remaining_value, due_date, status_value, notes_value, user_id]

            if 'paid' in columns:
                insert_cols.append('paid')
                insert_vals.append(paid_value)
            if 'remaining_payment' in columns:
                insert_cols.append('remaining_payment')
                insert_vals.append(remaining_value)
            if has_source:
                insert_cols.append('source')
                insert_cols.append('source_id')
                insert_vals.extend([normalized_source, transaction_id])

            placeholders = ', '.join(['%s'] * len(insert_cols))
            cursor.execute(
                f"INSERT INTO receivable_loans ({', '.join(insert_cols)}) VALUES ({placeholders})",
                tuple(insert_vals),
            )

        return True
    except Exception as e:
        print(f"Error syncing receivable loan for {transaction_type} ID {transaction_id}: {e}")
        import traceback
        traceback.print_exc()
        return False

def update_receivable_loan_for_payment(db, cursor, user_id, transaction_type, transaction_id, old_status, new_status, amount_paid, total_amount):
    """Enhanced function to handle automatic movement between receivable and received loans"""
    try:
        print(f"Updating receivable loan: {transaction_type} ID {transaction_id}, Status: {old_status} -> {new_status}")
        
        # Find existing receivable loan for this transaction
        cursor.execute("SELECT id, amount, borrower_name, due_date FROM receivable_loans WHERE notes LIKE %s", (f"%{transaction_type} ID {transaction_id}%",))
        existing_loan = cursor.fetchone()
        
        if existing_loan:
            loan_id, loan_amount, borrower_name, due_date = existing_loan
            
            # If status changed from Unpaid/Partially Paid to Paid
            if old_status in ['Unpaid', 'Partially Paid'] and new_status == 'Paid':
                print(f"Moving loan {loan_id} from receivable to received loans")
                
                # Transfer to received_loans with proper data
                cursor.execute(
                    """
                    INSERT INTO received_loans (lender_name, loan_amount, loan_date, due_date, interest_rate, status, notes, created_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        borrower_name or f"{transaction_type} Customer", 
                        loan_amount, 
                        due_date or '2024-01-01', 
                        due_date or '2024-01-01', 
                        0.00, 
                        'Paid', 
                        f"Payment received for {transaction_type} ID {transaction_id}. Original loan amount: {loan_amount}",
                        user_id
                    )
                )
                
                # Delete from receivable_loans
                cursor.execute("DELETE FROM receivable_loans WHERE id = %s", (loan_id,))
                print(f"Successfully moved loan {loan_id} to received loans")
                return True
                
            # If status changed to Partially Paid, update the loan amount
            elif new_status == 'Partially Paid':
                remaining_amount = total_amount - amount_paid
                cursor.execute(
                    "UPDATE receivable_loans SET amount = %s, status = 'Partially Paid' WHERE id = %s",
                    (remaining_amount, loan_id)
                )
                print(f"Updated loan {loan_id} to Partially Paid with remaining amount: {remaining_amount}")
                return True
                
            # If status changed back to Unpaid, ensure it's in receivable loans
            elif new_status == 'Unpaid' and old_status in ['Paid', 'Partially Paid']:
                # Check if loan exists in received_loans and move it back
                cursor.execute("SELECT id FROM received_loans WHERE notes LIKE %s", (f"%{transaction_type} ID {transaction_id}%",))
                received_loan = cursor.fetchone()
                
                if received_loan:
                    # Move back to receivable_loans
                    cursor.execute("""
                        INSERT INTO receivable_loans (issued_date, borrower_name, amount, due_date, status, notes, created_by)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        due_date or '2024-01-01',
                        borrower_name or f"{transaction_type} Customer",
                        loan_amount,
                        due_date or '2024-01-01',
                        'Unpaid',
                        f"{transaction_type} ID {transaction_id}. {notes}",
                        user_id
                    ))
                    
                    # Delete from received_loans
                    cursor.execute("DELETE FROM received_loans WHERE id = %s", (received_loan[0],))
                    print(f"Moved loan back to receivable loans for {transaction_type} ID {transaction_id}")
                    return True
                
        return False
    except Exception as e:
        print(f"Error updating receivable loan: {e}")
        import traceback
        traceback.print_exc()
        return False

def sync_received_loans_from_paid_transactions(db, cursor):
    """
    Ensure Received Loans always includes fully paid transactions from core modules.
    This backfills any missed transfer events.
    """
    sync_sources = [
        {
            "type": "Ticket",
            "query": """
                SELECT id, names AS customer, COALESCE(total_paid, net_fare, 0) AS amount,
                       COALESCE(date_departure, date_issue) AS loan_date
                FROM tickets
                WHERE payment_status = 'Paid'
            """,
        },
        {
            "type": "Visa",
            "query": """
                SELECT id, customer_name AS customer, COALESCE(total_paid, net_cost + commission, 0) AS amount,
                       requested_date AS loan_date
                FROM visas
                WHERE payment_status = 'Paid'
            """,
        },
        {
            "type": "Cargo",
            "query": """
                SELECT id, customer_name AS customer, COALESCE(total_paid, net_cost + commission, 0) AS amount,
                       requested_date AS loan_date
                FROM cargo
                WHERE payment_status = 'Paid'
            """,
        },
        {
            "type": "Transport",
            "query": """
                SELECT id, customer_name AS customer, COALESCE(total_paid, cost + commission, 0) AS amount,
                       date AS loan_date
                FROM transport
                WHERE payment_status = 'Paid'
            """,
        },
    ]

    # Track manually removed auto-sync items so they do not reappear
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS received_loans_exclusions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            source_type VARCHAR(50) NOT NULL,
            source_id INT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY unique_source_item (source_type, source_id)
        )
    """)

    for src in sync_sources:
        cursor.execute(src["query"])
        rows = cursor.fetchall() or []
        for row in rows:
            tx_id = row["id"] if isinstance(row, dict) else row[0]
            customer = row["customer"] if isinstance(row, dict) else row[1]
            amount = float((row["amount"] if isinstance(row, dict) else row[2]) or 0)
            loan_date = (row["loan_date"] if isinstance(row, dict) else row[3]) or '2024-01-01'
            note_key = f"AUTO_SYNC {src['type']} ID {tx_id}"

            # Skip any source item explicitly excluded by user delete action
            cursor.execute(
                "SELECT id FROM received_loans_exclusions WHERE source_type = %s AND source_id = %s",
                (src['type'], tx_id),
            )
            if cursor.fetchone():
                continue

            cursor.execute("SELECT id FROM received_loans WHERE notes LIKE %s", (f"%{note_key}%",))
            if cursor.fetchone():
                continue

            cursor.execute("DESCRIBE received_loans")
            received_cols = [c["Field"] if isinstance(c, dict) else c[0] for c in cursor.fetchall()]

            if 'lender_name' in received_cols and 'loan_amount' in received_cols and 'loan_date' in received_cols:
                cursor.execute("""
                    INSERT INTO received_loans (lender_name, loan_amount, loan_date, due_date, interest_rate, status, notes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (customer, amount, loan_date, loan_date, 0.00, 'Paid', note_key))
            else:
                cursor.execute("""
                    INSERT INTO received_loans (lender, amount, received_date, status, notes)
                    VALUES (%s, %s, %s, %s, %s)
                """, (customer, amount, loan_date, 'Paid', note_key))

# ---------------- AUDIT LOGGING ----------------
def log_audit_event(user_id, action, resource, details=None, ip_address=None):
    """Log user activity for audit purposes"""
    db = None
    cursor = None
    try:
        db = get_db_connection()
        cursor = db.cursor()
        
        # Create audit_logs table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                action VARCHAR(100) NOT NULL,
                resource VARCHAR(100) NOT NULL,
                details TEXT,
                ip_address VARCHAR(45),
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        
        # Insert audit log entry
        cursor.execute("""
            INSERT INTO audit_logs (user_id, action, resource, details, ip_address)
            VALUES (%s, %s, %s, %s, %s)
        """, (user_id, action, resource, details, ip_address))
        
        db.commit()
        
    except Exception as e:
        logger.error(f"Failed to log audit event: {str(e)}")
        if db:
            db.rollback()
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()

def get_client_ip():
    """Get client IP address from request"""
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    elif request.headers.get('X-Real-IP'):
        return request.headers.get('X-Real-IP')
    else:
        return request.remote_addr

# ---------------- ROLE-BASED ACCESS CONTROL ----------------
def require_role(required_roles):
    """Decorator to check user role - accepts single role or list of roles"""
    def decorator(f):
        def decorated_function(*args, **kwargs):
            db = None
            cursor = None
            try:
                user_id = int(get_jwt_identity())
                db = get_db_connection()
                cursor = db.cursor()
                cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
                user = cursor.fetchone()
                
                if not user:
                    return jsonify({'error': 'User not found'}), 404
                
                user_role = user['role']
                
                # Convert single role to list for consistent handling
                if isinstance(required_roles, str):
                    required_roles_list = [required_roles]
                else:
                    required_roles_list = required_roles
                
                # Check if user role is in required roles
                if user_role not in required_roles_list:
                    return jsonify({'error': 'Insufficient permissions'}), 403
                
                return f(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error in require_role decorator: {e}")
                return jsonify({'error': 'Database error', 'details': str(e)}), 500
            finally:
                if cursor:
                    cursor.close()
                if db:
                    db.close()
        decorated_function.__name__ = f.__name__ + '_' + str(required_roles)
        return decorated_function
    return decorator

def require_admin():
    """Decorator to require Admin role"""
    return require_role('admin')

def require_sales():
    """Decorator to require Sales role"""
    return require_role('sales')

def require_finance():
    """Decorator to require Finance role"""
    return require_role('finance')

def require_admin_or_finance():
    """Decorator to require Admin or Finance role"""
    return require_role(['admin', 'finance'])

def require_admin_or_sales():
    """Decorator to require Admin or Sales role"""
    return require_role(['admin', 'sales'])

def require_any_role():
    """Decorator to require any valid role"""
    return require_role(['admin', 'sales', 'finance'])

# Helpful JWT error handlers
@jwt.unauthorized_loader
def handle_missing_token(err):
    # Debug: Print request details
    print(f"JWT Unauthorized: {err}")
    print(f"Request headers: {dict(request.headers)}")
    print(f"Request cookies: {dict(request.cookies)}")
    return jsonify({'error': 'Missing token', 'details': err}), 401

@jwt.invalid_token_loader
def handle_invalid_token(err):
    return jsonify({'error': 'Invalid token', 'details': err}), 401

@jwt.expired_token_loader
def handle_expired_token(jwt_header, jwt_payload):
    return jsonify({'error': 'Token expired', 'details': 'Please sign in again.'}), 401

# ---------------- MYSQL CONFIG ----------------
import pymysql
import logging
import re

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_db_connection():
    """Get MySQL database connection with proper error handling"""
    try:
        # Get database configuration from environment variables
        db_host = os.getenv('DB_HOST', 'localhost')
        db_user = os.getenv('DB_USER', 'root')
        db_password = os.getenv('DB_PASSWORD', '')
        db_name = os.getenv('DB_NAME', 'wanaagtravel_db')
        
        # First try to connect to the database
        connection = pymysql.connect(
            host=db_host,
            user=db_user,
            password=db_password,
            database=db_name,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False
        )
        return connection
    except Exception as e:
        # If database doesn't exist, try to create it
        try:
            logger.info("Database not found, attempting to create it...")
            # Connect without specifying database
            temp_connection = pymysql.connect(
                host='localhost',
                user='root',
                password='',
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor,
                autocommit=True
            )
            cursor = temp_connection.cursor()
            cursor.execute("CREATE DATABASE IF NOT EXISTS wanaagtravel_db")
            cursor.close()
            temp_connection.close()
            
            # Now try to connect to the created database
            connection = pymysql.connect(
                host='localhost',
                user='root',
                password='',
                database='wanaagtravel_db',
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor,
                autocommit=False
            )
            return connection
        except Exception as create_error:
            logger.error(f"Database creation failed: {create_error}")
            raise Exception(f"Database connection failed: {e}")

# Ensure default user exists before app runs
DEFAULT_EMAIL = 'admin@wanaagtravel.com'
DEFAULT_USERNAME = 'admin'
DEFAULT_PASSWORD = 'Admin@123'  # This will be hashed

def ensure_default_user():
    """Ensure default Super Admin user exists in MySQL database"""
    db = None
    cursor = None
    try:
        logger.info("Attempting to connect to MySQL database...")
        db = get_db_connection()
        logger.info("MySQL database connection successful!")
        cursor = db.cursor()
        
        # Create password reset codes table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS password_reset_codes (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                email VARCHAR(255) NOT NULL,
                reset_code VARCHAR(255) NOT NULL,
                expires_at DATETIME NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create users table with proper MySQL syntax
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
        
        db.commit()
        
        # Check if default Super Admin user exists
        cursor.execute("SELECT id FROM users WHERE email = %s", (DEFAULT_EMAIL,))
        existing_user = cursor.fetchone()
        
        if not existing_user:
            logger.info(f"Creating default Admin user: {DEFAULT_EMAIL}")
            hashed_password = generate_password_hash(DEFAULT_PASSWORD)
            cursor.execute("""
                INSERT INTO users (username, email, password_hash, first_name, last_name, role, is_active, dashboard_access)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (DEFAULT_USERNAME, DEFAULT_EMAIL, hashed_password, 'Super', 'Admin', 'admin', 1, 1))
            db.commit()
            user_id = cursor.lastrowid
            logger.info("Default Admin user created successfully!")
        else:
            # Update existing user to admin role if needed
            cursor.execute("UPDATE users SET role='admin' WHERE email=%s", (DEFAULT_EMAIL,))
            db.commit()
            user_id = existing_user['id']
            logger.info("Default user updated to Admin role")
            
        # Ensure user module permissions table exists
        ensure_user_module_permissions_table()
        
        # Set up full permissions for super admin
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
        logger.info("Super Admin permissions set successfully!")
            
    except Exception as e:
        logger.error(f"Error in ensure_default_user: {e}")
        if db:
            db.rollback()
        raise Exception(f"Failed to ensure default user: {e}")
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()

def verify_super_admin():
    """Verify Super Admin account exists with full permissions"""
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
            logger.error("Super Admin account not found!")
            return False
        
        if not super_admin['is_active']:
            logger.error("Super Admin account is inactive!")
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
            logger.error(f"Super Admin missing permissions for: {missing_permissions}")
            return False
        
        logger.info(f"Super Admin verified: {super_admin['email']} with full permissions")
        return True
        
    except Exception as e:
        logger.error(f"Error verifying Super Admin: {e}")
        return False
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()

# New: ensure tickets table exists
def ensure_tickets_table():
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS tickets (
            id INT AUTO_INCREMENT PRIMARY KEY,
            names VARCHAR(255) NOT NULL,
            route VARCHAR(255) NOT NULL,
            contact_person VARCHAR(255) DEFAULT NULL,
            pnr_ref VARCHAR(255) DEFAULT NULL,
            airline_fac_agency VARCHAR(255) DEFAULT NULL,
            net_fare DECIMAL(10,2) DEFAULT 0.00,
            paid DECIMAL(10,2) DEFAULT 0.00,
            cmm DECIMAL(10,2) DEFAULT 0.00,
            total_paid DECIMAL(10,2) DEFAULT 0.00,
            date_issue DATE DEFAULT NULL,
            date_departure DATE DEFAULT NULL,
            return_date DATE DEFAULT NULL,
            telephone VARCHAR(255) DEFAULT NULL,
            payment_status VARCHAR(50) DEFAULT 'Unpaid',
            payment_method VARCHAR(255) DEFAULT NULL,
            transaction_ref VARCHAR(255) DEFAULT NULL,
            created_by INT DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
        """
    )
    
    # Add payment method fields to existing tickets table if they don't exist
    try:
        cursor.execute("ALTER TABLE tickets ADD COLUMN payment_method VARCHAR(255) DEFAULT NULL")
    except:
        pass  # Column already exists
    
    try:
        cursor.execute("ALTER TABLE tickets ADD COLUMN transaction_ref VARCHAR(255) DEFAULT NULL")
    except:
        pass  # Column already exists
    
    # Add amount_paid column to existing tickets table if it doesn't exist
    try:
        cursor.execute("ALTER TABLE tickets ADD COLUMN amount_paid DECIMAL(10,2) DEFAULT 0.00")
    except:
        pass  # Column already exists

    # Ensure updated_at exists for legacy ticket tables.
    try:
        cursor.execute("ALTER TABLE tickets ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")
    except:
        pass  # Column already exists
    
    # Update existing records to follow Net Fare + CMM = Total Paid formula
    try:
        cursor.execute("""
            UPDATE tickets 
            SET total_paid = net_fare + cmm,
                paid = net_fare + cmm,
                payment_status = 'Paid'
            WHERE total_paid != (net_fare + cmm) OR total_paid IS NULL
        """)
        updated_rows = cursor.rowcount
        if updated_rows > 0:
            print(f"Updated {updated_rows} existing ticket records to follow Net Fare + CMM = Total Paid formula")
    except Exception as e:
        print(f"Error updating existing records: {e}")
    
    db.commit()
    cursor.close()
    db.close()

# New: ensure visas table exists
def ensure_visas_table():
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS visas (
            id INT AUTO_INCREMENT PRIMARY KEY,
            customer_name VARCHAR(255) NOT NULL,
            country VARCHAR(255) NOT NULL,
            net_cost DECIMAL(10,2) DEFAULT 0.00,
            commission DECIMAL(10,2) DEFAULT 0.00,
            total_paid DECIMAL(10,2) DEFAULT 0.00,
            requested_date DATE DEFAULT NULL,
            payment_status VARCHAR(50) DEFAULT 'Unpaid',
            ref_no VARCHAR(255) DEFAULT NULL,
            contact_person_name VARCHAR(255) DEFAULT NULL,
            telephone VARCHAR(255) DEFAULT NULL,
            remarks TEXT,
            created_by INT DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    
    # Add payment method fields to existing visas table if they don't exist
    try:
        cursor.execute("ALTER TABLE visas ADD COLUMN payment_method VARCHAR(255) DEFAULT NULL")
        db.commit()
    except Exception:
        pass  # Column already exists
    
    try:
        cursor.execute("ALTER TABLE visas ADD COLUMN transaction_ref VARCHAR(255) DEFAULT NULL")
        db.commit()
    except Exception:
        pass  # Column already exists
    
    # Add amount_paid column to existing visas table if it doesn't exist
    try:
        cursor.execute("ALTER TABLE visas ADD COLUMN amount_paid DECIMAL(10,2) DEFAULT 0.00")
        db.commit()
    except Exception:
        pass  # Column already exists
    
    db.commit()
    cursor.close()
    db.close()

# New: ensure cargo table exists
def ensure_cargo_table():
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS cargo (
            id INT AUTO_INCREMENT PRIMARY KEY,
            customer_name VARCHAR(255) NOT NULL,
            country VARCHAR(255) NOT NULL,
            pickup_point VARCHAR(255) DEFAULT NULL,
            dropoff_point VARCHAR(255) DEFAULT NULL,
            net_cost DECIMAL(10,2) DEFAULT 0.00,
            commission DECIMAL(10,2) DEFAULT 0.00,
            total_paid DECIMAL(10,2) DEFAULT 0.00,
            requested_date DATE DEFAULT NULL,
            payment_status TEXT DEFAULT 'Unpaid',
            ref_no VARCHAR(255) DEFAULT NULL,
            contact_person_name VARCHAR(255) DEFAULT NULL,
            telephone VARCHAR(255) DEFAULT NULL,
            remarks TEXT,
            created_by INT DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    # Add pickup_point and dropoff_point columns if they don't exist (for existing databases)
    try:
        cursor.execute("ALTER TABLE cargo ADD COLUMN pickup_point VARCHAR(255) DEFAULT NULL")
        db.commit()
    except Exception:
        pass  # Column already exists
    
    try:
        cursor.execute("ALTER TABLE cargo ADD COLUMN dropoff_point VARCHAR(255) DEFAULT NULL")
        db.commit()
    except Exception:
        pass  # Column already exists
    
    # Add payment method fields to existing cargo table if they don't exist
    try:
        cursor.execute("ALTER TABLE cargo ADD COLUMN payment_method VARCHAR(255) DEFAULT NULL")
        db.commit()
    except Exception:
        pass  # Column already exists
    
    try:
        cursor.execute("ALTER TABLE cargo ADD COLUMN transaction_ref VARCHAR(255) DEFAULT NULL")
        db.commit()
    except Exception:
        pass  # Column already exists
    
    # Add amount_paid column to existing cargo table if it doesn't exist
    try:
        cursor.execute("ALTER TABLE cargo ADD COLUMN amount_paid DECIMAL(10,2) DEFAULT 0.00")
        db.commit()
    except Exception:
        pass  # Column already exists
    
    # Add weight and weight_cost columns to existing cargo table if they don't exist
    try:
        cursor.execute("ALTER TABLE cargo ADD COLUMN weight DECIMAL(10,2) DEFAULT 0.00")
        db.commit()
    except Exception:
        pass  # Column already exists
    
    try:
        cursor.execute("ALTER TABLE cargo ADD COLUMN weight_cost DECIMAL(10,2) DEFAULT 0.00")
        db.commit()
    except Exception:
        pass  # Column already exists
    
    db.commit()
    cursor.close()
    db.close()

# New: ensure transport table exists
def ensure_transport_table():
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS transport (
            id INT AUTO_INCREMENT PRIMARY KEY,
            customer_name VARCHAR(255) NOT NULL,
            agency_ref VARCHAR(255) DEFAULT NULL,
            pickup_point VARCHAR(255) DEFAULT NULL,
            dropoff_point VARCHAR(255) DEFAULT NULL,
            cost DECIMAL(10,2) DEFAULT 0.00,
            commission DECIMAL(10,2) DEFAULT 0.00,
            total DECIMAL(10,2) DEFAULT 0.00,
            total_paid DECIMAL(10,2) DEFAULT 0.00,
            date DATE DEFAULT NULL,
            telephone VARCHAR(255) DEFAULT NULL,
            vehicle VARCHAR(255) DEFAULT NULL,
            created_by INT DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    
    # Add payment method fields to existing transport table if they don't exist
    try:
        cursor.execute("ALTER TABLE transport ADD COLUMN payment_status TEXT DEFAULT 'Unpaid'")
        db.commit()
    except Exception:
        pass  # Column already exists
    
    try:
        cursor.execute("ALTER TABLE transport ADD COLUMN payment_method VARCHAR(255) DEFAULT NULL")
        db.commit()
    except Exception:
        pass  # Column already exists
    
    try:
        cursor.execute("ALTER TABLE transport ADD COLUMN transaction_ref VARCHAR(255) DEFAULT NULL")
        db.commit()
    except Exception:
        pass  # Column already exists
    
    # Add amount_paid column to existing transport table if it doesn't exist
    try:
        cursor.execute("ALTER TABLE transport ADD COLUMN amount_paid DECIMAL(10,2) DEFAULT 0.00")
        db.commit()
    except Exception:
        pass  # Column already exists
    
    # Add total_paid column to existing transport table if it doesn't exist
    try:
        cursor.execute("ALTER TABLE transport ADD COLUMN total_paid DECIMAL(10,2) DEFAULT 0.00")
        db.commit()
    except Exception:
        pass  # Column already exists
    
    db.commit()
    cursor.close()
    db.close()

# New: ensure financial tables exist (expenses, investments, receivable_loans, received_loans)
def ensure_financial_tables():
    db = get_db_connection()
    cursor = db.cursor()
    try:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS expenses (
                id INT AUTO_INCREMENT PRIMARY KEY,
                expense_date DATE DEFAULT NULL,
                category VARCHAR(255) DEFAULT NULL,
                description TEXT,
                quantity INT DEFAULT 1,
                amount DECIMAL(12,2) DEFAULT 0.00,
                created_by INT DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        # Backward compatibility for expenses
        try:
            cursor.execute("ALTER TABLE expenses ADD COLUMN quantity INT DEFAULT 1")
        except Exception:
            pass
        
        # Create investments table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS investments (
                id INT AUTO_INCREMENT PRIMARY KEY,
                invest_date DATE DEFAULT NULL,
                name VARCHAR(255) NOT NULL,
                amount DECIMAL(12,2) DEFAULT 0.00,
                required_amount DECIMAL(12,2) DEFAULT 0.00,
                requested_company VARCHAR(255) DEFAULT NULL,
                amount_paid DECIMAL(12,2) DEFAULT 0.00,
                amount_remaining DECIMAL(12,2) DEFAULT 0.00,
                required_interest DECIMAL(6,2) DEFAULT 0.00,
                status TEXT DEFAULT 'Not Paid',
                notes TEXT,
                created_by INT DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        # Backward compatibility: add columns if upgrading existing table
        try:
            cursor.execute("ALTER TABLE investments ADD COLUMN required_amount DECIMAL(12,2) DEFAULT 0.00")
        except Exception:
            pass
        try: cursor.execute("ALTER TABLE investments ADD COLUMN requested_company VARCHAR(255) DEFAULT NULL")
        except Exception: pass
        try: cursor.execute("ALTER TABLE investments ADD COLUMN amount_paid DECIMAL(12,2) DEFAULT 0.00")
        except Exception: pass
        try: cursor.execute("ALTER TABLE investments ADD COLUMN amount_remaining DECIMAL(12,2) DEFAULT 0.00")
        except Exception: pass
        try: cursor.execute("ALTER TABLE investments ADD COLUMN required_interest DECIMAL(6,2) DEFAULT 0.00")
        except Exception: pass
        try: cursor.execute("ALTER TABLE investments ADD COLUMN status TEXT DEFAULT 'Not Paid'")
        except Exception: pass
        try: cursor.execute("ALTER TABLE investments ADD COLUMN notes TEXT")
        except Exception: pass
        try: cursor.execute("ALTER TABLE investments ADD COLUMN created_by INT DEFAULT NULL")
        except Exception: pass
        try: cursor.execute("ALTER TABLE investments ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        except Exception: pass
        
        # Create received_loans table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS received_loans (
                id INT AUTO_INCREMENT PRIMARY KEY,
                received_date DATE DEFAULT NULL,
                lender VARCHAR(255) NOT NULL,
                amount DECIMAL(12,2) DEFAULT 0.00,
                due_date DATE DEFAULT NULL,
                interest_rate DECIMAL(5,2) DEFAULT 0.00,
                status TEXT DEFAULT 'Active',
                notes TEXT,
                created_by INT DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        
        # Add sample data if table is empty
        cursor.execute("SELECT COUNT(*) as count FROM expenses")
        count = cursor.fetchone()['count']
        if count == 0:
            sample_expenses = [
                ('2025-01-09', 'transport', 'moto ayaaa lagu raacey', 1, 2.00),
                ('2025-01-08', 'office', 'Stationery supplies', 5, 25.50),
                ('2025-01-07', 'utilities', 'Electricity bill', 1, 150.00),
                ('2025-01-06', 'rent', 'Office rent payment', 1, 500.00),
                ('2025-01-05', 'transport', 'Fuel for company vehicle', 1, 45.75)
            ]
            cursor.executemany(
                "INSERT INTO expenses (expense_date, category, description, quantity, amount) VALUES (%s, %s, %s, %s, %s)",
                sample_expenses
            )
            db.commit()
        
        # Add sample data for investments if table is empty
        cursor.execute("SELECT COUNT(*) as count FROM investments")
        count = cursor.fetchone()['count']
        if count == 0:
            sample_investments = [
                ('2025-01-09', 'ticket', 'ayuub', 3000.00, 0.00, 3000.00, 0.00, 'Draft', 'Sample investment 1'),
                ('2025-01-08', 'equipment', 'tech corp', 2000.00, 500.00, 1500.00, 5.00, 'Partial Paid', 'Sample investment 2'),
                ('2025-01-07', 'property', 'real estate', 5000.00, 5000.00, 0.00, 3.00, 'Paid', 'Sample investment 3'),
                ('2025-01-06', 'stocks', 'finance co', 1000.00, 0.00, 1000.00, 2.50, 'Not Paid', 'Sample investment 4')
            ]
            cursor.executemany(
                "INSERT INTO investments (invest_date, name, requested_company, required_amount, amount_paid, amount_remaining, required_interest, status, notes) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                sample_investments
            )
            db.commit()
        
        # Fix existing status values that might be truncated
        status_updates = [
            ('PA', 'Paid'),
            ('DR', 'Draft'),
            ('NP', 'Not Paid'),
            ('PP', 'Partial Paid'),
            ('draft', 'Draft'),
            ('paid', 'Paid'),
            ('not paid', 'Not Paid'),
            ('partial paid', 'Partial Paid')
        ]
        
        for old_status, new_status in status_updates:
            cursor.execute("UPDATE investments SET status = %s WHERE status = %s", (new_status, old_status))
        
        db.commit()
        
        # Add sample data for received loans if table is empty
        cursor.execute("SELECT COUNT(*) as count FROM received_loans")
        count = cursor.fetchone()['count']
        if count == 0:
            sample_loans = [
                ('2025-01-09', 'Bank of Somalia', 10000.00, '2025-12-31', 5.00, 'Active', 'Business expansion loan'),
                ('2025-01-08', 'Microfinance Institution', 5000.00, '2025-06-30', 8.00, 'Active', 'Working capital loan'),
                ('2025-01-07', 'Private Investor', 15000.00, '2025-09-15', 3.00, 'Active', 'Equipment purchase loan'),
                ('2025-01-06', 'Government Bank', 25000.00, '2026-01-01', 2.50, 'Active', 'Long-term business loan')
            ]
            cursor.executemany(
                "INSERT INTO received_loans (received_date, lender, amount, due_date, interest_rate, status, notes) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                sample_loans
            )
            db.commit()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS receivable_loans (
                id INT AUTO_INCREMENT PRIMARY KEY,
                issued_date DATE DEFAULT NULL,
                borrower VARCHAR(255) NOT NULL,
                amount DECIMAL(12,2) DEFAULT 0.00,
                due_date DATE DEFAULT NULL,
                status TEXT DEFAULT 'Pending',
                notes TEXT,
                created_by INT DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS received_loans (
                id INT AUTO_INCREMENT PRIMARY KEY,
                received_date DATE DEFAULT NULL,
                lender VARCHAR(255) NOT NULL,
                amount DECIMAL(12,2) DEFAULT 0.00,
                due_date DATE DEFAULT NULL,
                interest_rate DECIMAL(5,2) DEFAULT 0.00,
                status TEXT DEFAULT 'Active',
                notes TEXT,
                created_by INT DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        db.commit()
        
        # Create invoices table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS invoices (
                id INT AUTO_INCREMENT PRIMARY KEY,
                invoice_number VARCHAR(255) NOT NULL UNIQUE,
                invoice_date DATE NOT NULL,
                due_date DATE NOT NULL,
                customer_name VARCHAR(255) NOT NULL,
                customer_phone VARCHAR(255) DEFAULT NULL,
                customer_reference VARCHAR(255) DEFAULT NULL,
                sales_from VARCHAR(255) DEFAULT NULL,
                subtotal DECIMAL(12,2) DEFAULT 0.00,
                tax_percentage DECIMAL(5,2) DEFAULT 0.00,
                tax_amount DECIMAL(12,2) DEFAULT 0.00,
                total_amount DECIMAL(12,2) DEFAULT 0.00,
                notes VARCHAR(255) DEFAULT NULL,
                status VARCHAR(50) DEFAULT 'draft',
                created_by INT DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
            """
        )
        
        # Create invoice items table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS invoice_items (
                id INT AUTO_INCREMENT PRIMARY KEY,
                invoice_id INT NOT NULL,
                description VARCHAR(255) NOT NULL,
                quantity INT DEFAULT 1,
                unit_price DECIMAL(12,2) DEFAULT 0.00,
                amount DECIMAL(12,2) DEFAULT 0.00,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        db.commit()
        
        # Create receipts table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS receipts (
                id INT AUTO_INCREMENT PRIMARY KEY,
                receipt_number VARCHAR(255) NOT NULL UNIQUE,
                receipt_date DATE NOT NULL,
                received_from VARCHAR(255) NOT NULL,
                total_amount DECIMAL(12,2) DEFAULT 0.00,
                notes VARCHAR(255) DEFAULT NULL,
                status VARCHAR(50) DEFAULT 'draft',
                created_by INT DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            );
            """
        )
        
        # Create receipt items table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS receipt_items (
                id INT AUTO_INCREMENT PRIMARY KEY,
                receipt_id INT NOT NULL,
                item_number INT DEFAULT 1,
                description VARCHAR(255) NOT NULL,
                quantity INT DEFAULT 1,
                unit_price DECIMAL(12,2) DEFAULT 0.00,
                total_amount DECIMAL(12,2) DEFAULT 0.00,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        db.commit()
    finally:
        cursor.close(); db.close()

def ensure_invoice_receipt_tables():
    """Ensure invoice and receipt tables exist"""
    try:
        print("Ensuring invoice and receipt tables exist...")
        db = get_db_connection()
        cursor = db.cursor()
        
        # Create invoices table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS invoices (
                id INT AUTO_INCREMENT PRIMARY KEY,
                invoice_number VARCHAR(255) NOT NULL UNIQUE,
                invoice_date DATE NOT NULL,
                due_date DATE NOT NULL,
                customer_name VARCHAR(255) NOT NULL,
                customer_phone VARCHAR(255) DEFAULT NULL,
                customer_reference VARCHAR(255) DEFAULT NULL,
                subtotal DECIMAL(12,2) DEFAULT 0.00,
                tax_percentage DECIMAL(5,2) DEFAULT 0.00,
                tax_amount DECIMAL(12,2) DEFAULT 0.00,
                total_amount DECIMAL(12,2) DEFAULT 0.00,
                notes VARCHAR(255) DEFAULT NULL,
                status VARCHAR(50) DEFAULT 'draft',
                created_by INT DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            );
            """
        )
        
        # Create invoice items table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS invoice_items (
                id INT AUTO_INCREMENT PRIMARY KEY,
                invoice_id INT NOT NULL,
                description VARCHAR(255) NOT NULL,
                quantity INT DEFAULT 1,
                unit_price DECIMAL(12,2) DEFAULT 0.00,
                amount DECIMAL(12,2) DEFAULT 0.00,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        
        # Create receipts table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS receipts (
                id INT AUTO_INCREMENT PRIMARY KEY,
                receipt_number VARCHAR(255) NOT NULL UNIQUE,
                receipt_date DATE NOT NULL,
                received_from VARCHAR(255) NOT NULL,
                total_amount DECIMAL(12,2) DEFAULT 0.00,
                notes VARCHAR(255) DEFAULT NULL,
                status VARCHAR(50) DEFAULT 'draft',
                created_by INT DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            );
            """
        )
        
        # Create receipt items table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS receipt_items (
                id INT AUTO_INCREMENT PRIMARY KEY,
                receipt_id INT NOT NULL,
                item_number INT DEFAULT 1,
                description VARCHAR(255) NOT NULL,
                quantity INT DEFAULT 1,
                unit_price DECIMAL(12,2) DEFAULT 0.00,
                total_amount DECIMAL(12,2) DEFAULT 0.00,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        
        # Add sales_from column if it doesn't exist
        try:
            cursor.execute("ALTER TABLE invoices ADD COLUMN sales_from VARCHAR(255) DEFAULT NULL AFTER customer_reference")
            db.commit()
            print("Added sales_from column to invoices table")
        except Exception as e:
            # Column already exists, ignore error
            pass
        
        db.commit()
        cursor.close()
        db.close()
        print("Invoice and receipt tables ensured successfully!")
        
    except Exception as e:
        print(f"Error ensuring invoice and receipt tables: {e}")
        import traceback
        traceback.print_exc()

# ---------------- FRONTEND ROUTE ----------------
@app.before_request
def enforce_canonical_host():
    try:
        host = (request.host or '')
        # If host already canonical or is CLI/testing, do nothing
        if host.startswith('127.0.0.1:5000') or host.startswith('localhost:5000'):
            return None
        # Redirect any other host (e.g., ::1, machine name) to 127.0.0.1:5000 preserving path and query
        target = f"http://127.0.0.1:5000{request.full_path}"
        # Flask's request.full_path always ends with '%s' when no query; strip trailing '%s'
        if target.endswith('%s'):
            target = target[:-1]
        return redirect(target, code=302)
    except Exception:
        # Fail-open: never block request if something goes wrong here
        return None

@app.route('/')
def home():
    # Public layout disabled: send all traffic to admin login
    return redirect('/admin')

@app.route('/static/uploads/<filename>')
def uploaded_file(filename):
    """Serve uploaded files"""
    try:
        uploads_dir = os.path.join(app.static_folder, 'uploads')
        print(f"Serving file: {filename} from {uploads_dir}")
        
        if not os.path.exists(uploads_dir):
            print(f"Uploads directory does not exist: {uploads_dir}")
            return "Directory not found", 404
            
        file_path = os.path.join(uploads_dir, filename)
        if not os.path.exists(file_path):
            print(f"File does not exist: {file_path}")
            return "File not found", 404
            
        print(f"Successfully serving file: {file_path}")
        return send_from_directory(uploads_dir, filename)
    except Exception as e:
        print(f"Error serving file {filename}: {str(e)}")
        return f"Error: {str(e)}", 500

@app.route('/test-images')
def test_images():
    """Test route to check available images"""
    try:
        uploads_dir = os.path.join(app.static_folder, 'uploads')
        if os.path.exists(uploads_dir):
            files = os.listdir(uploads_dir)
            return jsonify({
                'success': True, 
                'uploads_dir': uploads_dir,
                'files': files,
                'static_folder': app.static_folder
            })
        else:
            return jsonify({'success': False, 'error': 'Uploads directory not found'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/dashboard')
def dashboard():
    """Public dashboard - redirect to admin dashboard"""
    # Check for JWT token in cookies or headers
    token = get_jwt_token_from_request()
    
    if not token:
        # No token found, redirect to login
        return redirect('/admin')
    
    # Verify the token
    user_id = verify_jwt_token(token)
    
    if not user_id:
        # Token is invalid, redirect to login
        return redirect('/admin')
        
    # Token is valid, redirect to admin dashboard
    return redirect('/admin/dashboard')

@app.route('/dashboard.html')
def dashboard_html():
    return redirect('/dashboard')

@app.route('/full')
def home_full():
    return redirect('/admin')

@app.route('/original')
def home_original():
    return redirect('/admin')

@app.route('/about')
def about():
    return redirect('/admin')

@app.route('/services')
def services():
    return redirect('/admin')

@app.route('/contact')
def contact():
    return redirect('/admin')

@app.route('/gallery')
def gallery():
    return redirect('/admin')


# ---------------- ADMIN ROUTES ----------------
@app.route('/admin')
def admin_login():
    """Admin login page - separate from public website"""
    return render_template('admin/login.html')

@app.route('/admin/dashboard')
def admin_dashboard():
    """Admin dashboard - separate from public website"""
    # Check for JWT token in cookies or headers
    token = get_jwt_token_from_request()
    
    if not token:
        # No token found, redirect to login
        return redirect('/admin')
    
    # Verify the token
    user_id = verify_jwt_token(token)
    
    if not user_id:
        # Token is invalid, redirect to login
        return redirect('/admin')
        
    # Token is valid, render dashboard
    return render_template('admin/dashboard.html')

@app.route('/admin/reset-password')
def admin_reset_password():
    """Admin reset password page"""
    return render_template('admin/reset-password.html')

# ---------------- API ROUTES ----------------

# Registration endpoint
@app.route('/api/register', methods=['POST'])
def register():
    """Register a new user with MySQL database"""
    db = None
    cursor = None
    
    try:
        # Get request data
        data = request.get_json(force=True)
        
        # Validate required fields
        email = (data.get('email') or '').strip().lower()
        password = (data.get('password') or '').strip()
        first_name = (data.get('firstName') or '').strip()
        last_name = (data.get('lastName') or '').strip()
        username = (data.get('username') or '').strip()
        
        # Validation
        if not email or not password:
            return jsonify({'error': 'Email and password are required'}), 400
        
        if len(password) < 6:
            return jsonify({'error': 'Password must be at least 6 characters long'}), 400
        
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            return jsonify({'error': 'Invalid email format'}), 400
        
        # Auto-generate username from email if not provided
        if not username:
            username = email.split('@')[0]
        
        # Connect to database
        db = get_db_connection()
        cursor = db.cursor()
        
        # Start transaction
        db.begin()
        
        # Check if email already exists
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        existing_user = cursor.fetchone()
        
        if existing_user:
            db.rollback()
            return jsonify({'error': 'Email already exists'}), 400
        
        # Hash password
        hashed_password = generate_password_hash(password)
        
        # Insert new user
        cursor.execute("""
            INSERT INTO users (username, email, password_hash, first_name, last_name, role, is_active, dashboard_access)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (username, email, hashed_password, first_name, last_name, 'sales', 1, 1))
        
        user_id = cursor.lastrowid
        
        # Set default module permissions for new user
        ensure_user_module_permissions_table()
        modules = [
            ('tickets', False),
            ('visas', False),
            ('cargo', False),
            ('transport', False),
            ('financial', False)
        ]
        
        for module_name, has_access in modules:
            cursor.execute(
                "INSERT INTO user_module_permissions (user_id, module_name, has_access) VALUES (%s, %s, %s)",
                (user_id, module_name, has_access)
            )
        
        # Commit transaction
        db.commit()
        
        logger.info(f"New user registered: {email}")
        
        return jsonify({
            'message': 'User registered successfully',
            'user': {
                'id': user_id,
                'email': email,
                'username': username,
                'firstName': first_name,
                'lastName': last_name,
                'role': 'user'
            }
        }), 201
        
    except Exception as e:
        logger.error(f"Registration error: {e}")
        if db:
            db.rollback()
        return jsonify({'error': 'Registration failed. Please try again.'}), 500
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()

# Login endpoint with MySQL
@app.route('/api/signin', methods=['POST'])
def signin():
    """Login user with MySQL database verification"""
    db = None
    cursor = None
    
    try:
        # Accept both JSON and form submissions
        data = request.get_json(silent=True) or {}
        email = (request.form.get('email') or data.get('email') or '').strip().lower()
        password = (request.form.get('password') or data.get('password') or '').strip()

        logger.info(f"Signin attempt: email={email}")

        if not email or not password:
            return jsonify({'error': 'Email and password are required'}), 400

        # Connect to MySQL database
        db = get_db_connection()
        cursor = db.cursor()
        
        # Query user by email using prepared statement
        cursor.execute("""
            SELECT id, username, email, password_hash, first_name, last_name, role, is_active, dashboard_access
            FROM users 
            WHERE email = %s AND is_active = 1
        """, (email,))
        user = cursor.fetchone()

        # If user not found but default creds provided, ensure user exists then reload
        if not user and email == DEFAULT_EMAIL and password == DEFAULT_PASSWORD:
            try:
                logger.info("[signin] Default admin not found. Creating...")
                cursor.close()
                db.close()
                ensure_default_user()
                db = get_db_connection()
                cursor = db.cursor()
                cursor.execute("""
                    SELECT id, username, email, password_hash, first_name, last_name, role, is_active, dashboard_access
                    FROM users 
                    WHERE email = %s AND is_active = 1
                """, (email,))
                user = cursor.fetchone()
            except Exception as e:
                logger.error(f"Init admin failed: {e}")
                try:
                    cursor.close()
                    db.close()
                except Exception:
                    pass
                return jsonify({'error': 'Authentication service unavailable'}), 500

        # If user exists but password mismatch and default creds used, reset the password hash
        if user and email == DEFAULT_EMAIL and password == DEFAULT_PASSWORD and not check_password_hash(user['password_hash'], password):
            logger.info("[signin] Resetting default admin password hash to known default.")
            cursor.execute("UPDATE users SET password_hash = %s WHERE id = %s", 
                         (generate_password_hash(DEFAULT_PASSWORD), user['id']))
            db.commit()
            # Reload user
            cursor.execute("""
                SELECT id, username, email, password_hash, first_name, last_name, role, is_active, dashboard_access
                FROM users 
                WHERE id = %s
            """, (user['id'],))
            user = cursor.fetchone()

        # Verify user exists and password matches
        if not user:
            logger.warning(f"Login attempt with non-existent email: {email}")
            return jsonify({'error': 'Invalid email or password'}), 401

        if not check_password_hash(user['password_hash'], password):
            logger.warning(f"Login attempt with incorrect password for email: {email}")
            return jsonify({'error': 'Invalid email or password'}), 401

        # Check if user is active
        if not user['is_active']:
            logger.warning(f"Login attempt with inactive account: {email}")
            return jsonify({'error': 'Account is deactivated'}), 401

        # Create JWT token
        access_token = create_access_token(identity=str(user['id']))
        
        # Log successful login (optional - don't fail if audit logging fails)
        try:
            log_audit_event(
                user_id=user['id'],
                action='LOGIN',
                resource='AUTHENTICATION',
                details=f"User {user['email']} logged in successfully",
                ip_address=get_client_ip()
            )
        except Exception as e:
            logger.warning(f"Failed to log login audit event: {e}")
            # Continue execution even if audit logging fails
        
        # Create response with token
        response = jsonify({
            'message': 'Login successful',
            'user': user['username'],
            'name': f"{user['first_name'] or ''} {user['last_name'] or ''}".strip() or user['username'],
            'role': user['role'],
            'token': access_token
        })
        
        # Set JWT cookie using Flask-JWT-Extended
        set_access_cookies(response, access_token)
        
        logger.info(f"Successful login for user {user['id']} ({email})")
        
        return response, 200
        
    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({'error': 'Login failed. Please try again.'}), 500
    finally:
        try:
            if cursor:
                cursor.close()
        except Exception:
            pass
        try:
            if db:
                db.close()
        except Exception:
            pass

@app.route('/api/logout', methods=['POST', 'GET'])
def logout():
    """Logout user and clear cookies"""
    print("Logout endpoint called")
    try:
        # Get the current token and add it to blacklist
        token = get_jwt_token_from_request()
        if token:
            blacklisted_tokens.add(token)
            print(f"Token blacklisted: {token[:20]}...")
        
        response = jsonify({'message': 'Logged out successfully'})
        unset_access_cookies(response)
        print("Logout successful")
        return response, 200
    except Exception as e:
        print(f"Logout error: {e}")
        return jsonify({'error': 'Logout failed', 'details': str(e)}), 500

@app.route('/logout', methods=['GET'])
def simple_logout():
    """Simple logout route for fallback"""
    print("Simple logout endpoint called")
    try:
        # Get the current token and add it to blacklist
        token = get_jwt_token_from_request()
        if token:
            blacklisted_tokens.add(token)
            print(f"Token blacklisted: {token[:20]}...")
        
        response = jsonify({'message': 'Logged out successfully'})
        unset_access_cookies(response)
        print("Simple logout successful")
        return response, 200
    except Exception as e:
        print(f"Simple logout error: {e}")
        return jsonify({'error': 'Logout failed', 'details': str(e)}), 500

@app.route('/test', methods=['GET'])
def test_route():
    """Test route to verify server is working"""
    return jsonify({'message': 'Server is working', 'status': 'ok'}), 200

@app.route('/api/verify-super-admin', methods=['GET'])
def verify_super_admin_route():
    """Verify Super Admin account exists with full permissions"""
    try:
        is_verified = verify_super_admin()
        if is_verified:
            return jsonify({
                'message': 'Super Admin account verified successfully',
                'status': 'ok',
                'super_admin_exists': True,
                'email': DEFAULT_EMAIL
            }), 200
        else:
            return jsonify({
                'message': 'Super Admin account verification failed',
                'status': 'error',
                'super_admin_exists': False
            }), 500
    except Exception as e:
        logger.error(f"Super Admin verification error: {e}")
        return jsonify({
            'message': 'Super Admin verification failed',
            'status': 'error',
            'error': str(e)
        }), 500

@app.route('/api/init-database', methods=['POST'])
def init_database():
    """Initialize database with default Super Admin user"""
    try:
        logger.info("Initializing database with default Super Admin user...")
        ensure_default_user()
        
        # Verify the user was created
        is_verified = verify_super_admin()
        if is_verified:
            return jsonify({
                'message': 'Database initialized successfully',
                'status': 'ok',
                'super_admin_created': True,
                'email': DEFAULT_EMAIL,
                'username': DEFAULT_USERNAME,
                'password': DEFAULT_PASSWORD
            }), 200
        else:
            return jsonify({
                'message': 'Database initialization failed - Super Admin not verified',
                'status': 'error',
                'super_admin_created': False
            }), 500
            
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        return jsonify({
            'message': 'Database initialization failed',
            'status': 'error',
            'error': str(e)
        }), 500

@app.route('/api/check-users', methods=['GET'])
def check_users():
    """Check if users exist in the database"""
    db = None
    cursor = None
    try:
        db = get_db_connection()
        cursor = db.cursor()
        
        # Count total users
        cursor.execute("SELECT COUNT(*) as total FROM users")
        total_users = cursor.fetchone()['total']
        
        # Get all users
        cursor.execute("""
            SELECT id, username, email, role, is_active, created_at
            FROM users 
            ORDER BY created_at DESC
        """)
        users = cursor.fetchall()
        
        return jsonify({
            'message': 'Users retrieved successfully',
            'total_users': total_users,
            'users': users
        }), 200
        
    except Exception as e:
        logger.error(f"Error checking users: {e}")
        return jsonify({
            'message': 'Failed to check users',
            'error': str(e)
        }), 500
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()

@app.route('/api/promote-to-super-admin', methods=['POST'])
def promote_to_super_admin():
    """Promote a user to Super Admin role"""
    db = None
    cursor = None
    try:
        data = request.get_json(force=True)
        email = data.get('email', '').strip().lower()
        
        if not email:
            return jsonify({'error': 'Email is required'}), 400
        
        db = get_db_connection()
        cursor = db.cursor()
        
        # Find user by email
        cursor.execute("SELECT id, email, role FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Update user role to super_admin
        cursor.execute("UPDATE users SET role = 'super_admin' WHERE email = %s", (email,))
        db.commit()
        
        user_id = user['id']
        
        # Set up full permissions for super admin
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
        
        logger.info(f"User {email} promoted to Super Admin successfully")
        
        return jsonify({
            'message': 'User promoted to Super Admin successfully',
            'user': {
                'id': user_id,
                'email': email,
                'role': 'super_admin'
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error promoting user to Super Admin: {e}")
        if db:
            db.rollback()
        return jsonify({
            'message': 'Failed to promote user to Super Admin',
            'error': str(e)
        }), 500
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()

@app.route('/api/force-super-admin', methods=['POST'])
def force_super_admin():
    """Force set current user to Super Admin role"""
    db = None
    cursor = None
    try:
        user_id = int(get_jwt_identity())
        db = get_db_connection()
        cursor = db.cursor()
        
        # Update current user role to super_admin
        cursor.execute("UPDATE users SET role = 'super_admin' WHERE id = %s", (user_id,))
        db.commit()
        
        # Set up full permissions for super admin
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
        
        logger.info(f"User {user_id} forced to Super Admin successfully")
        
        return jsonify({
            'message': 'User role updated to Super Admin successfully',
            'role': 'super_admin'
        }), 200
        
    except Exception as e:
        logger.error(f"Error forcing Super Admin role: {e}")
        if db:
            db.rollback()
        return jsonify({
            'message': 'Failed to update user role',
            'error': str(e)
        }), 500
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()

@app.route('/api/audit-logs', methods=['GET'])
@jwt_required()
@require_admin()
def get_audit_logs():
    """Get audit logs (admin only)"""
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        offset = (page - 1) * per_page
        
        db = get_db_connection()
        cursor = db.cursor()
        
        # Get total count
        cursor.execute("SELECT COUNT(*) FROM audit_logs")
        total_count = cursor.fetchone()['COUNT(*)']
        
        # Get audit logs with user info
        cursor.execute("""
            SELECT al.id, al.user_id, al.action, al.resource, al.details, 
                   al.ip_address, al.timestamp, u.email, u.first_name, u.last_name
            FROM audit_logs al
            LEFT JOIN users u ON al.user_id = u.id
            ORDER BY al.timestamp DESC
            LIMIT %s OFFSET %s
        """, (per_page, offset))
        
        logs = cursor.fetchall()
        
        cursor.close()
        db.close()
        
        return jsonify({
            'logs': logs,
            'total_count': total_count,
            'page': page,
            'per_page': per_page,
            'total_pages': (total_count + per_page - 1) // per_page
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting audit logs: {e}")
        return jsonify({'error': 'Failed to get audit logs', 'details': str(e)}), 500

@app.route('/api/debug-role', methods=['GET'])
@jwt_required()
def debug_role():
    """Debug endpoint to check current user role and permissions"""
    db = None
    cursor = None
    try:
        user_id = int(get_jwt_identity())
        db = get_db_connection()
        cursor = db.cursor()
        
        # Get user info
        cursor.execute("SELECT id, email, role FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        
        # Get module permissions
        cursor.execute("SELECT module_name, has_access FROM user_module_permissions WHERE user_id = %s", (user_id,))
        permissions = cursor.fetchall()
        
        return jsonify({
            'user': user,
            'permissions': permissions,
            'is_admin': user['role'] == 'admin' if user else False
        }), 200
        
    except Exception as e:
        logger.error(f"Error in debug_role: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()

@app.route('/api/forgot-password', methods=['POST'])
def forgot_password():
    """Send password reset code to admin email"""
    try:
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        
        if not email:
            return jsonify({'error': 'Email is required'}), 400
        
        # Check if user exists
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("SELECT id, username FROM users WHERE LOWER(email) = %s", (email,))
        user = cursor.fetchone()
        
        if not user:
            cursor.close()
            db.close()
            return jsonify({'error': 'No account found with this email address'}), 404
        
        # Generate 6-digit verification code
        import random
        reset_code = str(random.randint(100000, 999999))
        
        # Store reset code in database (expires in 15 minutes)
        cursor.execute("""
            INSERT INTO password_reset_codes (user_id, email, reset_code, expires_at) 
            VALUES (%s, %s, %s, DATE_ADD(NOW(), INTERVAL 15 MINUTE))
            ON CONFLICT(user_id) DO UPDATE SET 
            reset_code = excluded.reset_code, 
            expires_at = excluded.expires_at
        """, (user['id'], email, reset_code))
        db.commit()
        cursor.close()
        db.close()
        
        # In a real application, you would send this via email
        # For now, we'll just return the code (remove this in production!)
        print(f"Password reset code for {email}: {reset_code}")
        
        return jsonify({
            'message': 'Password reset code sent to your email',
            'code': reset_code  # Remove this in production!
        }), 200
        
    except Exception as e:
        print(f"Forgot password error: {e}")
        return jsonify({'error': 'Failed to send reset code'}), 500

@app.route('/api/reset-password', methods=['POST'])
def reset_password():
    """Reset password with verification code"""
    try:
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        code = data.get('code', '').strip()
        new_password = data.get('new_password', '').strip()
        
        if not all([email, code, new_password]):
            return jsonify({'error': 'Email, code, and new password are required'}), 400
        
        if len(new_password) < 6:
            return jsonify({'error': 'Password must be at least 6 characters long'}), 400
        
        # Verify reset code
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("""
            SELECT prc.user_id, u.email 
            FROM password_reset_codes prc
            JOIN users u ON prc.user_id = u.id
            WHERE prc.email = %s AND prc.reset_code = %s AND prc.expires_at > NOW()
        """, (email, code))
        
        reset_record = cursor.fetchone()
        
        if not reset_record:
            cursor.close()
            db.close()
            return jsonify({'error': 'Invalid or expired reset code'}), 400
        
        # Update password
        hashed_password = generate_password_hash(new_password)
        cursor.execute("""
            UPDATE users 
            SET password_hash = %s, updated_at = NOW()
            WHERE id = %s
        """, (hashed_password, reset_record['user_id']))
        
        # Delete used reset code
        cursor.execute("DELETE FROM password_reset_codes WHERE user_id = %s", (reset_record['user_id'],))
        
        db.commit()
        cursor.close()
        db.close()
        
        return jsonify({'message': 'Password reset successfully'}), 200
        
    except Exception as e:
        print(f"Reset password error: {e}")
        return jsonify({'error': 'Failed to reset password'}), 500

@app.route('/api/users/<int:user_id>', methods=['DELETE'])
@jwt_required()
@require_role('admin')
def delete_user(user_id):
    """Delete a user (admin and super_admin only)"""
    try:
        # Get current user ID and role
        current_user_id = int(get_jwt_identity())
        db = get_db_connection()
        cursor = db.cursor()
        
        # Get current user's role
        cursor.execute("SELECT role FROM users WHERE id = %s", (current_user_id,))
        current_user = cursor.fetchone()
        if not current_user:
            cursor.close()
            db.close()
            return jsonify({'error': 'Current user not found'}), 404
        
        current_user_role = current_user['role']
        
        # Prevent self-deletion
        if current_user_id == user_id:
            cursor.close()
            db.close()
            return jsonify({'error': 'You cannot delete yourself'}), 400
        
        # Check if target user exists and get their role
        cursor.execute("SELECT id, role FROM users WHERE id = %s", (user_id,))
        target_user = cursor.fetchone()
        if not target_user:
            cursor.close()
            db.close()
            return jsonify({'error': 'User not found'}), 404
        
        target_user_role = target_user['role']
        
        # Role-based deletion restrictions
        if current_user_role == 'admin':
            # Admin cannot delete super_admin
            if target_user_role == 'super_admin':
                cursor.close()
                db.close()
                return jsonify({'error': 'It is not possible to delete the Super Admin.'}), 403
        
        elif current_user_role == 'super_admin':
            # Super admin can delete anyone except themselves (already checked above)
            pass
        
        else:
            # Other roles cannot delete users
            cursor.close()
            db.close()
            return jsonify({'error': 'You do not have permission to delete users'}), 403
        
        # Delete the user
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        db.commit()
        cursor.close()
        db.close()
        
        return jsonify({'success': True, 'message': 'User deleted successfully'}), 200
        
    except Exception as e:
        return jsonify({'error': 'Database error', 'details': str(e)}), 500

@app.route('/api/profile', methods=['GET'])
@jwt_required()
def get_profile():
    db = None
    cursor = None
    try:
        user_id = int(get_jwt_identity())
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get module permissions - handle case where table might not exist
        module_permissions = {}
        try:
            cursor.execute("""
                SELECT module_name, has_access 
                FROM user_module_permissions 
                WHERE user_id = %s
            """, (user_id,))
            permissions = cursor.fetchall()
            module_permissions = {perm['module_name']: perm['has_access'] for perm in permissions}
        except Exception as e:
            logger.warning(f"Module permissions table might not exist: {e}")
            # Set default permissions for the user
            ensure_user_module_permissions_table()
            modules = [('tickets', True), ('visas', True), ('cargo', True), ('transport', True), ('financial', True)]
            for module_name, has_access in modules:
                cursor.execute(
                    "INSERT IGNORE INTO user_module_permissions (user_id, module_name, has_access) VALUES (%s, %s, %s)",
                    (user_id, module_name, has_access)
                )
            db.commit()
            module_permissions = {module_name: has_access for module_name, has_access in modules}

        return jsonify({
            'id': user.get('id', ''),
            'firstName': user.get('first_name', ''),
            'lastName': user.get('last_name', ''),
            'email': user.get('email', ''),
            'photoUrl': user.get('photo_url', ''),
            'role': user.get('role', 'user'),
            'isActive': user.get('is_active', True),
            'createdAt': user.get('created_at', ''),
            'updatedAt': user.get('updated_at', ''),
            'modulePermissions': module_permissions
        })
    except Exception as e:
        logger.error(f"Error in get_profile: {e}")
        return jsonify({'error': 'Failed to load profile', 'details': str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()

@app.route('/api/profile', methods=['PUT'])
@jwt_required()
def update_profile():
    user_id = int(get_jwt_identity())
    data = request.json
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("UPDATE users SET first_name=%s, last_name=%s, email=%s WHERE id=%s",
                   (data.get('firstName', ''), data.get('lastName', ''), data.get('email', ''), user_id))
    db.commit()
    cursor.close()
    db.close()
    return jsonify({'firstName': data.get('firstName', ''),
                    'lastName': data.get('lastName', ''),
                    'email': data.get('email', '')})

@app.route('/api/profile/photo', methods=['POST'])
@jwt_required()
def upload_photo():
    user_id = int(get_jwt_identity())
    if 'photo' not in request.files:
        return jsonify({'error': 'No file'}), 400
    file = request.files['photo']
    filename = secure_filename(file.filename)
    filepath = os.path.join('static/profile_photos', filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    file.save(filepath)

    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("UPDATE users SET photo_url=%s WHERE id=%s", ('/' + filepath, user_id))
    db.commit()
    cursor.close()
    db.close()
    return jsonify({'photoUrl': '/' + filepath})

@app.route('/api/profile/password', methods=['PUT'])
@jwt_required()
def change_password():
    user_id = int(get_jwt_identity())
    data = request.json
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("SELECT password_hash FROM users WHERE id=%s", (user_id,))
    user = cursor.fetchone()
    if not check_password_hash(user['password_hash'], data['currentPassword']):
        cursor.close()
        db.close()
        return jsonify({'success': False, 'message': 'Current password incorrect'}), 400
    new_password = generate_password_hash(data['newPassword'])
    cursor.execute("UPDATE users SET password_hash=%s WHERE id=%s", (new_password, user_id))
    db.commit()
    cursor.close()
    db.close()
    return jsonify({'success': True})

@app.route('/upload', methods=['POST'])
@jwt_required()
def upload_image():
    if 'image' not in request.files:
        return jsonify({'error': 'No image uploaded'}), 400
    image = request.files['image']
    filename = secure_filename(image.filename)
    filepath = os.path.join('static/uploads', filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    image.save(filepath)
    prediction = 'Positive'
    confidence = 0.95
    return jsonify({'prediction': prediction, 'confidence': confidence})

@app.route('/api/health', methods=['GET'])
def health():
    try:
        db = get_db_connection()
        db.ping(reconnect=True)
        db.close()
        return jsonify({'status': 'ok'}), 200
    except Exception as e:
        return jsonify({'status': 'db_error', 'details': str(e)}), 500

@app.route('/api/test-user-creation', methods=['POST'])
@jwt_required()
@require_admin()
def test_user_creation():
    """Test endpoint to verify user creation works"""
    try:
        logger.info("Test user creation endpoint called")
        db = get_db_connection()
        cursor = db.cursor()
        
        # Test basic database operations
        cursor.execute("SELECT COUNT(*) as count FROM users")
        result = cursor.fetchone()
        logger.info(f"Current user count: {result['count']}")
        
        cursor.close()
        db.close()
        
        return jsonify({
            'status': 'success',
            'message': 'Database connection and user table access working',
            'user_count': result['count']
        }), 200
        
    except Exception as e:
        logger.error(f"Test user creation failed: {e}")
        return jsonify({
            'status': 'error',
            'message': 'Database test failed',
            'error': str(e)
        }), 500

@app.route('/api/test-db', methods=['GET'])
def test_db():
    """Test database connection and default user"""
    try:
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM users")
        result = cursor.fetchone()
        
        # Check if invoice tables exist
        cursor.execute("SHOW TABLES LIKE 'invoices'")
        invoices_table = cursor.fetchone()
        
        cursor.execute("SHOW TABLES LIKE 'invoice_items'")
        invoice_items_table = cursor.fetchone()
        
        cursor.execute("SHOW TABLES LIKE 'receipts'")
        receipts_table = cursor.fetchone()
        
        cursor.execute("SHOW TABLES LIKE 'receipt_items'")
        receipt_items_table = cursor.fetchone()
        
        # Check data counts
        invoice_count = 0
        receipt_count = 0
        if invoices_table:
            cursor.execute("SELECT COUNT(*) as count FROM invoices")
            invoice_count = cursor.fetchone()['count']
        
        if receipts_table:
            cursor.execute("SELECT COUNT(*) as count FROM receipts")
            receipt_count = cursor.fetchone()['count']
        
        cursor.close()
        db.close()
        return jsonify({
            'status': 'success', 
            'message': 'Database connection successful',
            'user_count': result['count'],
            'data_counts': {
                'invoices': invoice_count,
                'receipts': receipt_count
            },
            'tables': {
                'invoices': bool(invoices_table),
                'invoice_items': bool(invoice_items_table),
                'receipts': bool(receipts_table),
                'receipt_items': bool(receipt_items_table)
            }
        })
    except Exception as e:
        return jsonify({
            'status': 'error', 
            'message': f'Database connection failed: {str(e)}'
        }), 500

# New: Tickets API
@app.route('/api/tickets/<int:ticket_id>', methods=['GET'])
@jwt_required()
def get_ticket(ticket_id):
    """Get a specific ticket record"""
    try:
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM tickets WHERE id = %s", (ticket_id,))
        ticket = cursor.fetchone()
        cursor.close()
        db.close()
        
        if not ticket:
            return jsonify({'error': 'Ticket not found'}), 404
            
        return jsonify(ticket)
    except Exception as e:
        return jsonify({'error': 'Failed to fetch ticket', 'details': str(e)}), 500

@app.route('/api/tickets/<int:ticket_id>', methods=['DELETE'])
@jwt_required()
def delete_ticket(ticket_id):
    """Delete a ticket record"""
    try:
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("DELETE FROM tickets WHERE id = %s", (ticket_id,))
        db.commit()
        cursor.close()
        db.close()
        
        return jsonify({'success': True, 'message': 'Ticket deleted successfully'})
    except Exception as e:
        return jsonify({'error': 'Failed to delete ticket', 'details': str(e)}), 500

@app.route('/api/tickets', methods=['GET'])
@jwt_required()
def list_tickets():
    db = get_db_connection()
    cursor = db.cursor()
    try:
        cursor.execute("SELECT * FROM tickets ORDER BY created_at DESC")
        rows = cursor.fetchall()
        return jsonify({'tickets': rows}), 200
    finally:
        cursor.close(); db.close()

@app.route('/api/tickets', methods=['POST'])
@jwt_required()
def create_ticket():
    user_id = int(get_jwt_identity())
    try:
        data = request.get_json(force=True)
    except Exception as e:
        return jsonify({'error': 'Invalid JSON', 'details': str(e)}), 400
    # Extract fields with defaults
    try:
        names = (data.get('names') or '').strip()
        route = (data.get('route') or '').strip()
        contact = (data.get('contact') or '').strip()
        pnr_ref = (data.get('pnr') or '').strip()
        airline = (data.get('airline') or '').strip()
        net_fare = float(data.get('netFare') or 0)
        total_paid_amount = float(data.get('totalPaid') or 0)
        amount_paid = float(data.get('amountPaid') or 0)
        # Auto-calculate commission: Commission = Total Paid - Net Fare
        commission_amount = total_paid_amount - net_fare
        cmm = commission_amount  # Store calculated commission amount
        paid = amount_paid  # Store amount paid as the actual paid amount
        date_issue = (data.get('dateIssue') or None) or None
        date_departure = (data.get('dateDeparture') or None) or None
        return_date = (data.get('returnDate') or None) or None
        phone = (data.get('phone') or '').strip()
        # Use manual payment status if provided, otherwise auto-determine
        status = (data.get('paymentStatus') or '').strip()
        if not status:
            # Auto-determine payment status based on amounts only if no manual status provided
            if amount_paid >= net_fare:
                status = 'Paid'
            elif amount_paid > 0:
                status = 'Partially Paid'
            else:
                status = 'Unpaid'
        payment_method = (data.get('paymentMethod') or '').strip()
        transaction_ref = (data.get('transactionRef') or '').strip()
    except Exception as e:
        return jsonify({'error': 'Invalid field types', 'details': str(e)}), 400

    if not names or not route:
        return jsonify({'error': 'names and route are required'}), 400

    def to_date(d):
        if not d:
            return None
        return d[:10]

    try:
        db = get_db_connection()
        cursor = db.cursor(pymysql.cursors.DictCursor)  # Use dictionary cursor
        cursor.execute(
            """
            INSERT INTO tickets
            (names, route, contact_person, pnr_ref, airline_fac_agency, net_fare, paid, cmm, total_paid, amount_paid, date_issue, date_departure, return_date, telephone, payment_status, payment_method, transaction_ref, created_by)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (names, route, contact, pnr_ref, airline, net_fare, paid, cmm, total_paid_amount, amount_paid, to_date(date_issue), to_date(date_departure), to_date(return_date), phone, status, payment_method, transaction_ref, user_id)
        )
        db.commit()
        ticket_id = cursor.lastrowid
        
        # Automatically create receivable loan for unpaid transactions
        if status in ['Unpaid', 'Partially Paid']:
            unpaid_amount = net_fare - amount_paid if status == 'Partially Paid' else net_fare
            print(f"Creating receivable loan for Ticket ID {ticket_id}, Status: {status}, Unpaid Amount: {unpaid_amount}")
            success = create_receivable_loan_for_unpaid_transaction(
                db, cursor, user_id, 'Ticket', ticket_id, names, unpaid_amount, 
                to_date(date_departure), f"Route: {route}, PNR: {pnr_ref}"
            )
            print(f"Receivable loan creation result: {success}")
            db.commit()
        
        cursor.close()
        cursor2 = db.cursor()
        cursor2.execute("SELECT * FROM tickets WHERE id=%s", (ticket_id,))
        row = cursor2.fetchone()
        cursor2.close()
        db.close()
        return jsonify({'success': True, 'ticket': row}), 201
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        return jsonify({'error': 'DB error while saving ticket', 'details': str(e)}), 500

@app.route('/api/tickets/<int:ticket_id>', methods=['PUT'])
@jwt_required()
def update_ticket(ticket_id):
    """Update a specific ticket record"""
    user_id = int(get_jwt_identity())
    try:
        data = request.get_json(force=True)
        print(f"UPDATE TICKET {ticket_id}: Received data: {data}")
    except Exception as e:
        print(f"UPDATE TICKET {ticket_id}: JSON parsing error: {e}")
        return jsonify({'error': 'Invalid JSON', 'details': str(e)}), 400
    
    # Extract fields with defaults
    try:
        names = (data.get('names') or '').strip()
        route = (data.get('route') or '').strip()
        contact = (data.get('contact') or '').strip()
        pnr_ref = (data.get('pnr') or '').strip()
        airline = (data.get('airline') or '').strip()
        net_fare = float(data.get('netFare') or 0)
        total_paid_amount = float(data.get('totalPaid') or 0)
        amount_paid = float(data.get('amountPaid') or 0)
        # Auto-calculate commission: Commission = Total Paid - Net Fare
        commission_amount = total_paid_amount - net_fare
        cmm = commission_amount  # Store calculated commission amount
        paid = amount_paid  # Store amount paid as the actual paid amount
        date_issue = (data.get('dateIssue') or None) or None
        date_departure = (data.get('dateDeparture') or None) or None
        return_date = (data.get('returnDate') or None) or None
        phone = (data.get('phone') or '').strip()
        # Use manual payment status if provided, otherwise auto-determine
        status = (data.get('paymentStatus') or '').strip()
        if not status:
            # Auto-determine payment status based on amounts only if no manual status provided
            if amount_paid >= net_fare:
                status = 'Paid'
            elif amount_paid > 0:
                status = 'Partially Paid'
            else:
                status = 'Unpaid'
        payment_method = (data.get('paymentMethod') or '').strip()
        transaction_ref = (data.get('transactionRef') or '').strip()
    except Exception as e:
        return jsonify({'error': 'Invalid field types', 'details': str(e)}), 400

    if not names or not route:
        return jsonify({'error': 'names and route are required'}), 400

    def to_date(d):
        if not d:
            return None
        return d[:10]

    try:
        db = get_db_connection()
        cursor = db.cursor()
        
        # Check if ticket exists and get old status
        print(f"Checking ticket {ticket_id} exists...")
        cursor.execute("SELECT payment_status FROM tickets WHERE id = %s", (ticket_id,))
        old_ticket = cursor.fetchone()
        print(f"Query result for ticket {ticket_id}: {old_ticket}")
        
        if not old_ticket:
            print(f"Ticket {ticket_id} not found")
            cursor.close()
            db.close()
            return jsonify({'error': 'Ticket not found'}), 404
        
        # Get the old status safely - handle both tuple and dict results
        try:
            if isinstance(old_ticket, dict):
                old_status = old_ticket.get('payment_status', 'Unknown')
            else:
                old_status = old_ticket[0] if old_ticket and len(old_ticket) > 0 else 'Unknown'
            print(f"Old status for ticket {ticket_id}: {old_status}")
        except (IndexError, TypeError, KeyError) as e:
            print(f"Error accessing old_ticket: {e}")
            old_status = 'Unknown'
        
        # Update the ticket
        print(f"Updating ticket {ticket_id} with status: {status}")
        cursor.execute("""
            UPDATE tickets SET 
                names = %s, route = %s, contact_person = %s, pnr_ref = %s, 
                airline_fac_agency = %s, net_fare = %s, cmm = %s, paid = %s, total_paid = %s, amount_paid = %s,
                date_issue = %s, date_departure = %s, return_date = %s, 
                telephone = %s, payment_status = %s, payment_method = %s, 
                transaction_ref = %s, updated_at = NOW()
            WHERE id = %s
        """, (
            names, route, contact, pnr_ref, airline, net_fare, cmm, paid, total_paid_amount, amount_paid,
            to_date(date_issue), to_date(date_departure), to_date(return_date),
            phone, status, payment_method, transaction_ref, ticket_id
        ))
        print(f"Ticket {ticket_id} updated successfully")
        
        # Always sync receivable state from current payment values.
        try:
            sync_receivable_loan_for_transaction(
                db=db,
                cursor=cursor,
                user_id=user_id,
                transaction_type='Ticket',
                transaction_id=ticket_id,
                customer_name=names,
                total_amount=net_fare,
                amount_paid=amount_paid,
                due_date=to_date(date_departure) or to_date(date_issue),
                notes=f"Route: {route}, PNR: {pnr_ref}",
            )
        except Exception as receivable_error:
            print(f"Error syncing receivable loan for ticket {ticket_id}: {receivable_error}")
        
        db.commit()
        cursor.close()
        db.close()
        
        return jsonify({'message': 'Ticket updated successfully'})
        
    except Exception as e:
        print(f"ERROR updating ticket {ticket_id}: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'DB error while updating ticket', 'details': str(e)}), 500

# New: Visas API (Create)
@app.route('/api/visas', methods=['POST'])
@jwt_required()
def create_visa():
    user_id = int(get_jwt_identity())
    try:
        data = request.get_json(force=True)
    except Exception as e:
        return jsonify({'error': 'Invalid JSON', 'details': str(e)}), 400

    def to_date(d):
        if not d:
            return None
        return d[:10]

    try:
        customer_name = (data.get('customerName') or '').strip()
        country = (data.get('country') or '').strip()
        net_cost = float(data.get('netCost') or 0)
        commission = float(data.get('commission') or 0)
        total_paid = float(data.get('totalPaid') or 0)
        amount_paid = float(data.get('amountPaid') or 0)
        requested_date = to_date(data.get('requestedDate'))
        # Use manual payment status if provided, otherwise auto-determine
        payment_status = (data.get('paymentStatus') or '').strip()
        if not payment_status:
            # Auto-determine payment status based on amounts only if no manual status provided
            if amount_paid >= (net_cost + commission):
                payment_status = 'Paid'
            elif amount_paid > 0:
                payment_status = 'Partially Paid'
            else:
                payment_status = 'Unpaid'
        ref_no = (data.get('refNo') or '').strip()
        contact_person_name = (data.get('contactPersonName') or '').strip()
        telephone = (data.get('telephone') or '').strip()
        remarks = data.get('remarks')
    except Exception as e:
        return jsonify({'error': 'Invalid field types', 'details': str(e)}), 400

    if not customer_name or not country:
        return jsonify({'error': 'customerName and country are required'}), 400

    try:
        db = get_db_connection()
        cursor = db.cursor(pymysql.cursors.DictCursor)  # Use dictionary cursor
        cursor.execute(
            """
            INSERT INTO visas
            (customer_name, country, net_cost, commission, total_paid, amount_paid, requested_date, payment_status, payment_method, transaction_ref, ref_no, contact_person_name, telephone, remarks, created_by)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (customer_name, country, net_cost, commission, total_paid, amount_paid, requested_date, payment_status, data.get('paymentMethod', ''), data.get('transactionRef', ''), ref_no, contact_person_name, telephone, remarks, user_id)
        )
        db.commit()
        visa_id = cursor.lastrowid
        
        # Automatically create receivable loan for unpaid transactions
        if payment_status in ['Unpaid', 'Partially Paid']:
            unpaid_amount = (net_cost + commission) - amount_paid if payment_status == 'Partially Paid' else (net_cost + commission)
            print(f"Creating receivable loan for Visa ID {visa_id}, Status: {payment_status}, Unpaid Amount: {unpaid_amount}")
            success = create_receivable_loan_for_unpaid_transaction(
                db, cursor, user_id, 'Visa', visa_id, customer_name, unpaid_amount, 
                requested_date, f"Country: {country}, Ref: {ref_no}"
            )
            print(f"Receivable loan creation result: {success}")
            db.commit()
        
        cursor.close()
        cursor2 = db.cursor()
        cursor2.execute("SELECT * FROM visas WHERE id=%s", (visa_id,))
        row = cursor2.fetchone()
        cursor2.close()
        db.close()
        return jsonify({'success': True, 'visa': row}), 201
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        return jsonify({'error': 'DB error while saving visa', 'details': str(e)}), 500

# New: Cargo API (Create)
@app.route('/api/cargo', methods=['POST'])
@jwt_required()
def create_cargo():
    user_id = int(get_jwt_identity())
    try:
        data = request.get_json(force=True)
    except Exception as e:
        return jsonify({'error': 'Invalid JSON', 'details': str(e)}), 400

    def to_date(d):
        if not d:
            return None
        return d[:10]

    try:
        customer_name = (data.get('customerName') or '').strip()
        country = (data.get('country') or '').strip()
        pickup_point = (data.get('pickupPoint') or '').strip()
        dropoff_point = (data.get('dropoffPoint') or '').strip()
        weight = float(data.get('weight') or 0)
        weight_cost = float(data.get('weightCost') or 0)
        net_cost = float(data.get('netCost') or 0)
        commission = float(data.get('commission') or 0)
        amount_paid = float(data.get('amountPaid') or 0)
        total_paid = float(data.get('totalPaid') or 0)
        requested_date = to_date(data.get('requestedDate'))
        # Use manual payment status if provided, otherwise auto-determine
        payment_status = (data.get('paymentStatus') or '').strip()
        if not payment_status:
            # Auto-determine payment status based on amounts only if no manual status provided
            if amount_paid >= (net_cost + commission):
                payment_status = 'Paid'
            elif amount_paid > 0:
                payment_status = 'Partially Paid'
            else:
                payment_status = 'Unpaid'
        ref_no = (data.get('refNo') or '').strip()
        contact_person_name = (data.get('contactPersonName') or '').strip()
        telephone = (data.get('telephone') or '').strip()
        remarks = data.get('remarks')
    except Exception as e:
        return jsonify({'error': 'Invalid field types', 'details': str(e)}), 400

    if not customer_name or not country:
        return jsonify({'error': 'customerName and country are required'}), 400

    try:
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute(
            """
            INSERT INTO cargo
            (customer_name, country, pickup_point, dropoff_point, weight, weight_cost, net_cost, commission, total_paid, amount_paid, requested_date, payment_status, payment_method, transaction_ref, ref_no, contact_person_name, telephone, remarks, created_by)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (customer_name, country, pickup_point, dropoff_point, weight, weight_cost, net_cost, commission, total_paid, amount_paid, requested_date, payment_status, data.get('paymentMethod', ''), data.get('transactionRef', ''), ref_no, contact_person_name, telephone, remarks, user_id)
        )
        db.commit()
        cargo_id = cursor.lastrowid
        
        # Automatically create receivable loan for unpaid transactions
        if payment_status in ['Unpaid', 'Partially Paid']:
            unpaid_amount = (net_cost + commission) - amount_paid if payment_status == 'Partially Paid' else (net_cost + commission)
            print(f"Creating receivable loan for Cargo ID {cargo_id}, Status: {payment_status}, Unpaid Amount: {unpaid_amount}")
            success = create_receivable_loan_for_unpaid_transaction(
                db, cursor, user_id, 'Cargo', cargo_id, customer_name, unpaid_amount, 
                requested_date, f"From: {pickup_point} to {dropoff_point}, Ref: {ref_no}"
            )
            print(f"Receivable loan creation result: {success}")
            db.commit()
        
        cursor.close()
        cursor2 = db.cursor()
        cursor2.execute("SELECT * FROM cargo WHERE id=%s", (cargo_id,))
        row = cursor2.fetchone()
        cursor2.close()
        db.close()
        return jsonify({'success': True, 'cargo': row}), 201
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        return jsonify({'error': 'DB error while saving cargo', 'details': str(e)}), 500

# New: Transport API (Create)
@app.route('/api/transport', methods=['POST'])
@jwt_required()
def create_transport():
    user_id = int(get_jwt_identity())
    try:
        data = request.get_json(force=True)
    except Exception as e:
        return jsonify({'error': 'Invalid JSON', 'details': str(e)}), 400

    def to_date(d):
        if not d:
            return None
        return d[:10]

    try:
        customer_name = (data.get('customerName') or '').strip()
        agency_ref = (data.get('agencyRef') or '').strip()
        pickup_point = (data.get('pickupPoint') or '').strip()
        dropoff_point = (data.get('dropoffPoint') or '').strip()
        cost = float(data.get('cost') or 0)
        commission = float(data.get('commission') or 0)
        total_paid = float(data.get('totalPaid') or 0)
        amount_paid = float(data.get('amountPaid') or 0)
        date = to_date(data.get('date'))
        # Auto-determine payment status based on amounts
        if amount_paid >= (cost + commission):
            payment_status = 'Paid'
        elif amount_paid > 0:
            payment_status = 'Partially Paid'
        else:
            payment_status = 'Unpaid'
        payment_method = (data.get('paymentMethod') or '').strip()
        transaction_ref = (data.get('transactionRef') or '').strip()
        telephone = (data.get('telephone') or '').strip()
        vehicle = (data.get('vehicle') or '').strip()
    except Exception as e:
        return jsonify({'error': 'Invalid field types', 'details': str(e)}), 400

    if not customer_name:
        return jsonify({'error': 'customerName is required'}), 400

    try:
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute(
            """
            INSERT INTO transport
            (customer_name, agency_ref, pickup_point, dropoff_point, cost, commission, total, total_paid, amount_paid, date, payment_status, payment_method, transaction_ref, telephone, vehicle, created_by)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (customer_name, agency_ref, pickup_point, dropoff_point, cost, commission, cost + commission, total_paid, amount_paid, date, payment_status, payment_method, transaction_ref, telephone, vehicle, user_id)
        )
        db.commit()
        t_id = cursor.lastrowid
        
        # Automatically create receivable loan for unpaid transactions
        if payment_status in ['Unpaid', 'Partially Paid']:
            unpaid_amount = (cost + commission) - amount_paid if payment_status == 'Partially Paid' else (cost + commission)
            print(f"Creating receivable loan for Transport ID {t_id}, Status: {payment_status}, Unpaid Amount: {unpaid_amount}")
            success = create_receivable_loan_for_unpaid_transaction(
                db, cursor, user_id, 'Transport', t_id, customer_name, unpaid_amount, 
                date, f"From: {pickup_point} to {dropoff_point}, Vehicle: {vehicle}"
            )
            print(f"Receivable loan creation result: {success}")
            db.commit()
        
        cursor.close()
        cursor2 = db.cursor()
        cursor2.execute("SELECT * FROM transport WHERE id=%s", (t_id,))
        row = cursor2.fetchone()
        cursor2.close()
        db.close()
        return jsonify({'success': True, 'transport': row}), 201
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        return jsonify({'error': 'DB error while saving transport', 'details': str(e)}), 500

# Reports: list visas
@app.route('/api/visas/<int:visa_id>', methods=['GET'])
@jwt_required()
def get_visa(visa_id):
    """Get a specific visa record"""
    try:
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM visas WHERE id = %s", (visa_id,))
        visa = cursor.fetchone()
        cursor.close()
        db.close()
        
        if not visa:
            return jsonify({'error': 'Visa not found'}), 404
            
        return jsonify(visa)
    except Exception as e:
        return jsonify({'error': 'Failed to fetch visa', 'details': str(e)}), 500

@app.route('/api/visas/<int:visa_id>', methods=['PUT'])
@jwt_required()
def update_visa(visa_id):
    """Update a visa record"""
    user_id = int(get_jwt_identity())
    
    def to_date(d):
        if not d:
            return None
        return d[:10]
    
    try:
        data = request.get_json()
        db = get_db_connection()
        cursor = db.cursor()
        
        # Get old payment status
        cursor.execute("SELECT payment_status, net_cost, commission FROM visas WHERE id = %s", (visa_id,))
        old_visa = cursor.fetchone()
        if not old_visa:
            cursor.close()
            db.close()
            return jsonify({'error': 'Visa not found'}), 404
        
        # Get the old status safely - handle both tuple and dict results
        try:
            if isinstance(old_visa, dict):
                old_status = old_visa.get('payment_status', 'Unknown')
                net_cost = old_visa.get('net_cost', 0)
                commission = old_visa.get('commission', 0)
            else:
                old_status = old_visa[0] if old_visa and len(old_visa) > 0 else 'Unknown'
                net_cost = old_visa[1] if old_visa and len(old_visa) > 1 else 0
                commission = old_visa[2] if old_visa and len(old_visa) > 2 else 0
        except (IndexError, TypeError, KeyError) as e:
            old_status = 'Unknown'
            net_cost = 0
            commission = 0
        
        # Auto-determine new payment status based on CURRENT update amounts
        current_net_cost = float(data.get('netCost') or net_cost or 0)
        current_commission = float(data.get('commission') or commission or 0)
        amount_paid = float(data.get('amountPaid') or 0)
        if amount_paid >= (current_net_cost + current_commission):
            new_status = 'Paid'
        elif amount_paid > 0:
            new_status = 'Partially Paid'
        else:
            new_status = 'Unpaid'
        
        cursor.execute("""
            UPDATE visas SET 
                customer_name = %s, country = %s, net_cost = %s, commission = %s, 
                total_paid = %s, amount_paid = %s, requested_date = %s, payment_status = %s, 
                payment_method = %s, transaction_ref = %s, ref_no = %s, 
                contact_person_name = %s, telephone = %s, remarks = %s
            WHERE id = %s
        """, (
            data.get('customerName'),
            data.get('country'),
            data.get('netCost'),
            data.get('commission'),
            data.get('totalPaid'),
            data.get('amountPaid'),
            data.get('requestedDate'),
            new_status,
            data.get('paymentMethod'),
            data.get('transactionRef'),
            data.get('refNo'),
            data.get('contactPersonName'),
            data.get('telephone'),
            data.get('remarks'),
            visa_id
        ))
        
        # Always sync receivable state from current payment values.
        try:
            sync_receivable_loan_for_transaction(
                db=db,
                cursor=cursor,
                user_id=user_id,
                transaction_type='Visa',
                transaction_id=visa_id,
                customer_name=data.get('customerName'),
                total_amount=(current_net_cost + current_commission),
                amount_paid=amount_paid,
                due_date=to_date(data.get('requestedDate')),
                notes=f"Country: {data.get('country')}, Ref: {data.get('refNo')}",
            )
        except Exception as loan_error:
            print(f"Receivable loan sync failed for visa {visa_id}: {loan_error}")
        
        db.commit()
        cursor.close()
        db.close()
        return jsonify({'success': True, 'message': 'Visa updated successfully'})
    except Exception as e:
        return jsonify({'error': 'Failed to update visa', 'details': str(e)}), 500

@app.route('/api/visas/<int:visa_id>', methods=['DELETE'])
@jwt_required()
def delete_visa(visa_id):
    """Delete a visa record"""
    try:
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("DELETE FROM visas WHERE id = %s", (visa_id,))
        db.commit()
        cursor.close()
        db.close()
        
        return jsonify({'success': True, 'message': 'Visa deleted successfully'})
    except Exception as e:
        return jsonify({'error': 'Failed to delete visa', 'details': str(e)}), 500

@app.route('/api/visas', methods=['GET'])
@jwt_required()
def list_visas():
    db = get_db_connection()
    cursor = db.cursor()
    try:
        cursor.execute("SELECT * FROM visas ORDER BY created_at DESC")
        rows = cursor.fetchall()
        return jsonify({'visas': rows}), 200
    finally:
        cursor.close(); db.close()

# Reports: list cargo
@app.route('/api/cargo/<int:cargo_id>', methods=['GET'])
@jwt_required()
def get_cargo(cargo_id):
    """Get a specific cargo record"""
    try:
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM cargo WHERE id = %s", (cargo_id,))
        cargo = cursor.fetchone()
        cursor.close()
        db.close()
        
        if not cargo:
            return jsonify({'error': 'Cargo not found'}), 404
            
        return jsonify(cargo)
    except Exception as e:
        return jsonify({'error': 'Failed to fetch cargo', 'details': str(e)}), 500

@app.route('/api/cargo/<int:cargo_id>', methods=['PUT'])
@jwt_required()
def update_cargo(cargo_id):
    """Update a cargo record"""
    user_id = int(get_jwt_identity())
    try:
        data = request.get_json(force=True)
    except Exception as e:
        return jsonify({'error': 'Invalid JSON', 'details': str(e)}), 400
    
    # Extract fields with defaults
    try:
        customer_name = (data.get('customerName') or '').strip()
        country = (data.get('country') or '').strip()
        pickup_point = (data.get('pickupPoint') or '').strip()
        dropoff_point = (data.get('dropoffPoint') or '').strip()
        weight = float(data.get('weight') or 0)
        weight_cost = float(data.get('weightCost') or 0)
        net_cost = float(data.get('netCost') or 0)
        commission = float(data.get('commission') or 0)
        amount_paid = float(data.get('amountPaid') or 0)
        total_paid = float(data.get('totalPaid') or 0)
        requested_date = (data.get('requestedDate') or None) or None
        payment_status = (data.get('paymentStatus') or '').strip()
        if not payment_status:
            if amount_paid >= (net_cost + commission):
                payment_status = 'Paid'
            elif amount_paid > 0:
                payment_status = 'Partially Paid'
            else:
                payment_status = 'Unpaid'
        payment_method = (data.get('paymentMethod') or '').strip()
        transaction_ref = (data.get('transactionRef') or '').strip()
        ref_no = (data.get('refNo') or '').strip()
        contact_person_name = (data.get('contactPersonName') or '').strip()
        telephone = (data.get('telephone') or '').strip()
        remarks = (data.get('remarks') or '').strip()
    except Exception as e:
        return jsonify({'error': 'Invalid field types', 'details': str(e)}), 400

    if not customer_name:
        return jsonify({'error': 'Customer name is required'}), 400

    def to_date(d):
        if not d:
            return None
        return d[:10]

    try:
        db = get_db_connection()
        cursor = db.cursor()
        
        # Check if cargo exists
        cursor.execute("SELECT payment_status FROM cargo WHERE id = %s", (cargo_id,))
        old_cargo = cursor.fetchone()
        if not old_cargo:
            cursor.close()
            db.close()
            return jsonify({'error': 'Cargo not found'}), 404
        
        # Get the old status safely
        try:
            if isinstance(old_cargo, dict):
                old_status = old_cargo.get('payment_status', 'Unknown')
            else:
                old_status = old_cargo[0] if old_cargo and len(old_cargo) > 0 else 'Unknown'
        except (IndexError, TypeError, KeyError) as e:
            old_status = 'Unknown'
        
        # Update the cargo
        cursor.execute("""
            UPDATE cargo SET 
                customer_name = %s, country = %s, pickup_point = %s, dropoff_point = %s,
                weight = %s, weight_cost = %s, net_cost = %s, commission = %s, total_paid = %s, amount_paid = %s,
                requested_date = %s, payment_status = %s, payment_method = %s, 
                transaction_ref = %s, ref_no = %s, contact_person_name = %s, 
                telephone = %s, remarks = %s, updated_at = NOW()
            WHERE id = %s
        """, (
            customer_name, country, pickup_point, dropoff_point, weight, weight_cost, net_cost, commission, 
            total_paid, amount_paid, to_date(requested_date), payment_status, 
            payment_method, transaction_ref, ref_no, contact_person_name, 
            telephone, remarks, cargo_id
        ))
        
        # Always sync receivable state from current payment values.
        try:
            sync_receivable_loan_for_transaction(
                db=db,
                cursor=cursor,
                user_id=user_id,
                transaction_type='Cargo',
                transaction_id=cargo_id,
                customer_name=customer_name,
                total_amount=(net_cost + commission),
                amount_paid=amount_paid,
                due_date=to_date(requested_date),
                notes=f"From: {pickup_point} to {dropoff_point}, Ref: {ref_no}",
            )
        except Exception as loan_error:
            print(f"Receivable loan sync failed for cargo {cargo_id}: {loan_error}")
        
        db.commit()
        cursor.close()
        db.close()
        return jsonify({'success': True, 'message': 'Cargo updated successfully'})
    except Exception as e:
        try:
            cursor.close()
            db.close()
        except Exception:
            pass
        return jsonify({'error': 'DB error while updating cargo', 'details': str(e)}), 500

@app.route('/api/cargo/<int:cargo_id>', methods=['DELETE'])
@jwt_required()
def delete_cargo(cargo_id):
    """Delete a cargo record"""
    try:
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("DELETE FROM cargo WHERE id = %s", (cargo_id,))
        db.commit()
        cursor.close()
        db.close()
        
        return jsonify({'success': True, 'message': 'Cargo deleted successfully'})
    except Exception as e:
        return jsonify({'error': 'Failed to delete cargo', 'details': str(e)}), 500

@app.route('/api/cargo', methods=['GET'])
@jwt_required()
def list_cargo():
    db = get_db_connection()
    cursor = db.cursor()
    try:
        cursor.execute("SELECT * FROM cargo ORDER BY created_at DESC")
        rows = cursor.fetchall()
        return jsonify({'cargo': rows}), 200
    finally:
        cursor.close(); db.close()

# Transport API - Get individual transport record
@app.route('/api/transport/<int:transport_id>', methods=['GET'])
@jwt_required()
def get_transport(transport_id):
    """Get a specific transport record"""
    try:
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("""
            SELECT id, customer_name, agency_ref, pickup_point, dropoff_point, 
                   cost, commission, total, date, payment_status, payment_method, 
                   transaction_ref, telephone, vehicle, created_at
            FROM transport 
            WHERE id = %s
        """, (transport_id,))
        transport = cursor.fetchone()
        cursor.close()
        db.close()
        
        if not transport:
            return jsonify({'error': 'Transport record not found'}), 404
            
        return jsonify(transport)
    except Exception as e:
        return jsonify({'error': 'Failed to fetch transport', 'details': str(e)}), 500

# Transport API - Update transport record
@app.route('/api/transport/<int:transport_id>', methods=['PUT'])
@jwt_required()
def update_transport(transport_id):
    """Update a transport record"""
    user_id = int(get_jwt_identity())
    
    def to_date(d):
        if not d:
            return None
        return d[:10]
    
    try:
        data = request.get_json()
        db = get_db_connection()
        cursor = db.cursor()
        
        # Get old payment status
        cursor.execute("SELECT payment_status, cost, commission FROM transport WHERE id = %s", (transport_id,))
        old_transport = cursor.fetchone()
        if not old_transport:
            cursor.close()
            db.close()
            return jsonify({'error': 'Transport not found'}), 404
        
        # Get the old status safely - handle both tuple and dict results
        try:
            if isinstance(old_transport, dict):
                old_status = old_transport.get('payment_status', 'Unknown')
                cost = old_transport.get('cost', 0)
                commission = old_transport.get('commission', 0)
            else:
                old_status = old_transport[0] if old_transport and len(old_transport) > 0 else 'Unknown'
                cost = old_transport[1] if old_transport and len(old_transport) > 1 else 0
                commission = old_transport[2] if old_transport and len(old_transport) > 2 else 0
        except (IndexError, TypeError, KeyError) as e:
            old_status = 'Unknown'
            cost = 0
            commission = 0
        
        # Auto-determine new payment status based on CURRENT update amounts
        amount_paid = float(data.get('amountPaid') or 0)
        cost_float = float(data.get('cost') or cost or 0)
        commission_float = float(data.get('commission') or commission or 0)
        if amount_paid >= (cost_float + commission_float):
            new_status = 'Paid'
        elif amount_paid > 0:
            new_status = 'Partially Paid'
        else:
            new_status = 'Unpaid'
        
        cursor.execute("""
            UPDATE transport SET 
                customer_name = %s, agency_ref = %s, pickup_point = %s, dropoff_point = %s, 
                cost = %s, commission = %s, total = %s, total_paid = %s, amount_paid = %s, date = %s, payment_status = %s, 
                payment_method = %s, transaction_ref = %s, telephone = %s, vehicle = %s
            WHERE id = %s
        """, (
            data.get('customerName'),
            data.get('agencyRef'),
            data.get('pickup'),
            data.get('dropoff'),
            data.get('cost'),
            data.get('commission'),
            data.get('total'),
            data.get('totalPaid'),
            data.get('amountPaid'),
            data.get('date'),
            new_status,
            data.get('paymentMethod'),
            data.get('transactionRef'),
            data.get('telephone'),
            data.get('vehicle'),
            transport_id
        ))
        
        # Always sync receivable state from current payment values.
        try:
            sync_receivable_loan_for_transaction(
                db=db,
                cursor=cursor,
                user_id=user_id,
                transaction_type='Transport',
                transaction_id=transport_id,
                customer_name=data.get('customerName'),
                total_amount=(cost_float + commission_float),
                amount_paid=amount_paid,
                due_date=to_date(data.get('date')),
                notes=f"From: {data.get('pickup')} to {data.get('dropoff')}, Vehicle: {data.get('vehicle')}",
            )
        except Exception as loan_error:
            print(f"Receivable loan sync failed for transport {transport_id}: {loan_error}")
        
        db.commit()
        cursor.close()
        db.close()
        return jsonify({'success': True, 'message': 'Transport updated successfully'})
    except Exception as e:
        return jsonify({'error': 'Failed to update transport', 'details': str(e)}), 500

# Transport API - Delete transport record
@app.route('/api/transport/<int:transport_id>', methods=['DELETE'])
@jwt_required()
def delete_transport(transport_id):
    """Delete a transport record"""
    try:
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("DELETE FROM transport WHERE id = %s", (transport_id,))
        db.commit()
        cursor.close()
        db.close()
        return jsonify({'success': True, 'message': 'Transport deleted successfully'})
    except Exception as e:
        return jsonify({'error': 'Failed to delete transport', 'details': str(e)}), 500

# Reports: list transport
@app.route('/api/transport', methods=['GET'])
@jwt_required()
def list_transport():
    db = get_db_connection()
    cursor = db.cursor()
    try:
        cursor.execute("SELECT * FROM transport ORDER BY created_at DESC")
        rows = cursor.fetchall()
        return jsonify({'transport': rows}), 200
    finally:
        cursor.close(); db.close()

# Recent Activities API
@app.route('/api/recent-activities', methods=['GET'])
@jwt_required()
def get_recent_activities():
    """Get recent activities from all modules (tickets, visas, cargo, transport)"""
    try:
        db = get_db_connection()
        cursor = db.cursor()
        
        activities = []
        
        # Get recent tickets
        cursor.execute("""
            SELECT 
                id, 'Flight' as type, names as customer, 
                created_at as date, payment_status as status, total_paid as amount
            FROM tickets 
            WHERE created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
            ORDER BY created_at DESC 
            LIMIT 10
        """)
        tickets = cursor.fetchall()
        for ticket in tickets:
            activities.append({
                'id': f"T{ticket['id']}",
                'type': ticket['type'],
                'customer': ticket['customer'],
                'date': ticket['date'].strftime('%Y-%m-%d') if ticket['date'] else '',
                'status': ticket['status'],
                'amount': f"${ticket['amount']}" if ticket['amount'] else '$0'
            })
        
        # Get recent visas
        cursor.execute("""
            SELECT 
                id, 'Visa' as type, customer_name as customer,
                created_at as date, payment_status as status, total_paid as amount
            FROM visas 
            WHERE created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
            ORDER BY created_at DESC 
            LIMIT 10
        """)
        visas = cursor.fetchall()
        for visa in visas:
            activities.append({
                'id': f"V{visa['id']}",
                'type': visa['type'],
                'customer': visa['customer'],
                'date': visa['date'].strftime('%Y-%m-%d') if visa['date'] else '',
                'status': visa['status'],
                'amount': f"${visa['amount']}" if visa['amount'] else '$0'
            })
        
        # Get recent cargo
        cursor.execute("""
            SELECT 
                id, 'Cargo' as type, customer_name as customer,
                created_at as date, payment_status as status, total_paid as amount
            FROM cargo 
            WHERE created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
            ORDER BY created_at DESC 
            LIMIT 10
        """)
        cargo = cursor.fetchall()
        for item in cargo:
            activities.append({
                'id': f"C{item['id']}",
                'type': item['type'],
                'customer': item['customer'],
                'date': item['date'].strftime('%Y-%m-%d') if item['date'] else '',
                'status': item['status'],
                'amount': f"${item['amount']}" if item['amount'] else '$0'
            })
        
        # Get recent transport
        cursor.execute("""
            SELECT 
                id, 'Vehicle' as type, customer_name as customer,
                created_at as date, payment_status as status, total as amount
            FROM transport 
            WHERE created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
            ORDER BY created_at DESC 
            LIMIT 10
        """)
        transport = cursor.fetchall()
        for item in transport:
            activities.append({
                'id': f"TR{item['id']}",
                'type': item['type'],
                'customer': item['customer'],
                'date': item['date'].strftime('%Y-%m-%d') if item['date'] else '',
                'status': item['status'],
                'amount': f"${item['amount']}" if item['amount'] else '$0'
            })
        
        # Sort all activities by date (most recent first) and limit to 10
        activities.sort(key=lambda x: x['date'], reverse=True)
        activities = activities[:10]
        
        cursor.close()
        db.close()
        
        return jsonify({'activities': activities})
        
    except Exception as e:
        return jsonify({'error': 'Failed to fetch recent activities', 'details': str(e)}), 500

# ---------- FINANCIAL API: Expenses ----------
@app.route('/api/expenses', methods=['GET'])
@jwt_required()
def list_expenses():
    db = None
    cursor = None
    try:
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM expenses ORDER BY expense_date DESC, created_at DESC")
        rows = cursor.fetchall()
        return jsonify({'expenses': rows}), 200
    except Exception as e:
        logger.error(f"Error in list_expenses: {e}")
        return jsonify({'error': 'Failed to load expenses', 'details': str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()

@app.route('/api/expenses', methods=['POST'])
@jwt_required()
def create_expense():
    user_id = int(get_jwt_identity())
    try:
        data = request.get_json(force=True)
    except Exception as e:
        return jsonify({'error': 'Invalid JSON', 'details': str(e)}), 400

    def to_date(d):
        if not d:
            return None
        return d[:10]

    expense_date = to_date((data.get('date') or None))
    category = (data.get('category') or '').strip() or None
    description = (data.get('description') or '').strip() or None
    try:
        quantity = int(float(data.get('quantity') or 1))
        amount = float(data.get('amount') or 0)
    except Exception:
        return jsonify({'error': 'quantity must be integer and amount must be a number'}), 400

    db = None
    cursor = None
    try:
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute(
            """
            INSERT INTO expenses (expense_date, category, description, quantity, amount, created_by)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (expense_date, category, description, quantity, amount, user_id)
        )
        db.commit()
        new_id = cursor.lastrowid
        cursor.execute("SELECT * FROM expenses WHERE id = %s", (new_id,))
        row = cursor.fetchone()
        return jsonify({'success': True, 'expense': row}), 201
    except Exception as e:
        if db:
            db.rollback()
        logger.error(f"Error creating expense: {e}")
        return jsonify({'error': 'DB error while saving expense', 'details': str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()

# Update an expense
@app.route('/api/expenses/<int:item_id>', methods=['PUT'])
@jwt_required()
def update_expense(item_id: int):
    try:
        data = request.get_json(force=True)
    except Exception as e:
        return jsonify({'error': 'Invalid JSON', 'details': str(e)}), 400

    def to_date(d):
        if not d:
            return None
        return d[:10]

    expense_date = to_date((data.get('date') or None))
    category = (data.get('category') or '').strip() or None
    description = (data.get('description') or '').strip() or None
    try:
        quantity = int(float(data.get('quantity') or 1))
        amount = float(data.get('amount') or 0)
    except Exception:
        return jsonify({'error': 'quantity must be integer and amount must be a number'}), 400

    try:
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute(
            """
            UPDATE expenses SET expense_date=%s, category=%s, description=%s, quantity=%s, amount=%s
            WHERE id=%s
            """,
            (expense_date, category, description, quantity, amount, item_id)
        )
        db.commit()
        cursor.close()
        cursor2 = db.cursor()
        cursor2.execute("SELECT * FROM expenses WHERE id=%s", (item_id,))
        row = cursor2.fetchone()
        cursor2.close(); db.close()
        if not row:
            return jsonify({'error':'Not found'}), 404
        return jsonify({'success': True, 'expense': row}), 200
    except Exception as e:
        try: db.rollback()
        except Exception: pass
        return jsonify({'error': 'DB error while updating expense', 'details': str(e)}), 500

# Delete an expense
@app.route('/api/expenses/<int:item_id>', methods=['DELETE'])
@jwt_required()
def delete_expense(item_id: int):
    db = get_db_connection()
    cursor = db.cursor()
    try:
        cursor.execute("DELETE FROM expenses WHERE id=%s", (item_id,))
        db.commit()
        return jsonify({'success': True}), 200
    except Exception as e:
        try: db.rollback()
        except Exception: pass
        return jsonify({'error': 'DB error while deleting expense', 'details': str(e)}), 500
    finally:
        cursor.close(); db.close()

# ---------- FINANCIAL API: Investments ----------
@app.route('/api/investments', methods=['GET'])
@jwt_required()
def list_investments():
    db = None
    cursor = None
    try:
        db = get_db_connection()
        cursor = db.cursor()
        
        # Ensure investments table has correct schema
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS investments (
                id INT AUTO_INCREMENT PRIMARY KEY,
                invest_date DATE DEFAULT NULL,
                name VARCHAR(255) NOT NULL DEFAULT '',
                amount DECIMAL(12,2) DEFAULT 0.00,
                required_amount DECIMAL(12,2) DEFAULT 0.00,
                requested_company VARCHAR(255) DEFAULT NULL,
                amount_paid DECIMAL(12,2) DEFAULT 0.00,
                amount_remaining DECIMAL(12,2) DEFAULT 0.00,
                required_interest DECIMAL(6,2) DEFAULT 0.00,
                status VARCHAR(50) DEFAULT 'Not Paid',
                notes TEXT,
                created_by INT DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Add missing columns if they don't exist
        columns_to_add = [
            ("name", "VARCHAR(255) NOT NULL DEFAULT ''"),
            ("required_amount", "DECIMAL(12,2) DEFAULT 0.00"),
            ("requested_company", "VARCHAR(255) DEFAULT NULL"),
            ("amount_paid", "DECIMAL(12,2) DEFAULT 0.00"),
            ("amount_remaining", "DECIMAL(12,2) DEFAULT 0.00"),
            ("required_interest", "DECIMAL(6,2) DEFAULT 0.00"),
            ("status", "VARCHAR(50) DEFAULT 'Not Paid'"),
            ("notes", "TEXT"),
            ("created_by", "INT DEFAULT NULL"),
            ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        ]
        
        for column_name, column_def in columns_to_add:
            try:
                cursor.execute(f"ALTER TABLE investments ADD COLUMN {column_name} {column_def}")
            except Exception:
                pass
        
        db.commit()
        
        cursor.execute("SELECT * FROM investments ORDER BY invest_date DESC, created_at DESC")
        rows = cursor.fetchall()
        return jsonify({'investments': rows}), 200
    except Exception as e:
        logger.error(f"Error in list_investments: {e}")
        return jsonify({'error': 'Failed to load investments', 'details': str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()

@app.route('/api/returned-investments', methods=['GET'])
@jwt_required()
def list_returned_investments():
    """Get all investments with status 'Paid' (returned investments)"""
    db = None
    cursor = None
    try:
        db = get_db_connection()
        cursor = db.cursor()
        
        # Get investments with status 'Paid'
        cursor.execute("""
            SELECT 
                id,
                invest_date as investment_date,
                name as investor_name,
                requested_company as company,
                amount as original_amount,
                amount_paid,
                required_interest as interest_rate,
                status,
                notes,
                created_at
            FROM investments 
            WHERE status = 'Paid' 
            ORDER BY invest_date DESC, created_at DESC
        """)
        rows = cursor.fetchall()
        return jsonify({'returnedInvestments': rows}), 200
    except Exception as e:
        logger.error(f"Error in list_returned_investments: {e}")
        return jsonify({'error': 'Failed to load returned investments', 'details': str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()

@app.route('/api/investments', methods=['POST'])
@jwt_required()
def create_investment():
    user_id = int(get_jwt_identity())
    try:
        data = request.get_json(force=True)
    except Exception as e:
        return jsonify({'error': 'Invalid JSON', 'details': str(e)}), 400

    def to_date(d):
        if not d:
            return None
        # Handle different date formats
        d = str(d).strip()
        if len(d) >= 10:
            # If it's in MM/DD/YYYY format, convert to YYYY-MM-DD
            if '/' in d and len(d) == 10:
                try:
                    from datetime import datetime
                    date_obj = datetime.strptime(d, '%m/%d/%Y')
                    return date_obj.strftime('%Y-%m-%d')
                except:
                    pass
            # If it's already in YYYY-MM-DD format, return as is
            return d[:10]
        return None

    invest_date = to_date((data.get('date') or None))
    name = (data.get('name') or '').strip()
    requested_company = (data.get('requestedCompany') or '').strip() or None
    requested_status = (data.get('status') or 'Not Paid').strip() or 'Not Paid'
    status = requested_status
    notes = (data.get('notes') or '').strip() or None
    try:
        required_amount = float(data.get('requiredAmount') or 0)
        amount_paid = float(data.get('amountPaid') or 0)
        # Always compute remaining from required - paid
        amount_remaining = required_amount - amount_paid
        if amount_remaining < 0:
            amount_remaining = 0.0
        required_interest = float(data.get('requiredInterest') or 0)
    except Exception:
        return jsonify({'error': 'requiredAmount, amountPaid, amountRemaining, requiredInterest must be numbers'}), 400

    # Honor explicit Paid selection from UI by closing the investment.
    if requested_status.lower() == 'paid':
        amount_paid = required_amount
        amount_remaining = 0.0
        status = 'Paid'
    # Otherwise normalize from amounts.
    elif amount_remaining <= 0:
        amount_paid = required_amount
        amount_remaining = 0.0
        status = 'Paid'
    elif amount_paid > 0:
        status = 'Partial Paid'
    else:
        status = 'Not Paid'

    if not name:
        return jsonify({'error': 'name is required'}), 400

    db = None
    cursor = None
    try:
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute(
            """
            INSERT INTO investments (invest_date, name, amount, required_amount, requested_company, amount_paid, amount_remaining, required_interest, status, notes, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (invest_date, name, 0.00, required_amount, requested_company, amount_paid, amount_remaining, required_interest, status, notes, user_id)
        )
        db.commit()
        new_id = cursor.lastrowid
        cursor.execute("SELECT * FROM investments WHERE id = %s", (new_id,))
        row = cursor.fetchone()
        return jsonify({'success': True, 'investment': row}), 201
    except Exception as e:
        if db:
            db.rollback()
        logger.error(f"Error creating investment: {e}")
        return jsonify({'error': 'DB error while saving investment', 'details': str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()

@app.route('/api/investments/<item_id>', methods=['PUT'])
@jwt_required()
def update_investment(item_id):
    user_id = int(get_jwt_identity())
    
    # Convert item_id to integer and validate
    try:
        item_id = int(item_id)
        if item_id <= 0:
            return jsonify({'error': 'Invalid investment ID'}), 400
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid investment ID format'}), 400
    
    logger.info(f"Update investment request: item_id={item_id}, user_id={user_id}")
    
    try:
        data = request.get_json(force=True)
        logger.info(f"Update data received: {data}")
    except Exception as e:
        logger.error(f"JSON parsing error: {e}")
        return jsonify({'error': 'Invalid JSON', 'details': str(e)}), 400

    def to_date(d):
        if not d:
            return None
        # Handle different date formats
        d = str(d).strip()
        if len(d) >= 10:
            # If it's in MM/DD/YYYY format, convert to YYYY-MM-DD
            if '/' in d and len(d) == 10:
                try:
                    from datetime import datetime
                    date_obj = datetime.strptime(d, '%m/%d/%Y')
                    return date_obj.strftime('%Y-%m-%d')
                except:
                    pass
            # If it's already in YYYY-MM-DD format, return as is
            return d[:10]
        return None

    invest_date = to_date((data.get('date') or None))
    name = (data.get('name') or '').strip()
    requested_company = (data.get('requestedCompany') or '').strip() or None
    requested_status = (data.get('status') or 'Not Paid').strip() or 'Not Paid'
    status = requested_status
    notes = (data.get('notes') or '').strip() or None
    try:
        required_amount = float(data.get('requiredAmount') or 0)
        amount_paid = float(data.get('amountPaid') or 0)
        # Always compute remaining from required - paid on updates
        amount_remaining = required_amount - amount_paid
        if amount_remaining < 0:
            amount_remaining = 0.0
        required_interest = float(data.get('requiredInterest') or 0)
    except Exception:
        return jsonify({'error': 'requiredAmount, amountPaid, amountRemaining, requiredInterest must be numbers'}), 400

    # Honor explicit Paid selection from UI by closing the investment.
    if requested_status.lower() == 'paid':
        amount_paid = required_amount
        amount_remaining = 0.0
        status = 'Paid'
    # Otherwise normalize from amounts.
    elif amount_remaining <= 0:
        amount_paid = required_amount
        amount_remaining = 0.0
        status = 'Paid'
    elif amount_paid > 0:
        status = 'Partial Paid'
    else:
        status = 'Not Paid'

    if not name:
        return jsonify({'error': 'name is required'}), 400

    try:
        logger.info("Getting database connection...")
        db = get_db_connection()
        logger.info("Database connection established")
        cursor = db.cursor()
        logger.info("Database cursor created")
        
        # Check if status is changing to "Paid"
        logger.info(f"Checking current status for investment {item_id}")
        cursor.execute("SELECT status FROM investments WHERE id = %s", (item_id,))
        old_status_result = cursor.fetchone()
        old_status = old_status_result['status'] if old_status_result else None
        logger.info(f"Current status: {old_status}")
        
        # Update the investment with all available columns
        try:
            cursor.execute(
                """
                UPDATE investments
                SET invest_date=%s, name=%s, amount=%s, required_amount=%s, requested_company=%s,
                    amount_paid=%s, amount_remaining=%s, required_interest=%s, status=%s, notes=%s
                WHERE id=%s
                """,
                (invest_date, name, required_amount, required_amount, requested_company,
                 amount_paid, amount_remaining, required_interest, status, notes, item_id)
            )
            logger.info(f"Investment {item_id} updated successfully")
        except Exception as update_error:
            logger.error(f"Update query failed: {update_error}")
            logger.error(f"Update parameters: invest_date={invest_date}, name={name}, required_amount={required_amount}, requested_company={requested_company}, amount_paid={amount_paid}, amount_remaining={amount_remaining}, required_interest={required_interest}, status={status}, notes={notes}, item_id={item_id}")
            # Try a simpler update with just the essential fields
            try:
                cursor.execute(
                    """
                    UPDATE investments
                    SET amount=%s, amount_paid=%s, amount_remaining=%s, status=%s
                    WHERE id=%s
                    """,
                    (required_amount, amount_paid, amount_remaining, status, item_id)
                )
                logger.info(f"Investment {item_id} updated with simplified query")
            except Exception as simple_update_error:
                logger.error(f"Simple update also failed: {simple_update_error}")
                raise simple_update_error
        
        # If status changed to "Paid", keep in investments table for "Returned Investment" section
        if status == 'Paid' and old_status != 'Paid':
            # Just update the investment status to "Paid" - don't delete or transfer
            # This allows it to appear in the "Returned Investment" section
            db.commit()
            cursor.close()
            return jsonify({'success': True, 'message': 'Investment marked as paid and will appear in Returned Investment section', 'transferred': False}), 200
        
        # If status is "Partial Paid", create a receivable loan for the remaining amount
        elif status == 'Partial Paid' and amount_remaining > 0:
            # Check if receivable loan already exists for this investment
            cursor.execute("SELECT id FROM receivable_loans WHERE notes LIKE %s", (f"%Investment ID {item_id}%",))
            existing_loan = cursor.fetchone()
            
            if not existing_loan:
                # Create receivable loan for remaining amount
                cursor.execute(
                    """
                    INSERT INTO receivable_loans (issued_date, borrower, amount, due_date, status, notes, created_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (invest_date, name, amount_remaining, None, 'Not Paid', f"Remaining amount from Investment ID {item_id}. {notes or ''}", user_id)
                )
            else:
                # Update existing receivable loan amount
                loan_id = existing_loan['id'] if isinstance(existing_loan, dict) else existing_loan[0]
                cursor.execute(
                    "UPDATE receivable_loans SET amount=%s WHERE id=%s",
                    (amount_remaining, loan_id)
                )
        
        db.commit()
        
        # Get the updated investment data
        logger.info(f"Fetching updated investment data for ID: {item_id}")
        cursor.execute("SELECT * FROM investments WHERE id = %s", (item_id,))
        row = cursor.fetchone()
        logger.info(f"Fetched row: {row}")
        cursor.close()
        db.close()
        
        if not row:
            logger.error(f"Investment {item_id} not found after update")
            return jsonify({'error':'Not found'}), 404
        return jsonify({'success': True, 'investment': row}), 200
    except Exception as e:
        try: 
            if db:
                db.rollback()
        except Exception: 
            pass
        logger.error(f"Error updating investment {item_id}: {e}")
        logger.error(f"Exception type: {type(e)}")
        logger.error(f"Exception args: {e.args}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'DB error while updating investment', 'details': str(e), 'exception_type': str(type(e))}), 500

@app.route('/api/investments/<int:item_id>', methods=['GET'])
@jwt_required()
def get_investment(item_id: int):
    db = None
    cursor = None
    try:
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM investments WHERE id = %s", (item_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({'error': 'Investment not found'}), 404
        return jsonify({'investment': row}), 200
    except Exception as e:
        logger.error(f"Error loading investment {item_id}: {e}")
        return jsonify({'error': 'Failed to load investment', 'details': str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()

@app.route('/api/investments/<int:item_id>', methods=['DELETE'])
@jwt_required()
def delete_investment(item_id: int):
    db = get_db_connection()
    cursor = db.cursor()
    try:
        cursor.execute("DELETE FROM investments WHERE id=%s", (item_id,))
        db.commit()
        return jsonify({'success': True}), 200
    except Exception as e:
        try: db.rollback()
        except Exception: pass
        return jsonify({'error': 'DB error while deleting investment', 'details': str(e)}), 500
    finally:
        cursor.close(); db.close()


# ---------- FINANCIAL API: Receivable Loans ----------
@app.route('/api/receivable-loans', methods=['GET'])
@jwt_required()
def list_receivable_loans():
    db = None
    cursor = None
    try:
        logger.info("Starting list_receivable_loans function")
        db = get_db_connection()
        logger.info("Database connection successful")
        cursor = db.cursor()
        logger.info("Cursor created successfully")
        
        # Create receivable_loans table if it doesn't exist
        logger.info("Creating receivable_loans table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS receivable_loans (
                id INT AUTO_INCREMENT PRIMARY KEY,
                issued_date DATE DEFAULT NULL,
                borrower VARCHAR(255) NOT NULL,
                amount DECIMAL(12,2) DEFAULT 0.00,
                paid DECIMAL(12,2) DEFAULT 0.00,
                commission DECIMAL(12,2) DEFAULT 0.00,
                remaining_payment DECIMAL(12,2) DEFAULT 0.00,
                source VARCHAR(50) DEFAULT NULL,
                source_id INT DEFAULT NULL,
                borrower_name VARCHAR(255) NOT NULL,
                borrower_phone VARCHAR(50) NULL,
                loan_amount DECIMAL(12,2) NOT NULL,
                interest_rate DECIMAL(5,2) NULL,
                loan_date DATE NOT NULL,
                due_date DATE NOT NULL,
                status VARCHAR(50) DEFAULT 'Pending',
                notes TEXT,
                created_by INT DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            );
        """)
        logger.info("Table creation query executed")
        db.commit()
        logger.info("Table creation committed")

        # Add new columns for older databases.
        for ddl in [
            "ALTER TABLE receivable_loans ADD COLUMN paid DECIMAL(12,2) DEFAULT 0.00",
            "ALTER TABLE receivable_loans ADD COLUMN commission DECIMAL(12,2) DEFAULT 0.00",
            "ALTER TABLE receivable_loans ADD COLUMN remaining_payment DECIMAL(12,2) DEFAULT 0.00",
            "ALTER TABLE receivable_loans ADD COLUMN source VARCHAR(50) DEFAULT NULL",
            "ALTER TABLE receivable_loans ADD COLUMN source_id INT DEFAULT NULL",
        ]:
            try:
                cursor.execute(ddl)
                db.commit()
            except Exception:
                pass
        
        logger.info("Executing SELECT query...")
        # Support both legacy and newer receivable_loans schemas
        cursor.execute("SHOW COLUMNS FROM receivable_loans")
        column_rows = cursor.fetchall()
        existing_columns = set()
        for row in column_rows:
            if isinstance(row, dict):
                # DictCursor returns rows like {'Field': 'column_name', ...}
                field_name = row.get("Field")
                if field_name:
                    existing_columns.add(field_name)
            elif isinstance(row, (list, tuple)) and row:
                existing_columns.add(row[0])

        borrower_expr = (
            "COALESCE(borrower_name, borrower)"
            if "borrower_name" in existing_columns and "borrower" in existing_columns
            else ("borrower_name" if "borrower_name" in existing_columns else "borrower")
        )
        amount_expr = (
            "COALESCE(amount, loan_amount)"
            if "amount" in existing_columns and "loan_amount" in existing_columns
            else ("amount" if "amount" in existing_columns else "loan_amount")
        )
        paid_expr = "paid" if "paid" in existing_columns else "0"
        commission_expr = "commission" if "commission" in existing_columns else "0"
        remaining_expr = "remaining_payment" if "remaining_payment" in existing_columns else f"({amount_expr} - {paid_expr} - {commission_expr})"
        source_expr = "source" if "source" in existing_columns else "NULL"
        source_id_expr = "source_id" if "source_id" in existing_columns else "NULL"
        due_date_expr = "due_date" if "due_date" in existing_columns else "NULL"
        notes_expr = "notes" if "notes" in existing_columns else "NULL"
        created_at_expr = "created_at" if "created_at" in existing_columns else "NOW()"

        # Reconcile stale receivable rows:
        # If remaining/amount indicates fully settled, mark as Paid so they leave receivable list.
        try:
            if "remaining_payment" in existing_columns:
                cursor.execute("""
                    UPDATE receivable_loans
                    SET status = 'Paid'
                    WHERE status IN ('Unpaid', 'Pending', 'Partially Paid')
                      AND COALESCE(remaining_payment, 0) <= 0
                """)
            if "amount" in existing_columns:
                cursor.execute("""
                    UPDATE receivable_loans
                    SET status = 'Paid'
                    WHERE status IN ('Unpaid', 'Pending', 'Partially Paid')
                      AND COALESCE(amount, 0) <= 0
                """)
            db.commit()
        except Exception as reconcile_error:
            logger.warning(f"Receivable reconciliation skipped: {reconcile_error}")

        # Show only unpaid receivable loans (automatic filtering)
        cursor.execute(f"""
            SELECT
                id,
                issued_date,
                {borrower_expr} as borrower,
                {amount_expr} as amount,
                {amount_expr} as loan_amount,
                {paid_expr} as paid,
                {commission_expr} as commission,
                {remaining_expr} as remaining_payment,
                {source_expr} as source,
                {source_id_expr} as source_id,
                {due_date_expr} as due_date,
                status,
                {notes_expr} as notes,
                {created_at_expr} as created_at
            FROM receivable_loans
            WHERE status IN ('Unpaid', 'Pending', 'Partially Paid')
            ORDER BY created_at DESC
        """)
        rows = cursor.fetchall()
        logger.info(f"Query executed successfully, found {len(rows)} receivable loans")
        return jsonify({'receivableLoans': rows}), 200
    except Exception as e:
        logger.error(f"Error in list_receivable_loans: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to load receivable loans', 'details': str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()

@app.route('/api/receivable-loans', methods=['POST'])
@jwt_required()
def create_receivable_loan():
    """Manual creation of receivable loans is disabled. Only automatic transactions from booking forms are allowed."""
    return jsonify({
        'error': 'Manual creation of receivable loans is disabled. Receivable loans are automatically created from unpaid booking transactions (tickets, visas, cargo, transport).'
    }), 403

# Update a receivable loan with automatic movement logic
@app.route('/api/receivable-loans/<int:item_id>', methods=['PUT'])
@jwt_required()
def update_receivable_loan(item_id: int):
    """Update a receivable loan and handle automatic movement to received loans when status changes to Paid"""
    user_id = int(get_jwt_identity())
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        print(f"DEBUG: Received update request for loan ID {item_id}")
        print(f"DEBUG: Payload: {data}")
        
        db = get_db_connection()
        cursor = db.cursor(pymysql.cursors.DictCursor)  # Use dictionary cursor
        
        # Get the current loan data
        cursor.execute("SELECT * FROM receivable_loans WHERE id = %s", (item_id,))
        current_loan = cursor.fetchone()
        if not current_loan:
            print(f"DEBUG: Loan ID {item_id} not found")
            return jsonify({'error': 'Receivable loan not found'}), 404
        
        print(f"DEBUG: Current loan data: {current_loan}")
        # Use dictionary access instead of index
        old_status = current_loan.get('status', 'Unpaid')
        new_status = data.get('status', old_status)
        print(f"DEBUG: Status change: {old_status} -> {new_status}")
        
        # Handle empty date fields - convert empty strings to None
        issued_date = data.get('issuedDate') if data.get('issuedDate') else None
        due_date = data.get('dueDate') if data.get('dueDate') else None
        
        print(f"DEBUG: Processing dates - issued_date: {issued_date}, due_date: {due_date}")
        
        cursor.execute("DESCRIBE receivable_loans")
        columns = [row['Field'] for row in cursor.fetchall()]

        amount_value = float(data.get('amount') if data.get('amount') is not None else (current_loan.get('amount') or current_loan.get('loan_amount') or 0))
        paid_value = float(data.get('paid') if data.get('paid') is not None else (current_loan.get('paid') or 0))
        commission_value = float(data.get('commission') if data.get('commission') is not None else (current_loan.get('commission') or 0))
        remaining_value = round(amount_value - paid_value - commission_value, 2)
        if remaining_value < 0:
            remaining_value = 0.0

        requested_status = (data.get('status') or old_status or '').strip()

        # If user explicitly marks as Paid from UI, honor it and close the loan.
        if requested_status == 'Paid':
            paid_value = amount_value
            commission_value = 0.0
            remaining_value = 0.0
            new_status = 'Paid'
        # Otherwise auto-status from computed amounts.
        elif remaining_value <= 0:
            new_status = 'Paid'
        elif paid_value > 0:
            new_status = 'Partially Paid'
        elif requested_status in ('Unpaid', 'Pending'):
            new_status = requested_status
        elif new_status not in ('Unpaid', 'Pending'):
            new_status = 'Unpaid'

        borrower_column = 'borrower_name' if 'borrower_name' in columns else 'borrower'
        update_fields = [
            "issued_date = %s",
            f"{borrower_column} = %s",
            "amount = %s",
            "due_date = %s",
            "status = %s",
            "notes = %s",
        ]
        update_values = [
            issued_date,
            data.get('borrower'),
            amount_value,
            due_date,
            new_status,
            data.get('notes'),
        ]
        if 'paid' in columns:
            update_fields.append("paid = %s")
            update_values.append(paid_value)
        if 'commission' in columns:
            update_fields.append("commission = %s")
            update_values.append(commission_value)
        if 'remaining_payment' in columns:
            update_fields.append("remaining_payment = %s")
            update_values.append(remaining_value)
        if 'source' in columns and data.get('source'):
            update_fields.append("source = %s")
            update_values.append(str(data.get('source')).lower())
        if 'source_id' in columns and data.get('source_id'):
            update_fields.append("source_id = %s")
            update_values.append(int(data.get('source_id')))

        update_fields.append("updated_at = NOW()")
        update_values.append(item_id)

        cursor.execute(
            f"UPDATE receivable_loans SET {', '.join(update_fields)} WHERE id = %s",
            tuple(update_values)
        )
        print("Successfully updated receivable loan")
        
        transferred = False
        
        # If status changed to Paid, move to received loans
        if new_status == 'Paid' and old_status != 'Paid':
            print(f"Moving receivable loan {item_id} to received loans due to status change to Paid")
            
            # Transfer to received_loans - use minimal required columns
            try:
                # First, check what columns actually exist in received_loans table
                cursor.execute("DESCRIBE received_loans")
                columns = [row['Field'] for row in cursor.fetchall()]
                print(f"DEBUG: received_loans table columns: {columns}")
                
                # Build INSERT query based on available columns
                if 'lender_name' in columns and 'loan_amount' in columns and 'loan_date' in columns:
                    # Newer structure
                    cursor.execute("""
                        INSERT INTO received_loans (lender_name, loan_amount, loan_date, due_date, interest_rate, status, notes)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        data.get('borrower'),
                        data.get('amount'),
                        issued_date or '2024-01-01',
                        due_date or '2024-01-01',
                        0.00,
                        'Paid',
                        f"Payment received for receivable loan {item_id}. {data.get('notes', '')}"
                    ))
                    print("Successfully inserted with newer structure")
                elif 'lender' in columns and 'amount' in columns and 'received_date' in columns:
                    # Older structure
                    cursor.execute("""
                        INSERT INTO received_loans (lender, amount, received_date, due_date, interest_rate, status, notes)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        data.get('borrower'),
                        data.get('amount'),
                        issued_date or '2024-01-01',
                        due_date or '2024-01-01',
                        0.00,
                        'Paid',
                        f"Payment received for receivable loan {item_id}. {data.get('notes', '')}"
                    ))
                    print("Successfully inserted with older structure")
                else:
                    # Minimal structure - only required columns
                    cursor.execute("""
                        INSERT INTO received_loans (lender, amount, received_date, status, notes)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (
                        data.get('borrower'),
                        data.get('amount'),
                        issued_date or '2024-01-01',
                        'Paid',
                        f"Payment received for receivable loan {item_id}. {data.get('notes', '')}"
                    ))
                    print("Successfully inserted with minimal structure")
                    
            except Exception as e:
                print(f"Failed to insert into received_loans: {e}")
                # If all else fails, just delete from receivable_loans without moving to received_loans
                print("Note: Loan will be deleted from receivable_loans but not moved to received_loans due to table structure issues")
            
            # Update the original transaction status to 'Paid' for data consistency
            try:
                # Extract transaction type and ID from notes
                cursor.execute("SELECT notes FROM receivable_loans WHERE id = %s", (item_id,))
                loan_notes = cursor.fetchone()
                if loan_notes and loan_notes.get('notes'):
                    notes = loan_notes['notes']
                    print(f"DEBUG: Loan notes: {notes}")
                    
                    # Extract transaction type and ID
                    if 'Ticket ID' in notes:
                        ticket_id = notes.split('Ticket ID ')[1].split('.')[0]
                        print(f"DEBUG: Updating ticket {ticket_id} status to Paid")
                        cursor.execute("UPDATE tickets SET payment_status = 'Paid' WHERE id = %s", (ticket_id,))
                        print(f"Successfully updated ticket {ticket_id} status to Paid")
                        
                    elif 'Visa ID' in notes:
                        visa_id = notes.split('Visa ID ')[1].split('.')[0]
                        print(f"DEBUG: Updating visa {visa_id} status to Paid")
                        cursor.execute("UPDATE visas SET payment_status = 'Paid' WHERE id = %s", (visa_id,))
                        print(f"Successfully updated visa {visa_id} status to Paid")
                        
                    elif 'Cargo ID' in notes:
                        cargo_id = notes.split('Cargo ID ')[1].split('.')[0]
                        print(f"DEBUG: Updating cargo {cargo_id} status to Paid")
                        cursor.execute("UPDATE cargo SET payment_status = 'Paid' WHERE id = %s", (cargo_id,))
                        print(f"Successfully updated cargo {cargo_id} status to Paid")
                        
                    elif 'Transport ID' in notes:
                        transport_id = notes.split('Transport ID ')[1].split('.')[0]
                        print(f"DEBUG: Updating transport {transport_id} status to Paid")
                        cursor.execute("UPDATE transport SET payment_status = 'Paid' WHERE id = %s", (transport_id,))
                        print(f"Successfully updated transport {transport_id} status to Paid")
                        
            except Exception as update_error:
                print(f"Failed to update original transaction status: {update_error}")
                # Continue with the loan transfer even if original transaction update fails
            
            # Delete from receivable_loans
            cursor.execute("DELETE FROM receivable_loans WHERE id = %s", (item_id,))
            transferred = True
            print(f"Successfully moved receivable loan {item_id} to received loans")
        
        db.commit()
        cursor.close()
        db.close()
        
        return jsonify({
            'success': True,
            'transferred': transferred,
            'message': 'Loan moved to Received Loans section!' if transferred else 'Receivable loan updated successfully'
        }), 200
        
    except Exception as e:
        print(f"Error updating receivable loan: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to update receivable loan', 'details': str(e)}), 500

# Delete a receivable loan (disabled - only automatic management allowed)
@app.route('/api/receivable-loans/<int:item_id>', methods=['GET'])
@jwt_required()
def get_receivable_loan(item_id: int):
    """Get a specific receivable loan"""
    db = get_db_connection()
    cursor = db.cursor()
    try:
        cursor.execute("SELECT * FROM receivable_loans WHERE id = %s", (item_id,))
        loan = cursor.fetchone()
        if not loan:
            return jsonify({'error': 'Receivable loan not found'}), 404
        return jsonify(loan), 200
    finally:
        cursor.close(); db.close()

@app.route('/receivable-loans/<int:item_id>/edit', methods=['GET'])
def receivable_loan_edit_redirect(item_id: int):
    """
    Redirect receivable-loan edit action to the correct source module edit UI.
    Uses source/source_id when available, with notes parsing fallback for legacy rows.
    """
    db = get_db_connection()
    cursor = db.cursor()
    try:
        cursor.execute("SELECT id, source, source_id, notes FROM receivable_loans WHERE id = %s", (item_id,))
        loan = cursor.fetchone()
        if not loan:
            return redirect(url_for('admin_dashboard', section='financialSection', loan_error='not_found'))

        source = (loan.get('source') or '').strip().lower() if isinstance(loan, dict) else ''
        source_id = loan.get('source_id') if isinstance(loan, dict) else None

        # Fallback for old records that only store source in notes.
        if (not source or not source_id) and isinstance(loan, dict):
            import re
            notes = loan.get('notes') or ''
            match = re.search(r'(Ticket|Visa|Cargo|Transport)\s+ID\s+(\d+)', notes, re.IGNORECASE)
            if match:
                source = match.group(1).lower()
                source_id = int(match.group(2))

        source_map = {
            'ticket': 'ticketSalesSection',
            'visa': 'visaProcessingSection',
            'cargo': 'cargoSection',
            'transport': 'transportSection',
        }
        target_section = source_map.get(source)
        if not target_section or not source_id:
            return redirect(url_for('admin_dashboard', section='financialSection', loan_error='unknown_source'))

        return redirect(url_for(
            'admin_dashboard',
            section=target_section,
            edit_source=source,
            edit_id=source_id
        ))
    finally:
        cursor.close(); db.close()

@app.route('/api/receivable-loans/<int:item_id>', methods=['DELETE'])
@jwt_required()
def delete_receivable_loan(item_id: int):
    """Delete a receivable loan"""
    db = get_db_connection()
    cursor = db.cursor()
    try:
        # Check if the loan exists
        cursor.execute("SELECT * FROM receivable_loans WHERE id = %s", (item_id,))
        loan = cursor.fetchone()
        if not loan:
            return jsonify({'error': 'Receivable loan not found'}), 404
        
        # Delete the loan
        cursor.execute("DELETE FROM receivable_loans WHERE id = %s", (item_id,))
        db.commit()
        
        return jsonify({'success': True, 'message': 'Receivable loan deleted successfully'}), 200
    except Exception as e:
        db.rollback()
        return jsonify({'error': 'Failed to delete receivable loan', 'details': str(e)}), 500
    finally:
        cursor.close(); db.close()

# ---------- FINANCIAL API: Received Loans ----------
@app.route('/api/received-loans', methods=['GET'])
@jwt_required()
def list_received_loans():
    db = None
    cursor = None
    try:
        logger.info("Starting list_received_loans function")
        db = get_db_connection()
        logger.info("Database connection successful")
        cursor = db.cursor()
        logger.info("Cursor created successfully")
        
        # Create received_loans table if it doesn't exist
        logger.info("Creating received_loans table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS received_loans (
                id INT AUTO_INCREMENT PRIMARY KEY,
                received_date DATE DEFAULT NULL,
                lender VARCHAR(255) NOT NULL,
                lender_name VARCHAR(255) DEFAULT NULL,
                amount DECIMAL(12,2) DEFAULT 0.00,
                loan_amount DECIMAL(12,2) DEFAULT 0.00,
                loan_date DATE DEFAULT NULL,
                due_date DATE DEFAULT NULL,
                interest_rate DECIMAL(6,2) DEFAULT 0.00,
                status VARCHAR(50) DEFAULT 'Active',
                notes TEXT,
                created_by INT DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Add missing columns if they don't exist
        try:
            cursor.execute("ALTER TABLE received_loans ADD COLUMN lender_name VARCHAR(255) DEFAULT NULL")
            db.commit()
        except Exception:
            pass  # Column already exists
        
        try:
            cursor.execute("ALTER TABLE received_loans ADD COLUMN loan_amount DECIMAL(12,2) DEFAULT 0.00")
            db.commit()
        except Exception:
            pass  # Column already exists
            
        try:
            cursor.execute("ALTER TABLE received_loans ADD COLUMN loan_date DATE DEFAULT NULL")
            db.commit()
        except Exception:
            pass  # Column already exists
        logger.info("Table creation query executed")
        db.commit()
        logger.info("Table creation committed")
        
        # Backfill missing received-loan entries from paid transactions
        sync_received_loans_from_paid_transactions(db, cursor)
        db.commit()

        logger.info("Executing SELECT query...")
        cursor.execute("""
            SELECT 
                id,
                COALESCE(loan_date, created_at) as loan_date,
                COALESCE(lender_name, lender) as lender_name,
                COALESCE(loan_amount, amount) as loan_amount,
                COALESCE(loan_amount, amount) as amount,
                due_date,
                status,
                notes,
                created_at
            FROM received_loans 
            WHERE status = 'Paid'
            ORDER BY COALESCE(loan_date, created_at) DESC, created_at DESC
        """)
        rows = cursor.fetchall()
        logger.info(f"Query executed successfully, found {len(rows)} rows")
        return jsonify({'receivedLoans': rows}), 200
    except Exception as e:
        logger.error(f"Error in list_received_loans: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to load received loans', 'details': str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()

@app.route('/api/received-loans', methods=['POST'])
@jwt_required()
def create_received_loan():
    user_id = int(get_jwt_identity())
    try:
        data = request.get_json(force=True)
    except Exception as e:
        return jsonify({'error': 'Invalid JSON', 'details': str(e)}), 400

    def to_date(d):
        if not d:
            return None
        return d[:10]

    received_date = to_date((data.get('receivedDate') or None))
    lender = (data.get('lender') or '').strip()
    due_date = to_date((data.get('dueDate') or None))
    notes = (data.get('notes') or '').strip() or None
    status = (data.get('status') or 'Active').strip() or 'Active'
    try:
        amount = float(data.get('amount') or 0)
        interest_rate = float(data.get('interestRate') or 0)
    except Exception:
        return jsonify({'error': 'amount and interestRate must be numbers'}), 400
    if not lender:
        return jsonify({'error': 'lender is required'}), 400

    try:
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute(
            """
            INSERT INTO received_loans (received_date, lender_name, amount, loan_amount, due_date, interest_rate, status, notes, created_by)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (received_date, lender, amount, amount, due_date, interest_rate, status, notes, user_id)
        )
        db.commit()
        new_id = cursor.lastrowid
        cursor.close()
        cursor2 = db.cursor()
        cursor2.execute("SELECT * FROM received_loans WHERE id=%s", (new_id,))
        row = cursor2.fetchone()
        cursor2.close(); db.close()
        return jsonify({'success': True, 'receivedLoan': row}), 201
    except Exception as e:
        try: db.rollback()
        except Exception: pass
        return jsonify({'error': 'DB error while saving received loan', 'details': str(e)}), 500

# Update a received loan
@app.route('/api/received-loans/<int:item_id>', methods=['PUT'])
@jwt_required()
def update_received_loan(item_id: int):
    try:
        data = request.get_json(force=True)
        print(f"[DEBUG] Update received loan {item_id} with data: {data}")
    except Exception as e:
        print(f"[DEBUG] JSON parsing error: {e}")
        return jsonify({'error': 'Invalid JSON', 'details': str(e)}), 400

    def to_date(d):
        if not d:
            return None
        return d[:10]

    received_date = to_date((data.get('receivedDate') or None))
    lender = (data.get('lender') or '').strip()
    due_date = to_date((data.get('dueDate') or None))
    notes = (data.get('notes') or '').strip() or None
    status = (data.get('status') or 'Active').strip() or 'Active'
    try:
        amount = float(data.get('amount') or 0)
        interest_rate = float(data.get('interestRate') or 0)
    except Exception:
        return jsonify({'error': 'amount and interestRate must be numbers'}), 400
    if not lender:
        return jsonify({'error': 'lender is required'}), 400

    try:
        db = get_db_connection()
        cursor = db.cursor()
        print(f"[DEBUG] Updating received loan {item_id} with values: received_date={received_date}, lender={lender}, amount={amount}, due_date={due_date}, interest_rate={interest_rate}, status={status}, notes={notes}")
        cursor.execute(
            """
            UPDATE received_loans 
            SET received_date=%s, lender_name=%s, amount=%s, loan_amount=%s, due_date=%s, interest_rate=%s, status=%s, notes=%s
            WHERE id=%s
            """,
            (received_date, lender, amount, amount, due_date, interest_rate, status, notes, item_id)
        )
        affected_rows = cursor.rowcount
        print(f"[DEBUG] Update affected {affected_rows} rows")
        db.commit()
        cursor.close()
        cursor2 = db.cursor()
        cursor2.execute("SELECT * FROM received_loans WHERE id=%s", (item_id,))
        row = cursor2.fetchone()
        cursor2.close(); db.close()
        if not row:
            print(f"[DEBUG] No row found after update for id {item_id}")
            return jsonify({'error':'Not found'}), 404
        print(f"[DEBUG] Update successful, returning row: {row}")
        return jsonify({'success': True, 'receivedLoan': row}), 200
    except Exception as e:
        print(f"[DEBUG] Database error: {e}")
        try: db.rollback()
        except Exception: pass
        return jsonify({'error': 'DB error while updating received loan', 'details': str(e)}), 500

# Delete a received loan
@app.route('/api/received-loans/<int:item_id>', methods=['DELETE'])
@jwt_required()
def delete_received_loan(item_id: int):
    db = get_db_connection()
    cursor = db.cursor()
    try:
        cursor.execute("SELECT notes FROM received_loans WHERE id=%s", (item_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({'error': 'Received loan not found'}), 404

        notes = row['notes'] if isinstance(row, dict) else row[0]

        # If deleting an AUTO_SYNC row, store exclusion so it doesn't reappear.
        if notes and str(notes).startswith("AUTO_SYNC "):
            # Expected format: AUTO_SYNC <Type> ID <id>
            try:
                parts = str(notes).split()
                source_type = parts[1]
                source_id = int(parts[3])
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS received_loans_exclusions (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        source_type VARCHAR(50) NOT NULL,
                        source_id INT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE KEY unique_source_item (source_type, source_id)
                    )
                """)
                cursor.execute(
                    """
                    INSERT INTO received_loans_exclusions (source_type, source_id)
                    VALUES (%s, %s)
                    ON DUPLICATE KEY UPDATE source_type = VALUES(source_type)
                    """,
                    (source_type, source_id),
                )
            except Exception as parse_error:
                print(f"Warning: failed to parse AUTO_SYNC note for exclusion: {parse_error}")

        cursor.execute("DELETE FROM received_loans WHERE id=%s", (item_id,))
        db.commit()
        return jsonify({'success': True, 'message': 'Received loan deleted successfully'}), 200
    except Exception as e:
        try: db.rollback()
        except Exception: pass
        return jsonify({'error': 'DB error while deleting received loan', 'details': str(e)}), 500
    finally:
        cursor.close(); db.close()

# New: ensure user module permissions table exists
def ensure_user_module_permissions_table():
    """Create user module permissions table with MySQL syntax"""
    db = None
    cursor = None
    try:
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS user_module_permissions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                module_name VARCHAR(100) NOT NULL,
                has_access TINYINT(1) DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY unique_user_module (user_id, module_name)
            )
            """
        )
        db.commit()
        logger.info("User module permissions table ensured")
    except Exception as e:
        logger.error(f"Error creating user_module_permissions table: {e}")
        if db:
            db.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()

# ---------------- ADMIN USER MANAGEMENT ----------------

@app.route('/api/users', methods=['GET'])
@jwt_required()
@require_role('admin')
def list_users():
    """List all users (admin and super_admin only)"""
    db = None
    cursor = None
    try:
        db = get_db_connection()
        cursor = db.cursor()
        
        cursor.execute("""
            SELECT id, username, email, first_name, last_name, role, is_active, 
                   dashboard_access, created_at, updated_at, photo_url
            FROM users 
            ORDER BY created_at DESC
        """)
        users = cursor.fetchall()
        
        # Add module permissions for each user
        for user in users:
            try:
                cursor.execute("""
                    SELECT module_name, has_access 
                    FROM user_module_permissions 
                    WHERE user_id = %s
                """, (user['id'],))
                permissions = cursor.fetchall()
                user['module_permissions'] = {perm['module_name']: perm['has_access'] for perm in permissions}
            except Exception as e:
                logger.warning(f"Module permissions not found for user {user['id']}: {e}")
                # Set default permissions
                user['module_permissions'] = {
                    'tickets': True,
                    'visas': True,
                    'cargo': True,
                    'transport': True,
                    'financial': True
                }
        
        return jsonify({'users': users}), 200
    except Exception as e:
        logger.error(f"Error in list_users: {e}")
        return jsonify({'error': 'Failed to load users', 'details': str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()

@app.route('/api/users', methods=['POST'])
@jwt_required()
@require_admin()
def create_user():
    """Create a new user (admin only)"""
    logger.info("Create user endpoint called")
    try:
        data = request.get_json(force=True)
        logger.info(f"Received user data: {data}")
    except Exception as e:
        logger.error(f"Invalid JSON in create_user: {e}")
        return jsonify({'error': 'Invalid JSON', 'details': str(e)}), 400
    
    email = (data.get('email') or '').strip().lower()
    password = (data.get('password') or '').strip()
    first_name = (data.get('firstName') or '').strip()
    last_name = (data.get('lastName') or '').strip()
    role = (data.get('role') or 'sales').strip()
    dashboard_access = bool(data.get('dashboardAccess', True))  # Default to True
    
    # Validate role - only allow admin, sales, finance
    valid_roles = ['admin', 'sales', 'finance']
    if role not in valid_roles:
        return jsonify({'error': f'Invalid role. Must be one of: {", ".join(valid_roles)}'}), 400
    
    # Module permissions
    module_permissions = data.get('modulePermissions', {})
    tickets_access = bool(module_permissions.get('tickets', True))
    visas_access = bool(module_permissions.get('visas', True))
    cargo_access = bool(module_permissions.get('cargo', True))
    transport_access = bool(module_permissions.get('transport', True))
    financial_access = bool(module_permissions.get('financial', True))
    
    # Auto-generate username from email if not provided
    username = (data.get('username') or '').strip()
    if not username:
        username = email.split('@')[0]  # Use email prefix as username
    
    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400
    
    # Allow any role, but validate it's not empty
    if not role or len(role.strip()) == 0:
        return jsonify({'error': 'Role is required'}), 400
    
    # Get current user to check permissions
    current_user_id = int(get_jwt_identity())
    logger.info(f"Current user ID: {current_user_id}")
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("SELECT role FROM users WHERE id=%s", (current_user_id,))
    current_user = cursor.fetchone()
    
    if not current_user:
        logger.error(f"Current user {current_user_id} not found")
        cursor.close()
        db.close()
        return jsonify({'error': 'Current user not found'}), 404
    
    current_user_role = current_user['role']
    logger.info(f"Current user role: {current_user_role}")
    
    # Admin users cannot create Super Admin accounts
    if current_user_role == 'admin' and role == 'super_admin':
        logger.warning(f"Admin user {current_user_id} attempted to create super_admin")
        cursor.close()
        db.close()
        return jsonify({'error': 'Admin users cannot create Super Admin accounts'}), 403
    
    try:
        # Ensure user module permissions table exists
        ensure_user_module_permissions_table()
        
        # Don't create a new cursor - reuse the existing one
        hashed_password = generate_password_hash(password)
        logger.info(f"Creating user with email: {email}, role: {role}")
        
        # Check if email already exists
        cursor.execute("SELECT id FROM users WHERE email=%s", (email,))
        existing_user = cursor.fetchone()
        if existing_user:
            logger.warning(f"Email {email} already exists")
            cursor.close()
            db.close()
            return jsonify({'error': 'Email already exists'}), 400
        
        logger.info("Inserting new user into database")
        cursor.execute("""
            INSERT INTO users (username, email, password_hash, first_name, last_name, role, is_active, dashboard_access)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (username, email, hashed_password, first_name, last_name, role, 1, dashboard_access))
        db.commit()
        user_id = cursor.lastrowid
        logger.info(f"User created successfully with ID: {user_id}")
        
        # Log user creation (optional - don't fail if audit logging fails)
        try:
            current_user_id = int(get_jwt_identity())
            log_audit_event(
                user_id=current_user_id,
                action='CREATE_USER',
                resource='USER_MANAGEMENT',
                details=f"Created user {email} with role {role}",
                ip_address=get_client_ip()
            )
        except Exception as e:
            logger.warning(f"Failed to log user creation audit event: {e}")
            # Continue execution even if audit logging fails
        
        # Insert module permissions
        modules = [
            ('tickets', tickets_access),
            ('visas', visas_access),
            ('cargo', cargo_access),
            ('transport', transport_access),
            ('financial', financial_access)
        ]
        
        for module_name, has_access in modules:
            cursor.execute(
                "INSERT INTO user_module_permissions (user_id, module_name, has_access) VALUES (%s, %s, %s)",
                (user_id, module_name, has_access)
            )
        
        db.commit()
        cursor.close()
        
        # Return the created user with permissions
        cursor2 = db.cursor()
        cursor2.execute("SELECT * FROM users WHERE id=%s", (user_id,))
        user = cursor2.fetchone()
        
        # Get module permissions
        cursor2.execute("SELECT module_name, has_access FROM user_module_permissions WHERE user_id=%s", (user_id,))
        permissions = cursor2.fetchall()
        module_permissions = {perm[0]: perm[1] for perm in permissions}
        
        cursor2.close()
        db.close()
        
        # Format user data for response
        user_data = {
            'id': user[0],
            'username': user[1],
            'email': user[2],
            'first_name': user[3],
            'last_name': user[4],
            'role': user[6],
            'is_active': user[8],
            'module_permissions': module_permissions
        }
        
        return jsonify({'success': True, 'user': user_data}), 201
    except pymysql.err.IntegrityError as e:
        logger.error(f"Integrity error: {e}")
        if db:
            db.rollback()
        return jsonify({'error': 'Email already exists'}), 400
    except Exception as e:
        logger.error(f"Database error in create_user: {e}")
        if db:
            db.rollback()
        return jsonify({'error': 'Database error', 'details': str(e)}), 500
    finally:
        if 'cursor' in locals() and cursor:
            cursor.close()
        if 'cursor2' in locals() and cursor2:
            cursor2.close()
        if 'db' in locals() and db:
            db.close()

@app.route('/api/roles', methods=['GET'])
@jwt_required()
@require_role('super_admin')
def get_available_roles():
    """Get available roles (Super Admin only)"""
    try:
        # Define available roles with their hierarchy levels
        roles = {
            'super_admin': {'level': 3, 'name': 'Super Admin', 'description': 'Full system access'},
            'admin': {'level': 2, 'name': 'Admin', 'description': 'Administrative access'},
            'manager': {'level': 2.5, 'name': 'Manager', 'description': 'Management access'},
            'user': {'level': 1, 'name': 'User', 'description': 'Basic user access'},
            'moderator': {'level': 1.5, 'name': 'Moderator', 'description': 'Limited admin access'},
            'viewer': {'level': 0.5, 'name': 'Viewer', 'description': 'Read-only access'}
        }
        
        return jsonify({'roles': roles}), 200
    except Exception as e:
        return jsonify({'error': 'Failed to get roles', 'details': str(e)}), 500

@app.route('/api/users/<int:user_id>', methods=['PUT'])
@jwt_required()
@require_role('admin')
def update_user(user_id):
    """Update user information (admin only - super_admin cannot edit other users)"""
    try:
        data = request.get_json(force=True)
    except Exception as e:
        return jsonify({'error': 'Invalid JSON', 'details': str(e)}), 400
    
    # Get current user to check permissions
    current_user_id = int(get_jwt_identity())
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("SELECT role FROM users WHERE id=%s", (current_user_id,))
    current_user = cursor.fetchone()
    
    if not current_user:
        cursor.close()
        db.close()
        return jsonify({'error': 'Current user not found'}), 404
    
    current_user_role = current_user['role']
    
    # Super Admin cannot edit other user accounts
    if current_user_role == 'super_admin' and current_user_id != user_id:
        cursor.close()
        db.close()
        return jsonify({'error': 'Super Admin is not allowed to edit other user accounts, only view or delete them.'}), 403
    
    # Only admin can edit users (super_admin can only edit themselves)
    if current_user_role not in ['admin', 'super_admin']:
        cursor.close()
        db.close()
        return jsonify({'error': 'You do not have permission to edit users'}), 403
    
    # Only super_admin can change roles and deactivate users (when editing themselves)
    can_change_role = current_user['role'] == 'super_admin' and current_user_id == user_id
    
    # Build update query
    update_fields = []
    update_values = []
    
    if 'firstName' in data:
        update_fields.append("first_name = %s")
        update_values.append(data['firstName'])
    
    if 'lastName' in data:
        update_fields.append("last_name = %s")
        update_values.append(data['lastName'])
    
    if 'email' in data:
        update_fields.append("email = %s")
        update_values.append(data['email'].strip().lower())
    
    if can_change_role and 'role' in data:
        if data['role'] and len(data['role'].strip()) > 0:
            update_fields.append("role = %s")
            update_values.append(data['role'])
    
    if can_change_role and 'isActive' in data:
        update_fields.append("is_active = %s")
        update_values.append(bool(data['isActive']))
    
    if can_change_role and 'dashboardAccess' in data:
        update_fields.append("dashboard_access = %s")
        update_values.append(bool(data['dashboardAccess']))
    
    if not update_fields:
        cursor.close()
        db.close()
        return jsonify({'error': 'No valid fields to update'}), 400
    
    update_values.append(user_id)
    
    try:
        cursor.execute(f"""
            UPDATE users SET {', '.join(update_fields)}
            WHERE id = %s
        """, update_values)
        db.commit()
        cursor.close()
        
        # Return updated user
        cursor2 = db.cursor()
        cursor2.execute("SELECT * FROM users WHERE id=%s", (user_id,))
        user = cursor2.fetchone()
        cursor2.close()
        db.close()
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        return jsonify({'success': True, 'user': user}), 200
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Email already exists'}), 400
    except Exception as e:
        return jsonify({'error': 'Database error', 'details': str(e)}), 500

@app.route('/api/users/<int:user_id>/password', methods=['PUT'])
@jwt_required()
@require_role('admin')
def reset_user_password(user_id):
    """Reset user password (admin and super_admin only)"""
    try:
        data = request.get_json(force=True)
    except Exception as e:
        return jsonify({'error': 'Invalid JSON', 'details': str(e)}), 400
    
    new_password = (data.get('newPassword') or '').strip()
    if not new_password:
        return jsonify({'error': 'New password is required'}), 400
    
    try:
        db = get_db_connection()
        cursor = db.cursor()
        hashed_password = generate_password_hash(new_password)
        cursor.execute("UPDATE users SET password_hash = %s WHERE id = %s", (hashed_password, user_id))
        db.commit()
        cursor.close()
        db.close()
        
        return jsonify({'success': True}), 200
    except Exception as e:
        return jsonify({'error': 'Database error', 'details': str(e)}), 500

# ---------------- WEBSITE CONTENT MANAGEMENT ----------------
def ensure_website_content_tables():
    """Create tables for website content management"""
    db = get_db_connection()
    cursor = db.cursor()
    
    # Website content table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS website_content (
            id INT AUTO_INCREMENT PRIMARY KEY,
            section VARCHAR(255) NOT NULL,
            field_name VARCHAR(255) NOT NULL,
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
    """)
    
    # Gallery images table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gallery_images (
            id INT AUTO_INCREMENT PRIMARY KEY,
            filename VARCHAR(255) NOT NULL,
            original_name VARCHAR(255) NOT NULL,
            file_path VARCHAR(255) NOT NULL,
            alt_text TEXT DEFAULT '',
            description TEXT DEFAULT '',
            uploaded_by INT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Slider slides table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS slider_slides (
            id INT AUTO_INCREMENT PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            subtitle TEXT DEFAULT '',
            description TEXT,
            button_text TEXT DEFAULT 'Learn More',
            button_link TEXT DEFAULT '#',
            background_image TEXT DEFAULT '',
            category TEXT DEFAULT 'GENERAL',
            sort_order INT DEFAULT 0,
            is_active INTEGER DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        );
    """)
    
    # Website settings table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS website_settings (
            id INT AUTO_INCREMENT PRIMARY KEY,
            setting_key VARCHAR(255) NOT NULL UNIQUE,
            setting_value TEXT,
            setting_type TEXT DEFAULT 'text',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
    """)
    
    db.commit()
    cursor.close()
    db.close()

# Website content management API endpoints
@app.route('/api/website/content', methods=['GET'])
def get_website_content():
    """Get all website content"""
    try:
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("SELECT section, field_name, content FROM website_content")
        content = cursor.fetchall()
        cursor.close()
        db.close()
        
        # Organize content by section
        organized_content = {}
        for item in content:
            section = item['section']
            if section not in organized_content:
                organized_content[section] = {}
            organized_content[section][item['field_name']] = item['content']
        
        return jsonify({'success': True, 'content': organized_content})
    except Exception as e:
        return jsonify({'error': 'Failed to fetch content', 'details': str(e)}), 500

@app.route('/api/website/content', methods=['POST'])
@jwt_required()
@require_role('admin')
def save_website_content():
    """Save website content"""
    try:
        data = request.get_json()
        section = data.get('section')
        field_name = data.get('field_name')
        content = data.get('content', '')
        
        if not section or not field_name:
            return jsonify({'error': 'Section and field_name are required'}), 400
        
        db = get_db_connection()
        cursor = db.cursor()
        
        # Use INSERT ... ON DUPLICATE KEY UPDATE for upsert
        cursor.execute("""
            INSERT INTO website_content (section, field_name, content)
            VALUES (%s, %s, %s)
            ON CONFLICT(section, field_name) DO UPDATE SET content = excluded.content, updated_at = NOW()
        """, (section, field_name, content))
        
        db.commit()
        cursor.close()
        db.close()
        
        return jsonify({'success': True, 'message': 'Content saved successfully'})
    except Exception as e:
        return jsonify({'error': 'Failed to save content', 'details': str(e)}), 500

@app.route('/api/website/settings', methods=['GET'])
def get_website_settings():
    """Get website settings"""
    try:
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("SELECT setting_key, setting_value, setting_type FROM website_settings")
        settings = cursor.fetchall()
        cursor.close()
        db.close()
        
        # Organize settings
        organized_settings = {}
        for setting in settings:
            organized_settings[setting['setting_key']] = {
                'value': setting['setting_value'],
                'type': setting['setting_type']
            }
        
        return jsonify({'success': True, 'settings': organized_settings})
    except Exception as e:
        return jsonify({'error': 'Failed to fetch settings', 'details': str(e)}), 500

@app.route('/api/website/settings', methods=['POST'])
@jwt_required()
@require_role('admin')
def save_website_settings():
    """Save website settings"""
    try:
        data = request.get_json()
        settings = data.get('settings', {})
        
        db = get_db_connection()
        cursor = db.cursor()
        
        for key, value_data in settings.items():
            if isinstance(value_data, dict):
                value = value_data.get('value', '')
                setting_type = value_data.get('type', 'text')
            else:
                value = str(value_data)
                setting_type = 'text'
            
            cursor.execute("""
                INSERT INTO website_settings (setting_key, setting_value, setting_type)
                VALUES (%s, %s, %s)
                ON CONFLICT(setting_key) DO UPDATE SET setting_value = excluded.setting_value, 
                setting_type = excluded.setting_type, updated_at = NOW()
            """, (key, value, setting_type))
        
        db.commit()
        cursor.close()
        db.close()
        
        return jsonify({'success': True, 'message': 'Settings saved successfully'})
    except Exception as e:
        return jsonify({'error': 'Failed to save settings', 'details': str(e)}), 500

@app.route('/api/gallery/upload', methods=['POST'])
@jwt_required()
@require_role('admin')
def upload_gallery_image():
    """Upload image to gallery"""
    try:
        print("=== GALLERY UPLOAD DEBUG ===")
        print("Request files:", request.files)
        print("Request form:", request.form)
        
        if 'image' not in request.files:
            print("ERROR: No image file in request")
            return jsonify({'error': 'No image file provided'}), 400
        
        file = request.files['image']
        if file.filename == '':
            print("ERROR: Empty filename")
            return jsonify({'error': 'No file selected'}), 400
        
        # Get additional data
        title = request.form.get('title', '')
        alt_text = request.form.get('alt_text', '')
        description = request.form.get('description', '')
        category = request.form.get('category', 'travel')
        featured = request.form.get('featured', 'false').lower() == 'true'
        
        # Secure filename
        filename = secure_filename(file.filename)
        if not filename:
            return jsonify({'error': 'Invalid filename'}), 400
        
        # Create unique filename
        import uuid
        unique_filename = f"{uuid.uuid4()}_{filename}"
        file_path = os.path.join('static/uploads', unique_filename)
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # Save file
        file.save(file_path)
        
        # Save to database
        print("Saving to database...")
        print(f"Filename: {unique_filename}")
        print(f"Original name: {filename}")
        print(f"File path: /static/uploads/{unique_filename}")
        print(f"Title: {title or alt_text}")
        print(f"Description: {description}")
        
        db = get_db_connection()
        cursor = db.cursor()
        try:
            user_id = int(get_jwt_identity())
            print(f"User ID: {user_id}")
        except Exception as e:
            print(f"Error getting user ID: {e}")
            user_id = None
        
        try:
            cursor.execute("""
                INSERT INTO gallery_images (filename, original_name, file_path, alt_text, description, uploaded_by, category, featured)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (unique_filename, filename, f'/static/uploads/{unique_filename}', title or alt_text, description, user_id, category, featured))
            
            # Get the inserted ID
            image_id = cursor.lastrowid
            print(f"Image ID: {image_id}")
            
            db.commit()
            print("Database commit successful")
        except Exception as e:
            print(f"Database error: {e}")
            db.rollback()
            raise e
        finally:
            cursor.close()
            db.close()
        
        return jsonify({
            'success': True, 
            'message': 'Image uploaded successfully',
            'image': {
                'id': image_id,
                'filename': unique_filename,
                'file_path': f'/static/uploads/{unique_filename}',
                'title': title or alt_text,
                'alt_text': alt_text,
                'description': description,
                'category': category,
                'featured': featured,
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        })
    except Exception as e:
        print(f"=== GALLERY UPLOAD ERROR ===")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to upload image', 'details': str(e)}), 500

@app.route('/api/gallery', methods=['GET'])
def list_gallery():
    """Return a list of gallery images from database"""
    try:
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("""
            SELECT id, filename, file_path, alt_text, description, created_at
            FROM gallery_images 
            ORDER BY created_at DESC
        """)
        images = cursor.fetchall()
        cursor.close()
        db.close()
        
        return jsonify({'success': True, 'images': images})
    except Exception as e:
        # Fallback to file system if database fails
        uploads_dir = os.path.join(app.static_folder, 'uploads')
        os.makedirs(uploads_dir, exist_ok=True)
        allowed = ('.png', '.jpg', '.jpeg', '.gif', '.webp')
        try:
            files = [
                    {'id': i, 'filename': f, 'file_path': f'/static/uploads/{f}', 'alt_text': '', 'description': ''}
                    for i, f in enumerate(sorted(os.listdir(uploads_dir)))
                if f.lower().endswith(allowed)
            ]
        except FileNotFoundError:
            files = []
        return jsonify({'success': True, 'images': files})

@app.route('/api/gallery/<int:image_id>', methods=['PUT'])
@jwt_required()
@require_role('admin')
def update_gallery_image(image_id):
    """Update gallery image details"""
    try:
        data = request.get_json()
        
        title = data.get('title', '')
        alt_text = data.get('alt_text', '')
        description = data.get('description', '')
        
        db = get_db_connection()
        cursor = db.cursor()
        
        cursor.execute("""
            UPDATE gallery_images 
            SET alt_text = %s, description = %s 
            WHERE id = %s
        """, (title or alt_text, description, image_id))
        
        db.commit()
        cursor.close()
        db.close()
        
        return jsonify({'success': True, 'message': 'Gallery item updated successfully'})
    except Exception as e:
        return jsonify({'error': 'Failed to update gallery item', 'details': str(e)}), 500

@app.route('/api/gallery/<int:image_id>', methods=['DELETE'])
@jwt_required()
@require_role('admin')
def delete_gallery_image(image_id):
    """Delete gallery image"""
    try:
        db = get_db_connection()
        cursor = db.cursor()
        
        # Get image info
        cursor.execute("SELECT filename, file_path FROM gallery_images WHERE id = %s", (image_id,))
        image = cursor.fetchone()
        
        if not image:
            return jsonify({'error': 'Image not found'}), 404
        
        # Delete from database
        cursor.execute("DELETE FROM gallery_images WHERE id = %s", (image_id,))
        db.commit()
        
        # Delete file
        file_path = os.path.join(app.static_folder, 'uploads', image['filename'])
        if os.path.exists(file_path):
            os.remove(file_path)
        
        cursor.close()
        db.close()
        
        return jsonify({'success': True, 'message': 'Image deleted successfully'})
    except Exception as e:
        return jsonify({'error': 'Failed to delete image', 'details': str(e)}), 500

@app.route('/api/homepage/background', methods=['POST'])
@jwt_required()
@require_role('admin')
def upload_homepage_background():
    """Upload homepage background image"""
    try:
        if 'background' not in request.files:
            return jsonify({'error': 'No background image provided'}), 400
        
        file = request.files['background']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Secure filename
        filename = secure_filename(file.filename)
        if not filename:
            return jsonify({'error': 'Invalid filename'}), 400
        
        # Create unique filename for homepage background
        import uuid
        unique_filename = f"homepage_bg_{uuid.uuid4()}_{filename}"
        file_path = os.path.join('static/uploads', unique_filename)
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # Save file
        file.save(file_path)
        
        # Save to website content
        db = get_db_connection()
        cursor = db.cursor()
        
        cursor.execute("""
            INSERT INTO website_content (section, field_name, content)
            VALUES (%s, %s, %s)
            ON CONFLICT(section, field_name) DO UPDATE SET content = excluded.content, updated_at = NOW()
        """, ('homepage', 'background_image', f'/static/uploads/{unique_filename}'))
        
        db.commit()
        cursor.close()
        db.close()
        
        return jsonify({
            'success': True, 
            'message': 'Homepage background uploaded successfully',
            'image_path': f'/static/uploads/{unique_filename}'
        })
    except Exception as e:
        return jsonify({'error': 'Failed to upload background', 'details': str(e)}), 500

@app.route('/api/homepage/background', methods=['GET'])
def get_homepage_background():
    """Get current homepage background image"""
    try:
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("SELECT content FROM website_content WHERE section = 'homepage' AND field_name = 'background_image'")
        result = cursor.fetchone()
        cursor.close()
        db.close()
        
        background_path = result['content'] if result else None
        return jsonify({'success': True, 'background_image': background_path})
    except Exception as e:
        return jsonify({'error': 'Failed to get background', 'details': str(e)}), 500

@app.route('/api/homepage/content', methods=['POST'])
@jwt_required()
@require_role('admin')
def save_homepage_content():
    """Save homepage content (headline, subtitle, background)"""
    try:
        data = request.get_json()
        print(f"Received data: {data}")  # Debug print
        
        headline = data.get('headline', '')
        subtitle = data.get('subtitle', '')
        background_image = data.get('background_image', '')
        alt_text = data.get('alt_text', '')
        
        print(f"Extracted values - headline: '{headline}', subtitle: '{subtitle}', background: '{background_image}', alt: '{alt_text}'")
        
        db = get_db_connection()
        cursor = db.cursor()
        
        # Save each field separately
        fields_to_save = [
            ('homepage', 'headline', headline),
            ('homepage', 'subtitle', subtitle),
            ('homepage', 'alt_text', alt_text)
        ]
        
        # Only save background if provided
        if background_image:
            fields_to_save.append(('homepage', 'background_image', background_image))
        
        print(f"Saving fields: {fields_to_save}")
        
        for section, field_name, content in fields_to_save:
            cursor.execute("""
                INSERT INTO website_content (section, field_name, content)
                VALUES (%s, %s, %s)
                ON CONFLICT(section, field_name) DO UPDATE SET content = excluded.content, updated_at = NOW()
            """, (section, field_name, content))
            print(f"Saved: {section}.{field_name} = '{content}'")
        
        db.commit()
        cursor.close()
        db.close()
        
        print("Homepage content saved successfully")
        return jsonify({'success': True, 'message': 'Homepage content saved successfully'})
    except Exception as e:
        print(f"Error saving homepage content: {e}")  # Debug print
        return jsonify({'error': 'Failed to save homepage content', 'details': str(e)}), 500

@app.route('/api/homepage/content', methods=['GET'])
def get_homepage_content():
    """Get homepage content (headline, subtitle, background)"""
    try:
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("""
            SELECT field_name, content 
            FROM website_content 
            WHERE section = 'homepage' 
            AND field_name IN ('headline', 'subtitle', 'background_image', 'alt_text')
        """)
        results = cursor.fetchall()
        cursor.close()
        db.close()
        
        # Organize content
        content = {
            'headline': '',
            'subtitle': '',
            'background_image': '',
            'alt_text': ''
        }
        
        for result in results:
            content[result['field_name']] = result['content']
        
        print(f"Homepage content retrieved: {content}")  # Debug print
        return jsonify({'success': True, 'content': content})
    except Exception as e:
        print(f"Error getting homepage content: {e}")  # Debug print
        return jsonify({'error': 'Failed to get homepage content', 'details': str(e)}), 500

# ---------------- STATIC FILE SERVING ----------------
@app.route('/static/<path:filename>')
def static_files(filename):
    """Serve static files"""
    return send_file(os.path.join('static', filename))

@app.route('/api/test-logo')
def test_logo():
    """Test if logo file exists and is accessible"""
    try:
        logo_path = os.path.join('static', 'logo.png')
        if os.path.exists(logo_path):
            return jsonify({'success': True, 'message': 'Logo file exists', 'path': logo_path})
        else:
            return jsonify({'success': False, 'message': 'Logo file not found', 'path': logo_path})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ---------------- SLIDER MANAGEMENT ENDPOINTS ----------------
@app.route('/api/slider/slides', methods=['GET'])
def get_slider_slides():
    """Get all slider slides"""
    try:
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("""
            SELECT id, title, subtitle, description, button_text, button_link, 
                   background_image, category, is_active, sort_order, created_at
            FROM slider_slides 
            WHERE is_active = 1 
            ORDER BY sort_order ASC, created_at ASC
        """)
        slides = cursor.fetchall()
        cursor.close()
        db.close()
        
        # Fix image paths to ensure they work with Flask static serving
        for slide in slides:
            if slide['background_image']:
                print(f"Original image path: {slide['background_image']}")
                # If the path starts with /static/uploads/, keep it as is
                # If it's just a filename, add the /static/uploads/ prefix
                if not slide['background_image'].startswith('/static/uploads/'):
                    slide['background_image'] = f"/static/uploads/{slide['background_image']}"
                print(f"Processed image path: {slide['background_image']}")
        
        # Debug: Log the slides data
        print("Slider slides from database:", slides)
        
        return jsonify({'success': True, 'slides': slides})
    except Exception as e:
        return jsonify({'error': 'Failed to get slider slides', 'details': str(e)}), 500

@app.route('/api/slider/slides', methods=['POST'])
@jwt_required()
@require_role('admin')
def create_slider_slide():
    """Create a new slider slide"""
    try:
        data = request.get_json()
        
        # Debug: Log the received data
        print("Creating slider slide with data:")
        print(f"  - Title: {data.get('title', '')}")
        print(f"  - Background image: {data.get('background_image', '')}")
        print(f"  - Background image type: {type(data.get('background_image', ''))}")
        print(f"  - Full data: {data}")
        
        title = data.get('title', '')
        subtitle = data.get('subtitle', '')
        description = data.get('description', '')
        button_text = data.get('button_text', 'Learn More')
        button_link = data.get('button_link', '#')
        background_image = data.get('background_image', '')
        category = data.get('category', 'GENERAL')
        sort_order = data.get('sort_order', 0)
        
        db = get_db_connection()
        cursor = db.cursor()
        
        # Debug: Log the values being inserted
        print("Inserting slide with values:")
        print(f"  - Title: {title}")
        print(f"  - Background image: {background_image}")
        print(f"  - Background image length: {len(background_image) if background_image else 0}")
        
        cursor.execute("""
            INSERT INTO slider_slides (title, subtitle, description, button_text, button_link, 
                                     background_image, category, sort_order, is_active, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1, CURRENT_TIMESTAMP)
        """, (title, subtitle, description, button_text, button_link, background_image, category, sort_order))
        
        slide_id = cursor.lastrowid
        db.commit()
        cursor.close()
        db.close()
        
        return jsonify({'success': True, 'message': 'Slide created successfully', 'slide_id': slide_id})
    except Exception as e:
        return jsonify({'error': 'Failed to create slide', 'details': str(e)}), 500

@app.route('/api/slider/slides/<int:slide_id>', methods=['PUT'])
@jwt_required()
@require_role('admin')
def update_slider_slide(slide_id):
    """Update a slider slide"""
    try:
        data = request.get_json()
        
        title = data.get('title', '')
        subtitle = data.get('subtitle', '')
        description = data.get('description', '')
        button_text = data.get('button_text', 'Learn More')
        button_link = data.get('button_link', '#')
        background_image = data.get('background_image', '')
        category = data.get('category', 'GENERAL')
        sort_order = data.get('sort_order', 0)
        is_active = data.get('is_active', 1)
        
        db = get_db_connection()
        cursor = db.cursor()
        
        cursor.execute("""
            UPDATE slider_slides 
            SET title = %s, subtitle = %s, description = %s, button_text = %s, 
                button_link = %s, background_image = %s, category = %s, 
                sort_order = %s, is_active = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (title, subtitle, description, button_text, button_link, background_image, 
              category, sort_order, is_active, slide_id))
        
        db.commit()
        cursor.close()
        db.close()
        
        return jsonify({'success': True, 'message': 'Slide updated successfully'})
    except Exception as e:
        return jsonify({'error': 'Failed to update slide', 'details': str(e)}), 500

@app.route('/api/slider/slides/<int:slide_id>', methods=['DELETE'])
@jwt_required()
@require_role('admin')
def delete_slider_slide(slide_id):
    """Delete a slider slide"""
    try:
        db = get_db_connection()
        cursor = db.cursor()
        
        cursor.execute("DELETE FROM slider_slides WHERE id = %s", (slide_id,))
        db.commit()
        cursor.close()
        db.close()
        
        return jsonify({'success': True, 'message': 'Slide deleted successfully'})
    except Exception as e:
        return jsonify({'error': 'Failed to delete slide', 'details': str(e)}), 500

@app.route('/api/slider/upload-image', methods=['POST'])
@jwt_required()
@require_role('admin')
def upload_slider_image():
    """Upload image for slider slide"""
    try:
        if 'image' not in request.files:
            return jsonify({'error': 'No image provided'}), 400
        
        file = request.files['image']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Secure filename
        filename = secure_filename(file.filename)
        if not filename:
            return jsonify({'error': 'Invalid filename'}), 400
        
        # Create unique filename for slider image
        import uuid
        unique_filename = f"slider_{uuid.uuid4()}_{filename}"
        file_path = os.path.join('static/uploads', unique_filename)
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # Save file
        file.save(file_path)
        
        # Debug: Log the upload details
        print(f"Image uploaded successfully:")
        print(f"  - Original filename: {file.filename}")
        print(f"  - Unique filename: {unique_filename}")
        print(f"  - File path: {file_path}")
        print(f"  - Image path returned: /static/uploads/{unique_filename}")
        print(f"  - File exists: {os.path.exists(file_path)}")
        
        return jsonify({
            'success': True, 
            'message': 'Image uploaded successfully',
            'image_path': f'/static/uploads/{unique_filename}'
        })
    except Exception as e:
        return jsonify({'error': 'Failed to upload image', 'details': str(e)}), 500

# ---------------- INVOICE ROUTES ----------------
@app.route('/api/invoices', methods=['GET'])
@jwt_required()
def get_invoices():
    """Get all invoices with optional filtering"""
    try:
        db = get_db_connection()
        cursor = db.cursor()
        
        # Get query parameters
        status = request.args.get('status')
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        customer = request.args.get('customer')
        
        # Build query
        query = """
            SELECT i.*, u.username as created_by_name,
                   (SELECT COUNT(*) FROM invoice_items ii WHERE ii.invoice_id = i.id) as item_count
            FROM invoices i
            LEFT JOIN users u ON i.created_by = u.id
            WHERE 1=1
        """
        params = []
        
        if status:
            query += " AND i.status = %s"
            params.append(status)
        
        if date_from:
            query += " AND i.invoice_date >= %s"
            params.append(date_from)
            
        if date_to:
            query += " AND i.invoice_date <= %s"
            params.append(date_to)
            
        if customer:
            query += " AND i.customer_name LIKE %s"
            params.append(f"%{customer}%")
        
        query += " ORDER BY i.created_at DESC"
        
        cursor.execute(query, params)
        invoices = cursor.fetchall()
        
        cursor.close()
        db.close()
        
        return jsonify({'success': True, 'invoices': invoices})
    except Exception as e:
        print(f"Error getting invoices: {e}")
        return jsonify({'error': 'Failed to get invoices', 'details': str(e)}), 500

@app.route('/api/invoices', methods=['POST'])
@jwt_required()
def create_invoice():
    """Create a new invoice"""
    try:
        data = request.get_json(force=True)
        user_id = get_jwt_identity()
        
        print(f"Creating invoice for user {user_id}")
        print(f"Invoice data: {data}")
        
        # Validate required fields
        required_fields = ['invoice_number', 'invoice_date', 'due_date', 'customer_name', 'items']
        for field in required_fields:
            if field not in data or not data[field]:
                print(f"Missing required field: {field}")
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        db = get_db_connection()
        cursor = db.cursor()
        
        # Calculate totals
        subtotal = sum(float(item.get('amount', 0)) for item in data['items'])
        tax_percentage = float(data.get('tax_percentage', 0))
        tax_amount = subtotal * (tax_percentage / 100)
        total_amount = subtotal + tax_amount
        
        print(f"Calculated totals - Subtotal: {subtotal}, Tax: {tax_amount}, Total: {total_amount}")
        
        # Insert invoice
        cursor.execute("""
            INSERT INTO invoices (
                invoice_number, invoice_date, due_date, customer_name, customer_phone,
                customer_reference, sales_from, subtotal, tax_percentage, tax_amount, total_amount,
                notes, status, created_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            data['invoice_number'], data['invoice_date'], data['due_date'],
            data['customer_name'], data.get('customer_phone'), data.get('customer_reference'),
            data.get('sales_from'), subtotal, tax_percentage, tax_amount, total_amount,
            data.get('notes'), data.get('status', 'draft'), user_id
        ))
        
        invoice_id = cursor.lastrowid
        print(f"Created invoice with ID: {invoice_id}")
        
        # Insert invoice items
        for item in data['items']:
            print(f"Inserting item: {item}")
            cursor.execute("""
                INSERT INTO invoice_items (invoice_id, description, quantity, unit_price, amount)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                invoice_id, item['description'], item['quantity'],
                item['unit_price'], item['amount']
            ))
        
        db.commit()
        cursor.close()
        db.close()
        
        print("Invoice created successfully")
        return jsonify({'success': True, 'invoice_id': invoice_id, 'message': 'Invoice created successfully'})
    except Exception as e:
        print(f"Error creating invoice: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to create invoice', 'details': str(e)}), 500

@app.route('/api/invoices/<int:invoice_id>', methods=['GET'])
@jwt_required()
def get_invoice(invoice_id):
    """Get a specific invoice with its items"""
    try:
        db = get_db_connection()
        cursor = db.cursor()
        
        # Get invoice details
        cursor.execute("""
            SELECT i.*, u.username as created_by_name
            FROM invoices i
            LEFT JOIN users u ON i.created_by = u.id
            WHERE i.id = %s
        """, (invoice_id,))
        
        invoice = cursor.fetchone()
        if not invoice:
            return jsonify({'error': 'Invoice not found'}), 404
        
        # Get invoice items
        cursor.execute("""
            SELECT * FROM invoice_items WHERE invoice_id = %s ORDER BY id
        """, (invoice_id,))
        
        items = cursor.fetchall()
        invoice['items'] = items
        
        cursor.close()
        db.close()
        
        return jsonify({'success': True, 'invoice': invoice})
    except Exception as e:
        print(f"Error getting invoice: {e}")
        return jsonify({'error': 'Failed to get invoice', 'details': str(e)}), 500

@app.route('/api/invoices/<int:invoice_id>', methods=['PUT'])
@jwt_required()
def update_invoice(invoice_id):
    """Update an existing invoice"""
    try:
        data = request.get_json(force=True)
        user_id = get_jwt_identity()
        
        db = get_db_connection()
        cursor = db.cursor()
        
        # Check if invoice exists
        cursor.execute("SELECT id FROM invoices WHERE id = %s", (invoice_id,))
        if not cursor.fetchone():
            return jsonify({'error': 'Invoice not found'}), 404
        
        # Calculate totals
        subtotal = sum(float(item.get('amount', 0)) for item in data['items'])
        tax_percentage = float(data.get('tax_percentage', 0))
        tax_amount = subtotal * (tax_percentage / 100)
        total_amount = subtotal + tax_amount
        
        # Update invoice
        cursor.execute("""
            UPDATE invoices SET
                invoice_date = %s, due_date = %s, customer_name = %s, customer_phone = %s,
                customer_reference = %s, sales_from = %s, subtotal = %s, tax_percentage = %s, tax_amount = %s,
                total_amount = %s, notes = %s, status = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (
            data['invoice_date'], data['due_date'], data['customer_name'],
            data.get('customer_phone'), data.get('customer_reference'), data.get('sales_from'),
            subtotal, tax_percentage, tax_amount, total_amount,
            data.get('notes'), data.get('status', 'draft'), invoice_id
        ))
        
        # Delete existing items and insert new ones
        cursor.execute("DELETE FROM invoice_items WHERE invoice_id = %s", (invoice_id,))
        
        for item in data['items']:
            cursor.execute("""
                INSERT INTO invoice_items (invoice_id, description, quantity, unit_price, amount)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                invoice_id, item['description'], item['quantity'],
                item['unit_price'], item['amount']
            ))
        
        db.commit()
        cursor.close()
        db.close()
        
        return jsonify({'success': True, 'message': 'Invoice updated successfully'})
    except Exception as e:
        print(f"Error updating invoice: {e}")
        return jsonify({'error': 'Failed to update invoice', 'details': str(e)}), 500

@app.route('/api/invoices/<int:invoice_id>', methods=['DELETE'])
@jwt_required()
def delete_invoice(invoice_id):
    """Delete an invoice"""
    try:
        db = get_db_connection()
        cursor = db.cursor()
        
        # Check if invoice exists
        cursor.execute("SELECT id FROM invoices WHERE id = %s", (invoice_id,))
        if not cursor.fetchone():
            return jsonify({'error': 'Invoice not found'}), 404
        
        # Delete invoice (items will be deleted automatically due to CASCADE)
        cursor.execute("DELETE FROM invoices WHERE id = %s", (invoice_id,))
        
        db.commit()
        cursor.close()
        db.close()
        
        return jsonify({'success': True, 'message': 'Invoice deleted successfully'})
    except Exception as e:
        print(f"Error deleting invoice: {e}")
        return jsonify({'error': 'Failed to delete invoice', 'details': str(e)}), 500

@app.route('/api/invoices/generate-number', methods=['GET'])
@jwt_required()
def generate_invoice_number():
    """Generate a unique invoice number"""
    try:
        db = get_db_connection()
        cursor = db.cursor()
        
        # Get the current year
        from datetime import datetime
        current_year = datetime.now().year
        
        # Find the highest invoice number for this year
        cursor.execute("""
            SELECT invoice_number FROM invoices 
            WHERE invoice_number LIKE %s 
            ORDER BY invoice_number DESC LIMIT 1
        """, (f"INV-{current_year}-%",))
        
        result = cursor.fetchone()
        if result:
            # Extract the number part and increment
            last_number = int(result[0].split('-')[-1])
            new_number = last_number + 1
        else:
            new_number = 1
        
        invoice_number = f"INV-{current_year}-{new_number:04d}"
        
        cursor.close()
        db.close()
        
        return jsonify({'success': True, 'invoice_number': invoice_number})
    except Exception as e:
        print(f"Error generating invoice number: {e}")
        return jsonify({'error': 'Failed to generate invoice number', 'details': str(e)}), 500

# ---------------- INVOICE REPORTS ROUTES ----------------
@app.route('/api/invoices/reports/summary', methods=['GET'])
@jwt_required()
def get_invoice_reports_summary():
    """Get invoice reports summary"""
    try:
        db = get_db_connection()
        cursor = db.cursor()
        
        # Get date range from query parameters
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        
        # Build date filter
        date_filter = ""
        params = []
        if date_from and date_to:
            date_filter = "WHERE invoice_date BETWEEN %s AND %s"
            params = [date_from, date_to]
        elif date_from:
            date_filter = "WHERE invoice_date >= %s"
            params = [date_from]
        elif date_to:
            date_filter = "WHERE invoice_date <= %s"
            params = [date_to]
        
        # Total invoices count
        cursor.execute(f"SELECT COUNT(*) as total_invoices FROM invoices {date_filter}", params)
        total_invoices = cursor.fetchone()['total_invoices']
        
        # Total amount
        cursor.execute(f"SELECT SUM(total_amount) as total_amount FROM invoices {date_filter}", params)
        total_amount = cursor.fetchone()['total_amount'] or 0
        
        # Status breakdown
        cursor.execute(f"""
            SELECT status, COUNT(*) as count, SUM(total_amount) as amount
            FROM invoices {date_filter}
            GROUP BY status
        """, params)
        status_breakdown = cursor.fetchall()
        
        # Monthly breakdown (last 12 months)
        cursor.execute(f"""
            SELECT 
                DATE_FORMAT(invoice_date, '%%Y-%%m') as month,
                COUNT(*) as count,
                SUM(total_amount) as amount
            FROM invoices {date_filter}
            GROUP BY DATE_FORMAT(invoice_date, '%%Y-%%m')
            ORDER BY month DESC
            LIMIT 12
        """, params)
        monthly_breakdown = cursor.fetchall()
        
        # Top customers
        cursor.execute(f"""
            SELECT 
                customer_name,
                COUNT(*) as invoice_count,
                SUM(total_amount) as total_amount
            FROM invoices {date_filter}
            GROUP BY customer_name
            ORDER BY total_amount DESC
            LIMIT 10
        """, params)
        top_customers = cursor.fetchall()
        
        cursor.close()
        db.close()
        
        return jsonify({
            'success': True,
            'summary': {
                'total_invoices': total_invoices,
                'total_amount': float(total_amount),
                'status_breakdown': status_breakdown,
                'monthly_breakdown': monthly_breakdown,
                'top_customers': top_customers
            }
        })
    except Exception as e:
        print(f"Error getting invoice reports: {e}")
        return jsonify({'error': 'Failed to get invoice reports', 'details': str(e)}), 500

# ---------------- RECEIPT ROUTES ----------------
@app.route('/api/receipts', methods=['GET'])
@jwt_required()
def get_receipts():
    """Get all receipts with optional filtering"""
    try:
        db = get_db_connection()
        cursor = db.cursor()
        
        # Get query parameters
        status = request.args.get('status')
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        received_from = request.args.get('received_from')
        
        # Build query
        query = """
            SELECT r.*, u.username as created_by_name,
                   (SELECT COUNT(*) FROM receipt_items ri WHERE ri.receipt_id = r.id) as item_count
            FROM receipts r
            LEFT JOIN users u ON r.created_by = u.id
            WHERE 1=1
        """
        params = []
        
        if status:
            query += " AND r.status = %s"
            params.append(status)
        
        if date_from:
            query += " AND r.receipt_date >= %s"
            params.append(date_from)
            
        if date_to:
            query += " AND r.receipt_date <= %s"
            params.append(date_to)
            
        if received_from:
            query += " AND r.received_from LIKE %s"
            params.append(f"%{received_from}%")
        
        query += " ORDER BY r.created_at DESC"
        
        cursor.execute(query, params)
        receipts = cursor.fetchall()
        
        cursor.close()
        db.close()
        
        return jsonify({'success': True, 'receipts': receipts})
    except Exception as e:
        print(f"Error getting receipts: {e}")
        return jsonify({'error': 'Failed to get receipts', 'details': str(e)}), 500

@app.route('/api/receipts', methods=['POST'])
@jwt_required()
def create_receipt():
    """Create a new receipt"""
    try:
        data = request.get_json(force=True)
        user_id = get_jwt_identity()
        
        # Validate required fields
        required_fields = ['receipt_number', 'receipt_date', 'received_from', 'items']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        db = get_db_connection()
        cursor = db.cursor()
        
        # Calculate total
        total_amount = sum(float(item.get('total_amount', 0)) for item in data['items'])
        
        # Insert receipt
        cursor.execute("""
            INSERT INTO receipts (
                receipt_number, receipt_date, received_from, total_amount,
                notes, status, created_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            data['receipt_number'], data['receipt_date'], data['received_from'],
            total_amount, data.get('notes'), data.get('status', 'draft'), user_id
        ))
        
        receipt_id = cursor.lastrowid
        
        # Insert receipt items
        for item in data['items']:
            cursor.execute("""
                INSERT INTO receipt_items (receipt_id, item_number, description, quantity, unit_price, total_amount)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                receipt_id, item['item_number'], item['description'], item['quantity'],
                item['unit_price'], item['total_amount']
            ))
        
        db.commit()
        cursor.close()
        db.close()
        
        return jsonify({'success': True, 'receipt_id': receipt_id, 'message': 'Receipt created successfully'})
    except Exception as e:
        print(f"Error creating receipt: {e}")
        return jsonify({'error': 'Failed to create receipt', 'details': str(e)}), 500

@app.route('/api/receipts/<int:receipt_id>', methods=['GET'])
@jwt_required()
def get_receipt(receipt_id):
    """Get a specific receipt with its items"""
    try:
        db = get_db_connection()
        cursor = db.cursor()
        
        # Get receipt details
        cursor.execute("""
            SELECT r.*, u.username as created_by_name
            FROM receipts r
            LEFT JOIN users u ON r.created_by = u.id
            WHERE r.id = %s
        """, (receipt_id,))
        
        receipt = cursor.fetchone()
        if not receipt:
            return jsonify({'error': 'Receipt not found'}), 404
        
        # Get receipt items
        cursor.execute("""
            SELECT * FROM receipt_items WHERE receipt_id = %s ORDER BY item_number
        """, (receipt_id,))
        
        items = cursor.fetchall()
        receipt['items'] = items
        
        cursor.close()
        db.close()
        
        return jsonify({'success': True, 'receipt': receipt})
    except Exception as e:
        print(f"Error getting receipt: {e}")
        return jsonify({'error': 'Failed to get receipt', 'details': str(e)}), 500

@app.route('/api/receipts/<int:receipt_id>', methods=['PUT'])
@jwt_required()
def update_receipt(receipt_id):
    """Update an existing receipt"""
    try:
        data = request.get_json(force=True)
        user_id = get_jwt_identity()
        
        db = get_db_connection()
        cursor = db.cursor()
        
        # Check if receipt exists
        cursor.execute("SELECT id FROM receipts WHERE id = %s", (receipt_id,))
        if not cursor.fetchone():
            return jsonify({'error': 'Receipt not found'}), 404
        
        # Calculate total
        total_amount = sum(float(item.get('total_amount', 0)) for item in data['items'])
        
        # Update receipt
        cursor.execute("""
            UPDATE receipts SET
                receipt_date = %s, received_from = %s, total_amount = %s,
                notes = %s, status = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (
            data['receipt_date'], data['received_from'], total_amount,
            data.get('notes'), data.get('status', 'draft'), receipt_id
        ))
        
        # Delete existing items and insert new ones
        cursor.execute("DELETE FROM receipt_items WHERE receipt_id = %s", (receipt_id,))
        
        for item in data['items']:
            cursor.execute("""
                INSERT INTO receipt_items (receipt_id, item_number, description, quantity, unit_price, total_amount)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                receipt_id, item['item_number'], item['description'], item['quantity'],
                item['unit_price'], item['total_amount']
            ))
        
        db.commit()
        cursor.close()
        db.close()
        
        return jsonify({'success': True, 'message': 'Receipt updated successfully'})
    except Exception as e:
        print(f"Error updating receipt: {e}")
        return jsonify({'error': 'Failed to update receipt', 'details': str(e)}), 500

@app.route('/api/receipts/<int:receipt_id>', methods=['DELETE'])
@jwt_required()
def delete_receipt(receipt_id):
    """Delete a receipt"""
    try:
        db = get_db_connection()
        cursor = db.cursor()
        
        # Check if receipt exists
        cursor.execute("SELECT id FROM receipts WHERE id = %s", (receipt_id,))
        if not cursor.fetchone():
            return jsonify({'error': 'Receipt not found'}), 404
        
        # Delete receipt (items will be deleted automatically due to CASCADE)
        cursor.execute("DELETE FROM receipts WHERE id = %s", (receipt_id,))
        
        db.commit()
        cursor.close()
        db.close()
        
        return jsonify({'success': True, 'message': 'Receipt deleted successfully'})
    except Exception as e:
        print(f"Error deleting receipt: {e}")
        return jsonify({'error': 'Failed to delete receipt', 'details': str(e)}), 500

@app.route('/api/receipts/generate-number', methods=['GET'])
@jwt_required()
def generate_receipt_number():
    """Generate a unique receipt number"""
    try:
        db = get_db_connection()
        cursor = db.cursor()
        
        # Get the current year
        from datetime import datetime
        current_year = datetime.now().year
        
        # Find the highest receipt number for this year
        cursor.execute("""
            SELECT receipt_number FROM receipts 
            WHERE receipt_number LIKE %s 
            ORDER BY receipt_number DESC LIMIT 1
        """, (f"RCPT-{current_year}-%",))
        
        result = cursor.fetchone()
        new_number = 1
        
        if result:
            if isinstance(result, dict):
                receipt_number = result.get('receipt_number')
            else:
                receipt_number = result[0]
            print(f"Found receipt: {receipt_number}")
            # Extract the number part and increment
            try:
                # Split by '-' and get the last part
                parts = receipt_number.split('-')
                if len(parts) >= 3:
                    last_number = int(parts[-1])
                    new_number = last_number + 1
                    print(f"Extracted number: {last_number}, new number: {new_number}")
                else:
                    print("Invalid receipt number format")
                    new_number = 1
            except (ValueError, IndexError) as e:
                print(f"Error parsing receipt number: {e}")
                # If parsing fails, start from 1
                new_number = 1
        else:
            print("No existing receipts found")
        
        receipt_number = f"RCPT-{current_year}-{new_number:04d}"
        
        cursor.close()
        db.close()
        
        return jsonify({'success': True, 'receipt_number': receipt_number})
    except Exception as e:
        print(f"Error generating receipt number: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to generate receipt number', 'details': str(e)}), 500

# ---------------- RECEIPT REPORTS ROUTES ----------------
@app.route('/api/receipts/reports/summary', methods=['GET'])
@jwt_required()
def get_receipt_reports_summary():
    """Get receipt reports summary"""
    try:
        db = get_db_connection()
        cursor = db.cursor()
        
        # Get date range from query parameters
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        
        # Build date filter
        date_filter = ""
        params = []
        if date_from and date_to:
            date_filter = "WHERE receipt_date BETWEEN %s AND %s"
            params = [date_from, date_to]
        elif date_from:
            date_filter = "WHERE receipt_date >= %s"
            params = [date_from]
        elif date_to:
            date_filter = "WHERE receipt_date <= %s"
            params = [date_to]
        
        # Total receipts count
        cursor.execute(f"SELECT COUNT(*) as total_receipts FROM receipts {date_filter}", params)
        total_receipts = cursor.fetchone()['total_receipts']
        
        # Total amount
        cursor.execute(f"SELECT SUM(total_amount) as total_amount FROM receipts {date_filter}", params)
        total_amount = cursor.fetchone()['total_amount'] or 0
        
        # Status breakdown
        cursor.execute(f"""
            SELECT status, COUNT(*) as count, SUM(total_amount) as amount
            FROM receipts {date_filter}
            GROUP BY status
        """, params)
        status_breakdown = cursor.fetchall()
        
        # Monthly breakdown (last 12 months)
        cursor.execute(f"""
            SELECT 
                DATE_FORMAT(receipt_date, '%%Y-%%m') as month,
                COUNT(*) as count,
                SUM(total_amount) as amount
            FROM receipts {date_filter}
            GROUP BY DATE_FORMAT(receipt_date, '%%Y-%%m')
            ORDER BY month DESC
            LIMIT 12
        """, params)
        monthly_breakdown = cursor.fetchall()
        
        # Top payers
        cursor.execute(f"""
            SELECT 
                received_from,
                COUNT(*) as receipt_count,
                SUM(total_amount) as total_amount
            FROM receipts {date_filter}
            GROUP BY received_from
            ORDER BY total_amount DESC
            LIMIT 10
        """, params)
        top_payers = cursor.fetchall()
        
        cursor.close()
        db.close()
        
        return jsonify({
            'success': True,
            'summary': {
                'total_receipts': total_receipts,
                'total_amount': float(total_amount),
                'status_breakdown': status_breakdown,
                'monthly_breakdown': monthly_breakdown,
                'top_payers': top_payers
            }
        })
    except Exception as e:
        print(f"Error getting receipt reports: {e}")
        return jsonify({'error': 'Failed to get receipt reports', 'details': str(e)}), 500

# ---------------- PDF AND EXCEL EXPORT ROUTES ----------------
@app.route('/api/export/invoices/pdf', methods=['GET'])
@jwt_required()
def export_invoices_pdf():
    """Export invoices to PDF"""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib import colors
        from io import BytesIO
        
        # Get query parameters
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        status = request.args.get('status')
        
        db = get_db_connection()
        cursor = db.cursor()
        
        # Build query
        query = "SELECT * FROM invoices WHERE 1=1"
        params = []
        
        if date_from:
            query += " AND invoice_date >= %s"
            params.append(date_from)
        if date_to:
            query += " AND invoice_date <= %s"
            params.append(date_to)
        if status:
            query += " AND status = %s"
            params.append(status)
        
        query += " ORDER BY invoice_date DESC"
        
        cursor.execute(query, params)
        invoices = cursor.fetchall()
        
        cursor.close()
        db.close()
        
        # Create professional PDF
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1*inch, bottomMargin=1*inch)
        styles = getSampleStyleSheet()
        story = []
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            alignment=1,  # Center alignment
            textColor=colors.HexColor('#2E86AB'),
            fontName='Helvetica-Bold'
        )
        
        subtitle_style = ParagraphStyle(
            'CustomSubtitle',
            parent=styles['Normal'],
            fontSize=12,
            spaceAfter=20,
            alignment=1,  # Center alignment
            textColor=colors.HexColor('#666666'),
            fontName='Helvetica'
        )
        
        # Header with company branding
        company_style = ParagraphStyle(
            'CompanyStyle',
            parent=styles['Normal'],
            fontSize=14,
            spaceAfter=10,
            alignment=1,  # Center alignment
            textColor=colors.HexColor('#2E86AB'),
            fontName='Helvetica-Bold'
        )
        
        company = Paragraph("GAAF TRAVEL & LOGISTICS", company_style)
        story.append(company)
        
        title = Paragraph("INVOICE TRACKER", title_style)
        story.append(title)
        
        subtitle = Paragraph(f"Last Update: {datetime.now().strftime('%d/%m/%Y')}", subtitle_style)
        story.append(subtitle)
        story.append(Spacer(1, 20))
        
        # Enhanced summary section like invoice tracker
        total_invoices = len(invoices)
        paid_count = len([inv for inv in invoices if inv.get('status', '').upper() == 'PAID'])
        pending_count = len([inv for inv in invoices if inv.get('status', '').upper() in ['SENT', 'DRAFT']])
        overdue_count = len([inv for inv in invoices if inv.get('status', '').upper() == 'OVERDUE'])
        cancelled_count = len([inv for inv in invoices if inv.get('status', '').upper() == 'CANCELLED'])
        
        total_amount = sum(float(inv.get('total_amount', 0)) for inv in invoices)
        paid_amount = sum(float(inv.get('total_amount', 0)) for inv in invoices if inv.get('status', '').upper() == 'PAID')
        pending_amount = sum(float(inv.get('total_amount', 0)) for inv in invoices if inv.get('status', '').upper() in ['SENT', 'DRAFT'])
        overdue_amount = sum(float(inv.get('total_amount', 0)) for inv in invoices if inv.get('status', '').upper() == 'OVERDUE')
        
        summary_data = [
            ['SUMMARY STATISTICS', 'No. INVOICES', 'PAID', 'PENDING', 'OVERDUE', 'CANCELLED', 'MONTH'],
            ['', str(total_invoices), str(paid_count), str(pending_count), str(overdue_count), str(cancelled_count), datetime.now().strftime('%B %Y')],
            ['TOTALS', '', f"${paid_amount:,.2f}", f"${pending_amount:,.2f}", f"${overdue_amount:,.2f}", '', f"${total_amount:,.2f}"]
        ]
        
        summary_table = Table(summary_data, colWidths=[1.5*inch, 1*inch, 1*inch, 1*inch, 1*inch, 1*inch, 1*inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2E86AB')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('FONTSIZE', (0, 1), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F8F9FA')),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
        ]))
        
        story.append(summary_table)
        story.append(Spacer(1, 20))
        
        # Main data table matching invoice tracker design
        if invoices:
            data = [['INVOICE #', 'CUSTOMER ID #', 'CUSTOMER', 'INVOICE DATE', 'DUE DATE', 'INVOICE TOTAL', 'TOTAL PAID', 'OUTSTANDING BALANCE', 'STATUS']]
            for invoice in invoices:
                # Calculate payment details
                total_amount = float(invoice.get('total_amount', 0))
                status = invoice.get('status', '').upper()
                
                if status == 'PAID':
                    total_paid = total_amount
                elif status in ['SENT', 'DRAFT', 'PENDING']:
                    total_paid = 0.0
                else:
                    total_paid = total_amount * 0.5 if status == 'OVERDUE' else 0.0
                
                outstanding_balance = total_amount - total_paid
                
                # Determine display status
                if total_paid == 0 and status not in ['PAID']:
                    display_status = 'UNPAID' if status in ['SENT', 'DRAFT'] else status
                elif total_paid == total_amount:
                    display_status = 'PAID'
                elif amount_paid > 0:
                    display_status = 'PARTIALLY PAID'
                else:
                    display_status = status
                
                # Generate customer ID
                customer_id = invoice.get('customer_reference', f"C{str(invoice.get('id', '')).zfill(3)}")
                
                data.append([
                    invoice.get('invoice_number', ''),
                    customer_id,
                    invoice.get('customer_name', ''),
                    str(invoice.get('invoice_date', '')),
                    str(invoice.get('due_date', '')),
                    f"${total_amount:,.2f}",
                    f"${total_paid:,.2f}",
                    f"${outstanding_balance:,.2f}",
                    display_status
                ])
            
            # Calculate column widths to match invoice tracker design
            table_width = 7.5 * inch
            col_widths = [
                table_width * 0.12,  # Invoice #
                table_width * 0.12,  # Customer ID #
                table_width * 0.18,  # Customer
                table_width * 0.10,  # Invoice Date
                table_width * 0.10,  # Due Date
                table_width * 0.12,  # Invoice Total
                table_width * 0.12,  # Total Paid
                table_width * 0.12,  # Outstanding Balance
                table_width * 0.12   # Status
            ]
            
            table = Table(data, colWidths=col_widths)
            table.setStyle(TableStyle([
                # Header row
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2E86AB')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('TOPPADDING', (0, 0), (-1, 0), 12),
                
                # Data rows
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('ALIGN', (0, 1), (0, -1), 'LEFT'),  # Invoice # left aligned
                ('ALIGN', (1, 1), (2, -1), 'CENTER'),  # Dates centered
                ('ALIGN', (3, 1), (5, -1), 'LEFT'),  # Customer, phone, and sales from left aligned
                ('ALIGN', (6, 1), (6, -1), 'RIGHT'),  # Amount right aligned
                ('ALIGN', (7, 1), (7, -1), 'CENTER'),  # Status centered
                
                # Grid and borders
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
                ('LINEBELOW', (0, 0), (-1, 0), 2, colors.HexColor('#2E86AB')),
                
                # Alternating row colors
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8F9FA')]),
                
                # Status color coding
                ('TEXTCOLOR', (7, 1), (7, -1), colors.white),
                ('BACKGROUND', (7, 1), (7, -1), colors.HexColor('#6C757D')),
                
                # Padding
                ('TOPPADDING', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
                ('LEFTPADDING', (0, 1), (-1, -1), 6),
                ('RIGHTPADDING', (0, 1), (-1, -1), 6),
            ]))
            
            # Apply status-specific colors
            for i, invoice in enumerate(invoices, 1):
                status = invoice.get('status', '').upper()
                status_color = {
                    'DRAFT': colors.HexColor('#FFC107'),
                    'SENT': colors.HexColor('#17A2B8'),
                    'PAID': colors.HexColor('#28A745'),
                    'OVERDUE': colors.HexColor('#DC3545'),
                    'CANCELLED': colors.HexColor('#6C757D')
                }.get(status, colors.HexColor('#6C757D'))
                
                table.setStyle(TableStyle([
                    ('BACKGROUND', (7, i), (7, i), status_color),
                    ('TEXTCOLOR', (7, i), (7, i), colors.white)
                ]))
            
            story.append(table)
        else:
            no_data = Paragraph("No invoices found for the selected criteria.", styles['Normal'])
            story.append(no_data)
        
        doc.build(story)
        
        buffer.seek(0)
        return send_file(buffer, as_attachment=True, download_name='invoices_report.pdf', mimetype='application/pdf')
        
    except Exception as e:
        print(f"Error exporting invoices PDF: {e}")
        return jsonify({'error': 'Failed to export PDF', 'details': str(e)}), 500

# ================ FINANCIAL SECTIONS EXPORT ENDPOINTS ================

# Monthly Expenses Export
@app.route('/api/export/expenses/excel', methods=['GET'])
@jwt_required()
def export_expenses_excel():
    """Export monthly expenses to Excel"""
    try:
        import xlsxwriter
        from io import BytesIO
        from datetime import datetime
        
        print("Starting monthly expenses Excel export...")
        
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM expenses ORDER BY expense_date DESC")
        expenses = cursor.fetchall()
        cursor.close()
        db.close()
        
        print(f"Found {len(expenses)} expenses")
        
        if not expenses:
            # Create empty Excel file with headers
            buffer = BytesIO()
            workbook = xlsxwriter.Workbook(buffer)
            worksheet = workbook.add_worksheet('Monthly Expenses Report')
            
            # Professional formatting
            header_format = workbook.add_format({
                'bold': True, 'font_color': 'white', 'bg_color': '#2E86AB',
                'border': 1, 'align': 'center', 'valign': 'vcenter', 'font_size': 12
            })
            
            company_format = workbook.add_format({
                'bold': True, 'font_size': 16, 'font_color': '#2E86AB', 'align': 'center'
            })
            
            title_format = workbook.add_format({
                'bold': True, 'font_size': 20, 'font_color': '#2E86AB', 'align': 'center'
            })
            
            # Header
            worksheet.merge_range('A1:F1', 'GAAF TRAVEL & LOGISTICS', company_format)
            worksheet.merge_range('A2:F2', 'MONTHLY EXPENSES REPORT', title_format)
            worksheet.merge_range('A3:F3', f'Generated: {datetime.now().strftime("%d/%m/%Y %H:%M")}', 
                                 workbook.add_format({'align': 'center', 'italic': True, 'font_size': 10}))
            worksheet.write('A4', '')
            
            # No data message
            worksheet.merge_range('A5:F5', 'No expense data available', 
                                 workbook.add_format({'align': 'center', 'italic': True, 'font_color': '#666666'}))
            
            # Headers
            headers = ['#', 'Date', 'Category', 'Description', 'Quantity', 'Amount']
            for col, header in enumerate(headers):
                worksheet.write(7, col, header, header_format)
            
            # Column widths
            column_widths = [5, 12, 15, 30, 10, 15]
            for col, width in enumerate(column_widths):
                worksheet.set_column(col, col, width)
            
            workbook.close()
            buffer.seek(0)
            
            return send_file(
                BytesIO(buffer.read()),
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name='monthly_expenses_report.xlsx'
            )
        
        # Create professional Excel file
        buffer = BytesIO()
        workbook = xlsxwriter.Workbook(buffer)
        worksheet = workbook.add_worksheet('Monthly Expenses Report')
        
        # Professional formatting
        header_format = workbook.add_format({
            'bold': True, 'font_color': 'white', 'bg_color': '#2E86AB',
            'border': 1, 'align': 'center', 'valign': 'vcenter', 'font_size': 12
        })
        
        company_format = workbook.add_format({
            'bold': True, 'font_size': 16, 'font_color': '#2E86AB', 'align': 'center'
        })
        
        title_format = workbook.add_format({
            'bold': True, 'font_size': 20, 'font_color': '#2E86AB', 'align': 'center'
        })
        
        currency_format = workbook.add_format({
            'num_format': '$#,##0.00', 'border': 1, 'align': 'right', 'font_size': 11
        })
        
        date_format = workbook.add_format({
            'num_format': 'dd/mm/yyyy', 'border': 1, 'align': 'center', 'font_size': 11
        })
        
        text_format = workbook.add_format({'border': 1, 'align': 'left', 'font_size': 11})
        
        number_format = workbook.add_format({'border': 1, 'align': 'center', 'font_size': 11})
        
        # Header with enhanced styling
        worksheet.merge_range('A1:F1', 'GAAF TRAVEL & LOGISTICS', company_format)
        worksheet.merge_range('A2:F2', 'MONTHLY EXPENSES REPORT', title_format)
        worksheet.merge_range('A3:F3', f'Generated: {datetime.now().strftime("%d/%m/%Y %H:%M")}', 
                             workbook.add_format({'align': 'center', 'italic': True, 'font_size': 10}))
        worksheet.write('A4', '')
        
        # Enhanced Summary Section
        total_expenses = sum(float(exp.get('amount', 0)) for exp in expenses)
        
        # Summary header
        summary_header_format = workbook.add_format({
            'bg_color': '#2E86AB', 'border': 1, 'bold': True, 'font_color': 'white', 'font_size': 12
        })
        worksheet.merge_range('A5:F5', 'EXPENSE SUMMARY', summary_header_format)
        
        # Summary details
        summary_format = workbook.add_format({
            'bg_color': '#F8F9FA', 'border': 1, 'bold': True, 'font_color': '#2E86AB', 'font_size': 11
        })
        
        worksheet.merge_range('A6:C6', 'Total Records:', summary_format)
        worksheet.write('D6', len(expenses), summary_format)
        worksheet.merge_range('E6:F6', 'Total Amount:', summary_format)
        worksheet.write('G6', total_expenses, workbook.add_format({
            'bg_color': '#F8F9FA', 'border': 1, 'bold': True, 'font_color': '#2E86AB', 
            'num_format': '$#,##0.00', 'font_size': 11
        }))
        
        worksheet.write('A7', '')
        
        # Headers
        headers = ['#', 'Date', 'Category', 'Description', 'Quantity', 'Amount']
        for col, header in enumerate(headers):
            worksheet.write(9, col, header, header_format)
        
        # Data with enhanced formatting
        for row, expense in enumerate(expenses, 10):
            # Row number
            worksheet.write(row, 0, row - 9, number_format)
            
            # Date
            if expense.get('expense_date'):
                worksheet.write(row, 1, expense['expense_date'], date_format)
            else:
                worksheet.write(row, 1, 'N/A', text_format)
            
            # Category and Description
            worksheet.write(row, 2, expense.get('category', ''), text_format)
            worksheet.write(row, 3, expense.get('description', ''), text_format)
            
            # Quantity
            worksheet.write(row, 4, expense.get('quantity', 1), number_format)
            
            # Amount
            worksheet.write(row, 5, float(expense.get('amount', 0)), currency_format)
        
        # Enhanced column widths
        column_widths = [6, 12, 18, 35, 10, 16]
        for col, width in enumerate(column_widths):
            worksheet.set_column(col, col, width)
        
        # Add footer
        footer_row = len(expenses) + 12
        worksheet.merge_range(f'A{footer_row}:F{footer_row}', 
                             f'Report generated on {datetime.now().strftime("%d/%m/%Y at %H:%M")} | GAAF TRAVEL & LOGISTICS', 
                             workbook.add_format({'align': 'center', 'italic': True, 'font_size': 9, 'font_color': '#666666'}))
        
        # Add page setup
        worksheet.set_landscape()
        worksheet.fit_to_pages(1, 0)
        worksheet.set_margins(0.5, 0.5, 0.5, 0.5)
        
        workbook.close()
        buffer.seek(0)
        
        print("Monthly expenses Excel export completed successfully")
        
        return send_file(
            BytesIO(buffer.read()),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='monthly_expenses_report.xlsx'
        )
        
    except Exception as e:
        return jsonify({'error': 'Failed to export expenses', 'details': str(e)}), 500

@app.route('/api/export/expenses/pdf', methods=['GET'])
@jwt_required()
def export_expenses_pdf():
    """Export monthly expenses to PDF"""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
        from reportlab.lib.units import inch
        from io import BytesIO
        
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM expenses ORDER BY expense_date DESC")
        expenses = cursor.fetchall()
        cursor.close()
        db.close()
        
        if not expenses:
            return jsonify({'error': 'No expenses found'}), 404
        
        # Create PDF
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1*inch, bottomMargin=1*inch)
        styles = getSampleStyleSheet()
        story = []
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle', parent=styles['Heading1'],
            fontSize=24, spaceAfter=30, alignment=1,
            textColor=colors.HexColor('#2E86AB'), fontName='Helvetica-Bold'
        )
        
        company_style = ParagraphStyle(
            'CompanyStyle', parent=styles['Normal'],
            fontSize=14, spaceAfter=10, alignment=1,
            textColor=colors.HexColor('#2E86AB'), fontName='Helvetica-Bold'
        )
        
        # Header
        company = Paragraph("GAAF TRAVEL & LOGISTICS", company_style)
        story.append(company)
        title = Paragraph("MONTHLY EXPENSES REPORT", title_style)
        story.append(title)
        story.append(Spacer(1, 20))
        
        # Summary
        total_expenses = sum(float(exp.get('amount', 0)) for exp in expenses)
        summary_data = [
            ['SUMMARY', '', '', ''],
            ['Total Expenses:', f"${total_expenses:,.2f}", 'Total Records:', str(len(expenses))]
        ]
        
        summary_table = Table(summary_data, colWidths=[2*inch, 1.5*inch, 2*inch, 1.5*inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2E86AB')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F8F9FA')),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        
        story.append(summary_table)
        story.append(Spacer(1, 20))
        
        # Data table
        data = [['#', 'Date', 'Category', 'Description', 'Qty', 'Amount']]
        for i, expense in enumerate(expenses, 1):
            data.append([
                str(i),
                str(expense.get('expense_date', '')),
                expense.get('category', ''),
                expense.get('description', ''),
                str(expense.get('quantity', 1)),
                f"${float(expense.get('amount', 0)):,.2f}"
            ])
        
        table = Table(data, colWidths=[0.5*inch, 1*inch, 1.2*inch, 2.5*inch, 0.5*inch, 1*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2E86AB')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
        ]))
        
        story.append(table)
        doc.build(story)
        buffer.seek(0)
        
        return send_file(
            buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name='monthly_expenses_report.pdf'
        )
        
    except Exception as e:
        return jsonify({'error': 'Failed to export expenses PDF', 'details': str(e)}), 500

# Investments Export
@app.route('/api/test/investments', methods=['GET'])
@jwt_required()
def test_investments():
    """Test endpoint to check investments data"""
    try:
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM investments ORDER BY invest_date DESC")
        investments = cursor.fetchall()
        cursor.close()
        db.close()
        
        return jsonify({
            'count': len(investments),
            'investments': investments[:3]  # Return first 3 for testing
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/fix/investments-status', methods=['POST'])
@jwt_required()
def fix_investments_status():
    """Fix truncated status values in investments table"""
    try:
        db = get_db_connection()
        cursor = db.cursor()
        
        # Update truncated status values
        status_updates = [
            ('PA', 'Paid'),
            ('DR', 'Draft'),
            ('NP', 'Not Paid'),
            ('PP', 'Partial Paid'),
            ('draft', 'Draft'),
            ('paid', 'Paid'),
            ('not paid', 'Not Paid'),
            ('partial paid', 'Partial Paid')
        ]
        
        updated_count = 0
        for old_status, new_status in status_updates:
            cursor.execute("UPDATE investments SET status = %s WHERE status = %s", (new_status, old_status))
            updated_count += cursor.rowcount
        
        db.commit()
        cursor.close()
        db.close()
        
        return jsonify({
            'success': True,
            'message': f'Updated {updated_count} investment records',
            'updated_count': updated_count
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/export/investments/excel', methods=['GET'])
@jwt_required()
def export_investments_excel():
    """Export investments to Excel"""
    try:
        import xlsxwriter
        from io import BytesIO
        from datetime import datetime
        
        print("Starting investments Excel export...")
        
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM investments ORDER BY invest_date DESC")
        investments = cursor.fetchall()
        cursor.close()
        db.close()
        
        print(f"Found {len(investments)} investments")
        
        if not investments:
            # Create empty Excel file with headers
            buffer = BytesIO()
            workbook = xlsxwriter.Workbook(buffer)
            worksheet = workbook.add_worksheet('Investments Report')
            
            # Professional formatting
            header_format = workbook.add_format({
                'bold': True, 'font_color': 'white', 'bg_color': '#2E86AB',
                'border': 1, 'align': 'center', 'valign': 'vcenter', 'font_size': 12
            })
            
            company_format = workbook.add_format({
                'bold': True, 'font_size': 14, 'font_color': '#2E86AB', 'align': 'center'
            })
            
            title_format = workbook.add_format({
                'bold': True, 'font_size': 18, 'font_color': '#2E86AB', 'align': 'center'
            })
            
            # Header
            worksheet.merge_range('A1:J1', 'GAAF TRAVEL & LOGISTICS', company_format)
            worksheet.merge_range('A2:J2', 'INVESTMENTS REPORT', title_format)
            worksheet.merge_range('A3:J3', f'Generated: {datetime.now().strftime("%d/%m/%Y %H:%M")}', 
                                 workbook.add_format({'align': 'center', 'italic': True}))
            worksheet.write('A4', '')
            
            # No data message
            worksheet.merge_range('A5:J5', 'No investment data available', 
                                 workbook.add_format({'align': 'center', 'italic': True, 'font_color': '#666666'}))
            
            # Headers
            headers = ['#', 'Date', 'Name', 'Company', 'Required Amount', 'Amount Paid', 'Amount Remaining', 'Interest %', 'Status', 'Notes']
            for col, header in enumerate(headers):
                worksheet.write(7, col, header, header_format)
            
            # Column widths
            column_widths = [5, 12, 20, 20, 15, 15, 15, 12, 15, 25]
            for col, width in enumerate(column_widths):
                worksheet.set_column(col, col, width)
            
            workbook.close()
            buffer.seek(0)
            
            return send_file(
                BytesIO(buffer.read()),
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name='investments_report.xlsx'
            )
        
        # Create professional Excel file
        buffer = BytesIO()
        workbook = xlsxwriter.Workbook(buffer)
        worksheet = workbook.add_worksheet('Investments Report')
        
        # Professional formatting
        header_format = workbook.add_format({
            'bold': True, 'font_color': 'white', 'bg_color': '#2E86AB',
            'border': 1, 'align': 'center', 'valign': 'vcenter', 'font_size': 12
        })
        
        company_format = workbook.add_format({
            'bold': True, 'font_size': 16, 'font_color': '#2E86AB', 'align': 'center'
        })
        
        title_format = workbook.add_format({
            'bold': True, 'font_size': 20, 'font_color': '#2E86AB', 'align': 'center'
        })
        
        currency_format = workbook.add_format({
            'num_format': '$#,##0.00', 'border': 1, 'align': 'right', 'font_size': 11
        })
        
        date_format = workbook.add_format({
            'num_format': 'dd/mm/yyyy', 'border': 1, 'align': 'center', 'font_size': 11
        })
        
        text_format = workbook.add_format({'border': 1, 'align': 'left', 'font_size': 11})
        
        number_format = workbook.add_format({'border': 1, 'align': 'center', 'font_size': 11})
        
        # Header with enhanced styling
        worksheet.merge_range('A1:J1', 'GAAF TRAVEL & LOGISTICS', company_format)
        worksheet.merge_range('A2:J2', 'INVESTMENTS REPORT', title_format)
        worksheet.merge_range('A3:J3', f'Generated: {datetime.now().strftime("%d/%m/%Y %H:%M")}', 
                             workbook.add_format({'align': 'center', 'italic': True, 'font_size': 10}))
        worksheet.write('A4', '')
        
        # Enhanced Summary Section
        total_required = sum(float(inv.get('required_amount', 0)) for inv in investments)
        total_paid = sum(float(inv.get('amount_paid', 0)) for inv in investments)
        total_remaining = sum(float(inv.get('amount_remaining', 0)) for inv in investments)
        
        # Summary header
        summary_header_format = workbook.add_format({
            'bg_color': '#2E86AB', 'border': 1, 'bold': True, 'font_color': 'white', 'font_size': 12
        })
        worksheet.merge_range('A5:J5', 'INVESTMENT SUMMARY', summary_header_format)
        
        # Summary details
        summary_format = workbook.add_format({
            'bg_color': '#F8F9FA', 'border': 1, 'bold': True, 'font_color': '#2E86AB', 'font_size': 11
        })
        
        worksheet.merge_range('A6:C6', 'Total Records:', summary_format)
        worksheet.write('D6', len(investments), summary_format)
        worksheet.merge_range('E6:G6', 'Total Required Amount:', summary_format)
        worksheet.write('H6', total_required, workbook.add_format({
            'bg_color': '#F8F9FA', 'border': 1, 'bold': True, 'font_color': '#2E86AB', 
            'num_format': '$#,##0.00', 'font_size': 11
        }))
        
        worksheet.merge_range('A7:C7', 'Total Amount Paid:', summary_format)
        worksheet.write('D7', total_paid, workbook.add_format({
            'bg_color': '#F8F9FA', 'border': 1, 'bold': True, 'font_color': '#2E86AB', 
            'num_format': '$#,##0.00', 'font_size': 11
        }))
        worksheet.merge_range('E7:G7', 'Total Remaining:', summary_format)
        worksheet.write('H7', total_remaining, workbook.add_format({
            'bg_color': '#F8F9FA', 'border': 1, 'bold': True, 'font_color': '#2E86AB', 
            'num_format': '$#,##0.00', 'font_size': 11
        }))
        
        worksheet.write('A8', '')
        
        # Headers
        headers = ['#', 'Date', 'Name', 'Company', 'Required Amount', 'Amount Paid', 'Amount Remaining', 'Interest %', 'Status', 'Notes']
        for col, header in enumerate(headers):
            worksheet.write(9, col, header, header_format)
        
        # Status mapping function
        def map_status(status):
            status_map = {
                'PA': 'Paid',
                'DR': 'Draft', 
                'NP': 'Not Paid',
                'PP': 'Partial Paid',
                'draft': 'Draft',
                'paid': 'Paid',
                'not paid': 'Not Paid',
                'partial paid': 'Partial Paid'
            }
            return status_map.get(status, status)
        
        # Data with enhanced formatting
        for row, investment in enumerate(investments, 10):
            # Row number
            worksheet.write(row, 0, row - 9, number_format)
            
            # Date
            if investment.get('invest_date'):
                worksheet.write(row, 1, investment['invest_date'], date_format)
            else:
                worksheet.write(row, 1, 'N/A', text_format)
            
            # Name and Company
            worksheet.write(row, 2, investment.get('name', ''), text_format)
            worksheet.write(row, 3, investment.get('requested_company', ''), text_format)
            
            # Currency amounts
            worksheet.write(row, 4, float(investment.get('required_amount', 0)), currency_format)
            worksheet.write(row, 5, float(investment.get('amount_paid', 0)), currency_format)
            worksheet.write(row, 6, float(investment.get('amount_remaining', 0)), currency_format)
            
            # Interest percentage
            worksheet.write(row, 7, float(investment.get('required_interest', 0)), 
                          workbook.add_format({'border': 1, 'align': 'center', 'font_size': 11, 'num_format': '0.00"%"'}))
            
            # Status with enhanced color coding
            status = map_status(investment.get('status', ''))
            status_colors = {
                'PAID': '#28A745',
                'PARTIAL PAID': '#FFC107', 
                'NOT PAID': '#DC3545',
                'DRAFT': '#6C757D'
            }
            status_color = status_colors.get(status.upper(), '#6C757D')
            
            status_format = workbook.add_format({
                'border': 1, 'align': 'center', 'bold': True,
                'bg_color': status_color, 'font_color': 'white', 'font_size': 11
            })
            worksheet.write(row, 8, status, status_format)
            
            # Notes
            worksheet.write(row, 9, investment.get('notes', ''), text_format)
        
        # Enhanced column widths
        column_widths = [6, 12, 18, 18, 16, 16, 16, 12, 14, 30]
        for col, width in enumerate(column_widths):
            worksheet.set_column(col, col, width)
        
        # Add footer
        footer_row = len(investments) + 12
        worksheet.merge_range(f'A{footer_row}:J{footer_row}', 
                             f'Report generated on {datetime.now().strftime("%d/%m/%Y at %H:%M")} | GAAF TRAVEL & LOGISTICS', 
                             workbook.add_format({'align': 'center', 'italic': True, 'font_size': 9, 'font_color': '#666666'}))
        
        # Add page setup
        worksheet.set_landscape()
        worksheet.fit_to_pages(1, 0)
        worksheet.set_margins(0.5, 0.5, 0.5, 0.5)
        
        workbook.close()
        buffer.seek(0)
        
        print("Excel export completed successfully")
        
        return send_file(
            BytesIO(buffer.read()),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='investments_report.xlsx'
        )
        
    except Exception as e:
        print(f"Investments Excel Export Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to export investments', 'details': str(e)}), 500

@app.route('/api/export/investments/pdf', methods=['GET'])
@jwt_required()
def export_investments_pdf():
    """Export investments to PDF"""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
        from reportlab.lib.units import inch
        from io import BytesIO
        
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM investments ORDER BY invest_date DESC")
        investments = cursor.fetchall()
        cursor.close()
        db.close()
        
        if not investments:
            return jsonify({'error': 'No investments found'}), 404
        
        # Create PDF
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1*inch, bottomMargin=1*inch)
        styles = getSampleStyleSheet()
        story = []
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle', parent=styles['Heading1'],
            fontSize=24, spaceAfter=30, alignment=1,
            textColor=colors.HexColor('#2E86AB'), fontName='Helvetica-Bold'
        )
        
        company_style = ParagraphStyle(
            'CompanyStyle', parent=styles['Normal'],
            fontSize=14, spaceAfter=10, alignment=1,
            textColor=colors.HexColor('#2E86AB'), fontName='Helvetica-Bold'
        )
        
        # Header
        company = Paragraph("GAAF TRAVEL & LOGISTICS", company_style)
        story.append(company)
        title = Paragraph("INVESTMENTS REPORT", title_style)
        story.append(title)
        story.append(Spacer(1, 20))
        
        # Summary
        total_required = sum(float(inv.get('required_amount', 0)) for inv in investments)
        total_paid = sum(float(inv.get('amount_paid', 0)) for inv in investments)
        total_remaining = sum(float(inv.get('amount_remaining', 0)) for inv in investments)
        
        summary_data = [
            ['SUMMARY', '', '', ''],
            ['Total Required:', f"${total_required:,.2f}", 'Total Paid:', f"${total_paid:,.2f}"],
            ['Total Remaining:', f"${total_remaining:,.2f}", 'Total Records:', str(len(investments))]
        ]
        
        summary_table = Table(summary_data, colWidths=[2*inch, 1.5*inch, 2*inch, 1.5*inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2E86AB')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F8F9FA')),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        
        story.append(summary_table)
        story.append(Spacer(1, 20))
        
        # Data table
        data = [['#', 'Date', 'Name', 'Company', 'Required', 'Paid', 'Remaining', 'Interest %', 'Status']]
        
        # Status mapping function
        def map_status(status):
            status_map = {
                'PA': 'Paid',
                'DR': 'Draft', 
                'NP': 'Not Paid',
                'PP': 'Partial Paid',
                'draft': 'Draft',
                'paid': 'Paid',
                'not paid': 'Not Paid',
                'partial paid': 'Partial Paid'
            }
            return status_map.get(status, status)
        
        for i, investment in enumerate(investments, 1):
            status = map_status(investment.get('status', ''))
            data.append([
                str(i),
                str(investment.get('invest_date', '')),
                investment.get('name', ''),
                investment.get('requested_company', ''),
                f"${float(investment.get('required_amount', 0)):,.2f}",
                f"${float(investment.get('amount_paid', 0)):,.2f}",
                f"${float(investment.get('amount_remaining', 0)):,.2f}",
                f"{float(investment.get('required_interest', 0)):.1f}%",
                status
            ])
        
        table = Table(data, colWidths=[0.5*inch, 1*inch, 1.5*inch, 1.5*inch, 1*inch, 1*inch, 1*inch, 0.8*inch, 1*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2E86AB')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
        ]))
        
        story.append(table)
        doc.build(story)
        buffer.seek(0)
        
        return send_file(
            buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name='investments_report.pdf'
        )
        
    except Exception as e:
        print(f"Investments PDF Export Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to export investments PDF', 'details': str(e)}), 500

# Received Loans Export
@app.route('/api/export/received-loans/excel', methods=['GET'])
@jwt_required()
def export_received_loans_excel():
    """Export received loans to Excel"""
    try:
        import xlsxwriter
        from io import BytesIO
        from datetime import datetime
        
        print("Starting received loans Excel export...")
        
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM received_loans ORDER BY received_date DESC")
        loans = cursor.fetchall()
        cursor.close()
        db.close()
        
        print(f"Found {len(loans)} received loans")
        
        if not loans:
            # Create empty Excel file with headers
            buffer = BytesIO()
            workbook = xlsxwriter.Workbook(buffer)
            worksheet = workbook.add_worksheet('Received Loans Report')
            
            # Professional formatting
            header_format = workbook.add_format({
                'bold': True, 'font_color': 'white', 'bg_color': '#2E86AB',
                'border': 1, 'align': 'center', 'valign': 'vcenter', 'font_size': 12
            })
            
            company_format = workbook.add_format({
                'bold': True, 'font_size': 16, 'font_color': '#2E86AB', 'align': 'center'
            })
            
            title_format = workbook.add_format({
                'bold': True, 'font_size': 20, 'font_color': '#2E86AB', 'align': 'center'
            })
            
            # Header
            worksheet.merge_range('A1:H1', 'GAAF TRAVEL & LOGISTICS', company_format)
            worksheet.merge_range('A2:H2', 'RECEIVED LOANS REPORT', title_format)
            worksheet.merge_range('A3:H3', f'Generated: {datetime.now().strftime("%d/%m/%Y %H:%M")}', 
                                 workbook.add_format({'align': 'center', 'italic': True, 'font_size': 10}))
            worksheet.write('A4', '')
            
            # No data message
            worksheet.merge_range('A5:H5', 'No received loans data available', 
                                 workbook.add_format({'align': 'center', 'italic': True, 'font_color': '#666666'}))
            
            # Headers
            headers = ['#', 'Date', 'Lender', 'Amount', 'Due Date', 'Interest %', 'Status', 'Notes']
            for col, header in enumerate(headers):
                worksheet.write(7, col, header, header_format)
            
            # Column widths
            column_widths = [5, 12, 20, 15, 12, 12, 15, 25]
            for col, width in enumerate(column_widths):
                worksheet.set_column(col, col, width)
            
            workbook.close()
            buffer.seek(0)
            
            return send_file(
                BytesIO(buffer.read()),
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name='received_loans_report.xlsx'
            )
        
        # Create professional Excel file
        buffer = BytesIO()
        workbook = xlsxwriter.Workbook(buffer)
        worksheet = workbook.add_worksheet('Received Loans Report')
        
        # Professional formatting
        header_format = workbook.add_format({
            'bold': True, 'font_color': 'white', 'bg_color': '#2E86AB',
            'border': 1, 'align': 'center', 'valign': 'vcenter', 'font_size': 12
        })
        
        company_format = workbook.add_format({
            'bold': True, 'font_size': 16, 'font_color': '#2E86AB', 'align': 'center'
        })
        
        title_format = workbook.add_format({
            'bold': True, 'font_size': 20, 'font_color': '#2E86AB', 'align': 'center'
        })
        
        currency_format = workbook.add_format({
            'num_format': '$#,##0.00', 'border': 1, 'align': 'right', 'font_size': 11
        })
        
        date_format = workbook.add_format({
            'num_format': 'dd/mm/yyyy', 'border': 1, 'align': 'center', 'font_size': 11
        })
        
        text_format = workbook.add_format({'border': 1, 'align': 'left', 'font_size': 11})
        
        number_format = workbook.add_format({'border': 1, 'align': 'center', 'font_size': 11})
        
        # Header with enhanced styling
        worksheet.merge_range('A1:H1', 'GAAF TRAVEL & LOGISTICS', company_format)
        worksheet.merge_range('A2:H2', 'RECEIVED LOANS REPORT', title_format)
        worksheet.merge_range('A3:H3', f'Generated: {datetime.now().strftime("%d/%m/%Y %H:%M")}', 
                             workbook.add_format({'align': 'center', 'italic': True, 'font_size': 10}))
        worksheet.write('A4', '')
        
        # Enhanced Summary Section
        total_amount = sum(float(loan.get('amount', 0)) for loan in loans)
        
        # Summary header
        summary_header_format = workbook.add_format({
            'bg_color': '#2E86AB', 'border': 1, 'bold': True, 'font_color': 'white', 'font_size': 12
        })
        worksheet.merge_range('A5:H5', 'LOAN SUMMARY', summary_header_format)
        
        # Summary details
        summary_format = workbook.add_format({
            'bg_color': '#F8F9FA', 'border': 1, 'bold': True, 'font_color': '#2E86AB', 'font_size': 11
        })
        
        worksheet.merge_range('A6:C6', 'Total Records:', summary_format)
        worksheet.write('D6', len(loans), summary_format)
        worksheet.merge_range('E6:G6', 'Total Amount:', summary_format)
        worksheet.write('H6', total_amount, workbook.add_format({
            'bg_color': '#F8F9FA', 'border': 1, 'bold': True, 'font_color': '#2E86AB', 
            'num_format': '$#,##0.00', 'font_size': 11
        }))
        
        worksheet.write('A7', '')
        
        # Headers
        headers = ['#', 'Date', 'Lender', 'Amount', 'Due Date', 'Interest %', 'Status', 'Notes']
        for col, header in enumerate(headers):
            worksheet.write(9, col, header, header_format)
        
        # Data with enhanced formatting
        for row, loan in enumerate(loans, 10):
            # Row number
            worksheet.write(row, 0, row - 9, number_format)
            
            # Date
            if loan.get('received_date'):
                worksheet.write(row, 1, loan['received_date'], date_format)
            else:
                worksheet.write(row, 1, 'N/A', text_format)
            
            # Lender and Amount
            worksheet.write(row, 2, loan.get('lender_name', ''), text_format)
            worksheet.write(row, 3, float(loan.get('loan_amount', 0)), currency_format)
            
            # Due Date
            if loan.get('due_date'):
                worksheet.write(row, 4, loan['due_date'], date_format)
            else:
                worksheet.write(row, 4, 'N/A', text_format)
            
            # Interest percentage
            worksheet.write(row, 5, float(loan.get('interest_rate', 0)), 
                          workbook.add_format({'border': 1, 'align': 'center', 'font_size': 11, 'num_format': '0.00"%"'}))
            
            # Status
            status = loan.get('status', 'Active')
            status_colors = {
                'ACTIVE': '#28A745',
                'PAID': '#28A745',
                'OVERDUE': '#DC3545',
                'DEFAULTED': '#DC3545'
            }
            status_color = status_colors.get(status.upper(), '#6C757D')
            
            status_format = workbook.add_format({
                'border': 1, 'align': 'center', 'bold': True,
                'bg_color': status_color, 'font_color': 'white', 'font_size': 11
            })
            worksheet.write(row, 6, status, status_format)
            
            # Notes
            worksheet.write(row, 7, loan.get('notes', ''), text_format)
        
        # Enhanced column widths
        column_widths = [6, 12, 20, 16, 12, 12, 14, 30]
        for col, width in enumerate(column_widths):
            worksheet.set_column(col, col, width)
        
        # Add footer
        footer_row = len(loans) + 12
        worksheet.merge_range(f'A{footer_row}:H{footer_row}', 
                             f'Report generated on {datetime.now().strftime("%d/%m/%Y at %H:%M")} | GAAF TRAVEL & LOGISTICS', 
                             workbook.add_format({'align': 'center', 'italic': True, 'font_size': 9, 'font_color': '#666666'}))
        
        # Add page setup
        worksheet.set_landscape()
        worksheet.fit_to_pages(1, 0)
        worksheet.set_margins(0.5, 0.5, 0.5, 0.5)
        
        workbook.close()
        buffer.seek(0)
        
        print("Received loans Excel export completed successfully")
        
        return send_file(
            BytesIO(buffer.read()),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='received_loans_report.xlsx'
        )
        
    except Exception as e:
        print(f"Received Loans Excel Export Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to export received loans', 'details': str(e)}), 500

@app.route('/api/export/received-loans/pdf', methods=['GET'])
@jwt_required()
def export_received_loans_pdf():
    """Export received loans to PDF"""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
        from reportlab.lib.units import inch
        from io import BytesIO
        
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM received_loans ORDER BY received_date DESC")
        loans = cursor.fetchall()
        cursor.close()
        db.close()
        
        if not loans:
            return jsonify({'error': 'No received loans found'}), 404
        
        # Create PDF
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1*inch, bottomMargin=1*inch)
        styles = getSampleStyleSheet()
        story = []
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle', parent=styles['Heading1'],
            fontSize=24, spaceAfter=30, alignment=1,
            textColor=colors.HexColor('#2E86AB'), fontName='Helvetica-Bold'
        )
        
        company_style = ParagraphStyle(
            'CompanyStyle', parent=styles['Normal'],
            fontSize=14, spaceAfter=10, alignment=1,
            textColor=colors.HexColor('#2E86AB'), fontName='Helvetica-Bold'
        )
        
        # Header
        company = Paragraph("GAAF TRAVEL & LOGISTICS", company_style)
        story.append(company)
        title = Paragraph("RECEIVED LOANS REPORT", title_style)
        story.append(title)
        story.append(Spacer(1, 20))
        
        # Summary
        total_amount = sum(float(loan.get('amount', 0)) for loan in loans)
        
        summary_data = [
            ['SUMMARY', '', '', ''],
            ['Total Amount:', f"${total_amount:,.2f}", 'Total Records:', str(len(loans))]
        ]
        
        summary_table = Table(summary_data, colWidths=[2*inch, 1.5*inch, 2*inch, 1.5*inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2E86AB')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F8F9FA')),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        
        story.append(summary_table)
        story.append(Spacer(1, 20))
        
        # Data table
        data = [['#', 'Date', 'Lender', 'Amount', 'Due Date', 'Interest %', 'Status']]
        for i, loan in enumerate(loans, 1):
            data.append([
                str(i),
                str(loan.get('received_date', '')),
                loan.get('lender_name', ''),
                f"${float(loan.get('loan_amount', 0)):,.2f}",
                str(loan.get('due_date', '')),
                f"{float(loan.get('interest_rate', 0)):.1f}%",
                loan.get('status', 'Active').upper()
            ])
        
        table = Table(data, colWidths=[0.5*inch, 1*inch, 1.5*inch, 1*inch, 1*inch, 0.8*inch, 1*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2E86AB')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
        ]))
        
        story.append(table)
        doc.build(story)
        buffer.seek(0)
        
        return send_file(
            buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name='received_loans_report.pdf'
        )
        
    except Exception as e:
        print(f"Received Loans PDF Export Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to export received loans PDF', 'details': str(e)}), 500

# Balance Sheet Export
@app.route('/api/export/balance-sheet/excel', methods=['GET'])
@jwt_required()
def export_balance_sheet_excel():
    """Export balance sheet to Excel"""
    try:
        import xlsxwriter
        from io import BytesIO
        from datetime import datetime
        
        print("Starting balance sheet Excel export...")
        
        # Get all financial data
        db = get_db_connection()
        cursor = db.cursor()
        
        # Get investments
        cursor.execute("SELECT * FROM investments ORDER BY invest_date DESC")
        investments = cursor.fetchall()
        
        # Get receivable loans
        cursor.execute("SELECT * FROM receivable_loans ORDER BY issued_date DESC")
        receivable_loans = cursor.fetchall()
        
        # Get received loans
        cursor.execute("SELECT * FROM received_loans ORDER BY received_date DESC")
        received_loans = cursor.fetchall()
        
        # Get expenses
        cursor.execute("SELECT * FROM expenses ORDER BY expense_date DESC")
        expenses = cursor.fetchall()
        
        cursor.close()
        db.close()
        
        # Calculate totals
        total_investments = sum(float(inv.get('required_amount', 0)) for inv in investments)
        total_receivable = sum(float(loan.get('amount', 0)) for loan in receivable_loans)
        total_received = sum(float(loan.get('amount', 0)) for loan in received_loans)
        total_expenses = sum(float(exp.get('amount', 0)) for exp in expenses)
        
        total_assets = total_investments + total_receivable
        total_liabilities = total_received + total_expenses
        net_worth = total_assets - total_liabilities
        
        print(f"Balance Sheet - Assets: ${total_assets:,.2f}, Liabilities: ${total_liabilities:,.2f}, Net Worth: ${net_worth:,.2f}")
        
        # Create professional Excel file
        buffer = BytesIO()
        workbook = xlsxwriter.Workbook(buffer)
        worksheet = workbook.add_worksheet('Balance Sheet Report')
        
        # Professional formatting
        header_format = workbook.add_format({
            'bold': True, 'font_color': 'white', 'bg_color': '#2E86AB',
            'border': 1, 'align': 'center', 'valign': 'vcenter', 'font_size': 12
        })
        
        company_format = workbook.add_format({
            'bold': True, 'font_size': 16, 'font_color': '#2E86AB', 'align': 'center'
        })
        
        title_format = workbook.add_format({
            'bold': True, 'font_size': 20, 'font_color': '#2E86AB', 'align': 'center'
        })
        
        currency_format = workbook.add_format({
            'num_format': '$#,##0.00', 'border': 1, 'align': 'right', 'font_size': 11
        })
        
        text_format = workbook.add_format({'border': 1, 'align': 'left', 'font_size': 11})
        
        number_format = workbook.add_format({'border': 1, 'align': 'center', 'font_size': 11})
        
        # Header with enhanced styling
        worksheet.merge_range('A1:H1', 'GAAF TRAVEL & LOGISTICS', company_format)
        worksheet.merge_range('A2:H2', 'BALANCE SHEET REPORT', title_format)
        worksheet.merge_range('A3:H3', f'Generated: {datetime.now().strftime("%d/%m/%Y %H:%M")}', 
                             workbook.add_format({'align': 'center', 'italic': True, 'font_size': 10}))
        worksheet.write('A4', '')
        
        # Summary Section
        summary_header_format = workbook.add_format({
            'bg_color': '#2E86AB', 'border': 1, 'bold': True, 'font_color': 'white', 'font_size': 12
        })
        worksheet.merge_range('A5:H5', 'FINANCIAL SUMMARY', summary_header_format)
        
        # Summary details
        summary_format = workbook.add_format({
            'bg_color': '#F8F9FA', 'border': 1, 'bold': True, 'font_color': '#2E86AB', 'font_size': 11
        })
        
        worksheet.merge_range('A6:C6', 'Total Assets:', summary_format)
        worksheet.write('D6', total_assets, workbook.add_format({
            'bg_color': '#F8F9FA', 'border': 1, 'bold': True, 'font_color': '#2E86AB', 
            'num_format': '$#,##0.00', 'font_size': 11
        }))
        worksheet.merge_range('E6:G6', 'Total Liabilities:', summary_format)
        worksheet.write('H6', total_liabilities, workbook.add_format({
            'bg_color': '#F8F9FA', 'border': 1, 'bold': True, 'font_color': '#2E86AB', 
            'num_format': '$#,##0.00', 'font_size': 11
        }))
        
        worksheet.merge_range('A7:C7', 'Net Worth:', summary_format)
        worksheet.write('D7', net_worth, workbook.add_format({
            'bg_color': '#F8F9FA', 'border': 1, 'bold': True, 'font_color': '#2E86AB', 
            'num_format': '$#,##0.00', 'font_size': 11
        }))
        
        worksheet.write('A8', '')
        
        # Assets Section
        assets_header_format = workbook.add_format({
            'bg_color': '#28A745', 'border': 1, 'bold': True, 'font_color': 'white', 'font_size': 12
        })
        worksheet.merge_range('A9:H9', 'ASSETS BREAKDOWN', assets_header_format)
        
        # Assets data
        assets_data = [
            ['Investments', total_investments],
            ['Receivable Loans', total_receivable],
            ['Total Assets', total_assets]
        ]
        
        for row, (item, amount) in enumerate(assets_data, 10):
            worksheet.write(row, 0, item, text_format)
            worksheet.write(row, 1, amount, currency_format)
        
        worksheet.write('A13', '')
        
        # Liabilities Section
        liabilities_header_format = workbook.add_format({
            'bg_color': '#DC3545', 'border': 1, 'bold': True, 'font_color': 'white', 'font_size': 12
        })
        worksheet.merge_range('A14:H14', 'LIABILITIES BREAKDOWN', liabilities_header_format)
        
        # Liabilities data
        liabilities_data = [
            ['Received Loans', total_received],
            ['Monthly Expenses', total_expenses],
            ['Total Liabilities', total_liabilities]
        ]
        
        for row, (item, amount) in enumerate(liabilities_data, 15):
            worksheet.write(row, 0, item, text_format)
            worksheet.write(row, 1, amount, currency_format)
        
        # Enhanced column widths
        column_widths = [25, 15, 15, 15, 15, 15, 15, 15]
        for col, width in enumerate(column_widths):
            worksheet.set_column(col, col, width)
        
        # Add footer
        footer_row = 20
        worksheet.merge_range(f'A{footer_row}:H{footer_row}', 
                             f'Report generated on {datetime.now().strftime("%d/%m/%Y at %H:%M")} | GAAF TRAVEL & LOGISTICS', 
                             workbook.add_format({'align': 'center', 'italic': True, 'font_size': 9, 'font_color': '#666666'}))
        
        # Add page setup
        worksheet.set_landscape()
        worksheet.fit_to_pages(1, 0)
        worksheet.set_margins(0.5, 0.5, 0.5, 0.5)
        
        workbook.close()
        buffer.seek(0)
        
        print("Balance sheet Excel export completed successfully")
        
        return send_file(
            BytesIO(buffer.read()),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='balance_sheet_report.xlsx'
        )
        
    except Exception as e:
        print(f"Balance Sheet Excel Export Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to export balance sheet', 'details': str(e)}), 500

@app.route('/api/export/balance-sheet/pdf', methods=['GET'])
@jwt_required()
def export_balance_sheet_pdf():
    """Export balance sheet to PDF"""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
        from reportlab.lib.units import inch
        from io import BytesIO
        
        # Get all financial data
        db = get_db_connection()
        cursor = db.cursor()
        
        # Get investments
        cursor.execute("SELECT * FROM investments ORDER BY invest_date DESC")
        investments = cursor.fetchall()
        
        # Get receivable loans
        cursor.execute("SELECT * FROM receivable_loans ORDER BY issued_date DESC")
        receivable_loans = cursor.fetchall()
        
        # Get received loans
        cursor.execute("SELECT * FROM received_loans ORDER BY received_date DESC")
        received_loans = cursor.fetchall()
        
        # Get expenses
        cursor.execute("SELECT * FROM expenses ORDER BY expense_date DESC")
        expenses = cursor.fetchall()
        
        cursor.close()
        db.close()
        
        # Calculate totals
        total_investments = sum(float(inv.get('required_amount', 0)) for inv in investments)
        total_receivable = sum(float(loan.get('amount', 0)) for loan in receivable_loans)
        total_received = sum(float(loan.get('amount', 0)) for loan in received_loans)
        total_expenses = sum(float(exp.get('amount', 0)) for exp in expenses)
        
        total_assets = total_investments + total_receivable
        total_liabilities = total_received + total_expenses
        net_worth = total_assets - total_liabilities
        
        # Create PDF
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1*inch, bottomMargin=1*inch)
        styles = getSampleStyleSheet()
        story = []
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle', parent=styles['Heading1'],
            fontSize=24, spaceAfter=30, alignment=1,
            textColor=colors.HexColor('#2E86AB'), fontName='Helvetica-Bold'
        )
        
        company_style = ParagraphStyle(
            'CompanyStyle', parent=styles['Normal'],
            fontSize=14, spaceAfter=10, alignment=1,
            textColor=colors.HexColor('#2E86AB'), fontName='Helvetica-Bold'
        )
        
        # Header
        company = Paragraph("GAAF TRAVEL & LOGISTICS", company_style)
        story.append(company)
        title = Paragraph("BALANCE SHEET REPORT", title_style)
        story.append(title)
        story.append(Spacer(1, 20))
        
        # Summary Section
        summary_header_data = [['FINANCIAL SUMMARY']]
        summary_header_table = Table(summary_header_data, colWidths=[7*inch])
        summary_header_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2E86AB')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 16),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        
        # Summary details
        summary_data = [
            ['Total Assets:', f"${total_assets:,.2f}"],
            ['Total Liabilities:', f"${total_liabilities:,.2f}"],
            ['Net Worth:', f"${net_worth:,.2f}"]
        ]
        
        summary_table = Table(summary_data, colWidths=[3.5*inch, 3.5*inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8F9FA')),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        story.append(summary_header_table)
        story.append(summary_table)
        story.append(Spacer(1, 20))
        
        # Assets and Liabilities side by side
        assets_data = [
            ['ASSETS BREAKDOWN'],
            ['Investments', f"${total_investments:,.2f}"],
            ['Receivable Loans', f"${total_receivable:,.2f}"],
            ['Total Assets', f"${total_assets:,.2f}"]
        ]
        
        liabilities_data = [
            ['LIABILITIES BREAKDOWN'],
            ['Received Loans', f"${total_received:,.2f}"],
            ['Monthly Expenses', f"${total_expenses:,.2f}"],
            ['Total Liabilities', f"${total_liabilities:,.2f}"]
        ]
        
        # Create side-by-side tables
        assets_table = Table(assets_data, colWidths=[2.5*inch, 1.5*inch])
        assets_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#28A745')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        liabilities_table = Table(liabilities_data, colWidths=[2.5*inch, 1.5*inch])
        liabilities_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#DC3545')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        # Combine tables side by side
        combined_data = [[assets_table, liabilities_table]]
        combined_table = Table(combined_data, colWidths=[4*inch, 4*inch])
        combined_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        
        story.append(combined_table)
        doc.build(story)
        buffer.seek(0)
        
        return send_file(
            buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name='balance_sheet_report.pdf'
        )
        
    except Exception as e:
        print(f"Balance Sheet PDF Export Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to export balance sheet PDF', 'details': str(e)}), 500

@app.route('/api/export/invoices/excel', methods=['GET'])
@jwt_required()
def export_invoices_excel():
    """Export invoices to Excel"""
    try:
        from io import BytesIO, StringIO
        import csv
        
        # Try to create proper Excel file using xlsxwriter
        try:
            import xlsxwriter
            excel_available = True
            print("Using xlsxwriter for Excel export")
        except ImportError:
            excel_available = False
            print("xlsxwriter not available, using CSV format")
        
        # Get query parameters
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        status = request.args.get('status')
        
        db = get_db_connection()
        cursor = db.cursor()
        
        # Build query
        query = "SELECT * FROM invoices WHERE 1=1"
        params = []
        
        if date_from:
            query += " AND invoice_date >= %s"
            params.append(date_from)
        if date_to:
            query += " AND invoice_date <= %s"
            params.append(date_to)
        if status:
            query += " AND status = %s"
            params.append(status)
        
        query += " ORDER BY invoice_date DESC"
        
        cursor.execute(query, params)
        invoices = cursor.fetchall()
        
        print(f"DEBUG: Found {len(invoices)} invoices for export")
        print(f"DEBUG: Query: {query}")
        print(f"DEBUG: Params: {params}")
        
        cursor.close()
        db.close()
        
        # Check if we have any data
        if not invoices:
            return jsonify({'error': 'No invoices found for the selected criteria', 'details': 'No data available for export'}), 404
        
        if excel_available:
            try:
                # Create professional Excel file with xlsxwriter
                buffer = BytesIO()
                workbook = xlsxwriter.Workbook(buffer)
                worksheet = workbook.add_worksheet('Invoice Report')
                
                # Define professional formats
                header_format = workbook.add_format({
                    'bold': True,
                    'font_color': 'white',
                    'bg_color': '#2E86AB',
                    'border': 1,
                    'align': 'center',
                    'valign': 'vcenter',
                    'font_size': 12
                })
                
                title_format = workbook.add_format({
                    'bold': True,
                    'font_size': 16,
                    'font_color': '#2E86AB',
                    'align': 'center'
                })
                
                date_format = workbook.add_format({
                    'num_format': 'dd/mm/yyyy',
                    'border': 1,
                    'align': 'center'
                })
                
                currency_format = workbook.add_format({
                    'num_format': '$#,##0.00',
                    'border': 1,
                    'align': 'right'
                })
                
                number_format = workbook.add_format({
                    'border': 1,
                    'align': 'center'
                })
                
                text_format = workbook.add_format({
                    'border': 1,
                    'align': 'left'
                })
                
                status_format = workbook.add_format({
                    'border': 1,
                    'align': 'center',
                    'bold': True
                })
                
                # Add professional header with company branding
                company_format = workbook.add_format({
                    'bold': True,
                    'font_size': 14,
                    'font_color': '#2E86AB',
                    'align': 'left'
                })
                
                title_format = workbook.add_format({
                    'bold': True,
                    'font_size': 18,
                    'font_color': '#2E86AB',
                    'align': 'center'
                })
                
                subtitle_format = workbook.add_format({
                    'font_size': 10,
                    'font_color': '#666666',
                    'align': 'center',
                    'italic': True
                })
                
                # Company header
                worksheet.merge_range('A1:P1', 'GAAF TRAVEL & LOGISTICS', company_format)
                worksheet.merge_range('A2:P2', 'INVOICE TRACKER', title_format)
                worksheet.merge_range('A3:P3', f'Last Update: {datetime.now().strftime("%d/%m/%Y")}', subtitle_format)
                worksheet.write('A4', '')  # Empty row
                
                # Add summary statistics section
                summary_bg_format = workbook.add_format({
                    'bg_color': '#E8F4F8',
                    'border': 1,
                    'align': 'center',
                    'bold': True,
                    'font_color': '#2E86AB'
                })
                
                summary_value_format = workbook.add_format({
                    'bg_color': '#E8F4F8',
                    'border': 1,
                    'align': 'center',
                    'bold': True,
                    'font_size': 12,
                    'font_color': '#2E86AB'
                })
                
                # Calculate statistics
                total_invoices = len(invoices)
                paid_count = len([inv for inv in invoices if inv.get('status', '').upper() == 'PAID'])
                pending_count = len([inv for inv in invoices if inv.get('status', '').upper() in ['SENT', 'DRAFT']])
                overdue_count = len([inv for inv in invoices if inv.get('status', '').upper() == 'OVERDUE'])
                cancelled_count = len([inv for inv in invoices if inv.get('status', '').upper() == 'CANCELLED'])
                
                # Summary row
                worksheet.merge_range('A5:H5', 'SUMMARY STATISTICS', summary_bg_format)
                worksheet.write('I5', 'No. INVOICES', summary_bg_format)
                worksheet.write('J5', 'PAID', summary_bg_format)
                worksheet.write('K5', 'PENDING', summary_bg_format)
                worksheet.write('L5', 'OVERDUE', summary_bg_format)
                worksheet.write('M5', 'CANCELLED', summary_bg_format)
                worksheet.merge_range('N5:P5', f'{datetime.now().strftime("%B %Y")}', summary_bg_format)
                
                # Summary values
                worksheet.write('I6', total_invoices, summary_value_format)
                worksheet.write('J6', paid_count, summary_value_format)
                worksheet.write('K6', pending_count, summary_value_format)
                worksheet.write('L6', overdue_count, summary_value_format)
                worksheet.write('M6', cancelled_count, summary_value_format)
                
                # Calculate totals
                total_amount = sum(float(inv.get('total_amount', 0)) for inv in invoices)
                paid_amount = sum(float(inv.get('total_amount', 0)) for inv in invoices if inv.get('status', '').upper() == 'PAID')
                pending_amount = sum(float(inv.get('total_amount', 0)) for inv in invoices if inv.get('status', '').upper() in ['SENT', 'DRAFT'])
                overdue_amount = sum(float(inv.get('total_amount', 0)) for inv in invoices if inv.get('status', '').upper() == 'OVERDUE')
                
                # Totals row
                totals_bg_format = workbook.add_format({
                    'bg_color': '#2E86AB',
                    'border': 1,
                    'align': 'center',
                    'bold': True,
                    'font_color': 'white',
                    'font_size': 12
                })
                
                worksheet.merge_range('A7:H7', 'TOTALS', totals_bg_format)
                worksheet.write('I7', '', totals_bg_format)
                worksheet.write('J7', f'${paid_amount:,.2f}', totals_bg_format)
                worksheet.write('K7', f'${pending_amount:,.2f}', totals_bg_format)
                worksheet.write('L7', f'${overdue_amount:,.2f}', totals_bg_format)
                worksheet.write('M7', '', totals_bg_format)
                worksheet.merge_range('N7:P7', f'${total_amount:,.2f}', totals_bg_format)
                
                # Add currency selector section like in the design
                currency_bg_format = workbook.add_format({
                    'bg_color': 'white',
                    'border': 1,
                    'align': 'center',
                    'bold': True,
                    'font_color': '#2E86AB'
                })
                
                worksheet.merge_range('A8:C8', 'SELECT CURRENCY', currency_bg_format)
                worksheet.merge_range('D8:F8', '$ DOLLARS', currency_bg_format)
                worksheet.write('A9', '')  # Empty row
                
                # Define column headers to match the invoice tracker design exactly
                headers = [
                    'INVOICE #', 'CUSTOMER ID #', 'CUSTOMER', 'INVOICE DATE', 'DUE DATE', 
                    'INVOICE TOTAL', 'TOTAL PAID', 'OUTSTANDING BALANCE', 'STATUS'
                ]
                
                # Add headers with formatting
                for col, header in enumerate(headers):
                    worksheet.write(10, col, header, header_format)
                
                # Add data with proper formatting to match invoice tracker design
                if invoices:
                    for row, invoice in enumerate(invoices, 11):
                        # Invoice Number
                        worksheet.write(row, 0, invoice.get('invoice_number', ''), text_format)
                        
                        # Customer ID (generate from customer name or use existing)
                        customer_id = invoice.get('customer_reference', f"C{str(invoice.get('id', '')).zfill(3)}")
                        worksheet.write(row, 1, customer_id, text_format)
                        
                        # Customer Name
                        worksheet.write(row, 2, invoice.get('customer_name', ''), text_format)
                        
                        # Invoice Date
                        if invoice.get('invoice_date'):
                            worksheet.write(row, 3, invoice['invoice_date'], date_format)
                        
                        # Due Date
                        if invoice.get('due_date'):
                            worksheet.write(row, 4, invoice['due_date'], date_format)
                        
                        # Invoice Total
                        total_amount = float(invoice.get('total_amount', 0))
                        worksheet.write(row, 5, total_amount, currency_format)
                        
                        # Total Paid (calculate based on status)
                        status = invoice.get('status', '').upper()
                        if status == 'PAID':
                            total_paid = total_amount
                        elif status in ['SENT', 'DRAFT', 'PENDING']:
                            total_paid = 0.0
                        else:
                            # For partially paid, assume some payment
                            total_paid = total_amount * 0.5 if status == 'OVERDUE' else 0.0
                        
                        worksheet.write(row, 6, total_paid, currency_format)
                        
                        # Outstanding Balance
                        outstanding_balance = total_amount - total_paid
                        outstanding_format = workbook.add_format({
                            'num_format': '$#,##0.00',
                            'border': 1,
                            'align': 'right',
                            'bold': True,
                            'font_color': '#DC3545' if outstanding_balance > 0 else '#28A745'
                        })
                        worksheet.write(row, 7, outstanding_balance, outstanding_format)
                        
                        # Status with enhanced color coding like invoice tracker
                        status_colors = {
                            'DRAFT': '#FFC107',      # Yellow
                            'SENT': '#17A2B8',       # Blue
                            'PAID': '#28A745',       # Green
                            'OVERDUE': '#DC3545',    # Red
                            'CANCELLED': '#6C757D',  # Gray
                            'PENDING': '#FF8C00',    # Orange
                            'IN PROGRESS': '#20C997', # Teal
                            'PARTIALLY PAID': '#17A2B8' # Light Blue
                        }
                        
                        # Determine status based on payment
                        if total_paid == 0 and status not in ['PAID']:
                            display_status = 'UNPAID' if status in ['SENT', 'DRAFT'] else status
                        elif total_paid == total_amount:
                            display_status = 'PAID'
                        elif amount_paid > 0:
                            display_status = 'PARTIALLY PAID'
                        else:
                            display_status = status
                        
                        status_color = status_colors.get(display_status, '#6C757D')
                        
                        status_cell_format = workbook.add_format({
                            'border': 1,
                            'align': 'center',
                            'bold': True,
                            'bg_color': status_color,
                            'font_color': 'white',
                            'font_size': 10
                        })
                        worksheet.write(row, 8, display_status, status_cell_format)
                
                # Set column widths to match invoice tracker design
                column_widths = [12, 12, 20, 12, 12, 15, 15, 18, 15]
                for col, width in enumerate(column_widths):
                    worksheet.set_column(col, col, width)
                
                # Add summary section at the bottom
                summary_row = len(invoices) + 13
                worksheet.merge_range(f'A{summary_row}:F{summary_row}', 'DETAILED SUMMARY', workbook.add_format({'bold': True, 'font_size': 14, 'font_color': '#2E86AB'}))
                
                # Calculate totals
                total_invoices = len(invoices)
                total_amount = sum(float(inv.get('total_amount', 0)) for inv in invoices)
                total_subtotal = sum(float(inv.get('subtotal', 0)) for inv in invoices)
                total_tax = sum(float(inv.get('tax_amount', 0)) for inv in invoices)
                
                worksheet.write(summary_row + 1, 0, 'Total Invoices:', workbook.add_format({'bold': True}))
                worksheet.write(summary_row + 1, 1, total_invoices, number_format)
                
                worksheet.write(summary_row + 2, 0, 'Total Subtotal:', workbook.add_format({'bold': True}))
                worksheet.write(summary_row + 2, 1, total_subtotal, currency_format)
                
                worksheet.write(summary_row + 3, 0, 'Total Tax:', workbook.add_format({'bold': True}))
                worksheet.write(summary_row + 3, 1, total_tax, currency_format)
                
                worksheet.write(summary_row + 4, 0, 'Total Amount:', workbook.add_format({'bold': True, 'font_size': 12}))
                worksheet.write(summary_row + 4, 1, total_amount, workbook.add_format({'bold': True, 'num_format': '$#,##0.00', 'font_size': 12}))
                
                workbook.close()
                buffer.seek(0)
                print(f"DEBUG: Professional Excel buffer size: {len(buffer.getvalue())} bytes")
                return send_file(buffer, as_attachment=True, download_name='invoices_report.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            except Exception as excel_error:
                print(f"DEBUG: Excel creation failed: {excel_error}")
                print("DEBUG: Falling back to CSV format")
                excel_available = False
        
        if not excel_available:
            # Fallback to CSV
            output = StringIO()
            if invoices:
                fieldnames = invoices[0].keys()
                writer = csv.DictWriter(output, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(invoices)
            
            csv_content = output.getvalue()
            print(f"DEBUG: CSV content length: {len(csv_content)} characters")
            print(f"DEBUG: CSV preview: {csv_content[:200]}...")
            
            return send_file(
                BytesIO(csv_content.encode('utf-8')),
                as_attachment=True,
                download_name='invoices_report.csv',
                mimetype='text/csv'
            )
        
    except Exception as e:
        print(f"Error exporting invoices Excel: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to export Excel', 'details': str(e)}), 500

@app.route('/api/export/invoices/csv', methods=['GET'])
@jwt_required()
def export_invoices_csv():
    """Export invoices to CSV (fallback when pandas is not available)"""
    try:
        import csv
        from io import StringIO
        
        # Get query parameters
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        status = request.args.get('status')
        
        db = get_db_connection()
        cursor = db.cursor()
        
        # Build query
        query = "SELECT * FROM invoices WHERE 1=1"
        params = []
        
        if date_from:
            query += " AND invoice_date >= %s"
            params.append(date_from)
        if date_to:
            query += " AND invoice_date <= %s"
            params.append(date_to)
        if status:
            query += " AND status = %s"
            params.append(status)
        
        query += " ORDER BY invoice_date DESC"
        
        cursor.execute(query, params)
        invoices = cursor.fetchall()
        
        cursor.close()
        db.close()
        
        # Create CSV
        output = StringIO()
        if invoices:
            fieldnames = invoices[0].keys()
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(invoices)
        
        output.seek(0)
        return send_file(
            BytesIO(output.getvalue().encode('utf-8')),
            as_attachment=True,
            download_name='invoices_report.csv',
            mimetype='text/csv'
        )
        
    except Exception as e:
        print(f"Error exporting invoices CSV: {e}")
        return jsonify({'error': 'Failed to export CSV', 'details': str(e)}), 500

@app.route('/api/export/receipts/pdf', methods=['GET'])
@jwt_required()
def export_receipts_pdf():
    """Export receipts to PDF"""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib import colors
        from io import BytesIO
        
        # Get query parameters
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        status = request.args.get('status')
        
        db = get_db_connection()
        cursor = db.cursor()
        
        # Build query
        query = "SELECT * FROM receipts WHERE 1=1"
        params = []
        
        if date_from:
            query += " AND receipt_date >= %s"
            params.append(date_from)
        if date_to:
            query += " AND receipt_date <= %s"
            params.append(date_to)
        if status:
            query += " AND status = %s"
            params.append(status)
        
        query += " ORDER BY receipt_date DESC"
        
        cursor.execute(query, params)
        receipts = cursor.fetchall()
        
        cursor.close()
        db.close()
        
        # Create professional PDF
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1*inch, bottomMargin=1*inch)
        styles = getSampleStyleSheet()
        story = []
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            alignment=1,  # Center alignment
            textColor=colors.HexColor('#28A745'),
            fontName='Helvetica-Bold'
        )
        
        subtitle_style = ParagraphStyle(
            'CustomSubtitle',
            parent=styles['Normal'],
            fontSize=12,
            spaceAfter=20,
            alignment=1,  # Center alignment
            textColor=colors.HexColor('#666666'),
            fontName='Helvetica'
        )
        
        # Header
        title = Paragraph("RECEIPT REPORT", title_style)
        story.append(title)
        
        subtitle = Paragraph(f"Generated on: {datetime.now().strftime('%d/%m/%Y at %H:%M')}", subtitle_style)
        story.append(subtitle)
        story.append(Spacer(1, 20))
        
        # Summary section
        total_receipts = len(receipts)
        total_amount = sum(float(rec.get('total_amount', 0)) for rec in receipts)
        
        summary_data = [
            ['SUMMARY', '', ''],
            ['Total Receipts:', str(total_receipts), 'Total Amount:', f"${total_amount:,.2f}"]
        ]
        
        summary_table = Table(summary_data, colWidths=[2*inch, 1.5*inch, 2*inch, 1.5*inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#28A745')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('FONTSIZE', (0, 1), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F8F9FA')),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
        ]))
        
        story.append(summary_table)
        story.append(Spacer(1, 20))
        
        # Main data table
        if receipts:
            data = [['Receipt #', 'Date', 'Received From', 'Amount', 'Status']]
            for receipt in receipts:
                data.append([
                    receipt.get('receipt_number', ''),
                    str(receipt.get('receipt_date', '')),
                    receipt.get('received_from', ''),
                    f"${float(receipt.get('total_amount', 0)):,.2f}",
                    receipt.get('status', '').upper()
                ])
            
            # Calculate column widths
            table_width = 7.5 * inch
            col_widths = [
                table_width * 0.20,  # Receipt #
                table_width * 0.15,  # Date
                table_width * 0.35,  # Received From
                table_width * 0.15,  # Amount
                table_width * 0.15   # Status
            ]
            
            table = Table(data, colWidths=col_widths)
            table.setStyle(TableStyle([
                # Header row
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#28A745')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('TOPPADDING', (0, 0), (-1, 0), 12),
                
                # Data rows
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('ALIGN', (0, 1), (0, -1), 'LEFT'),  # Receipt # left aligned
                ('ALIGN', (1, 1), (1, -1), 'CENTER'),  # Date centered
                ('ALIGN', (2, 1), (2, -1), 'LEFT'),  # Received From left aligned
                ('ALIGN', (3, 1), (3, -1), 'RIGHT'),  # Amount right aligned
                ('ALIGN', (4, 1), (4, -1), 'CENTER'),  # Status centered
                
                # Grid and borders
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
                ('LINEBELOW', (0, 0), (-1, 0), 2, colors.HexColor('#28A745')),
                
                # Alternating row colors
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8F9FA')]),
                
                # Status color coding
                ('TEXTCOLOR', (4, 1), (4, -1), colors.white),
                ('BACKGROUND', (4, 1), (4, -1), colors.HexColor('#6C757D')),
                
                # Padding
                ('TOPPADDING', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
                ('LEFTPADDING', (0, 1), (-1, -1), 6),
                ('RIGHTPADDING', (0, 1), (-1, -1), 6),
            ]))
            
            # Apply status-specific colors
            for i, receipt in enumerate(receipts, 1):
                status = receipt.get('status', '').upper()
                status_color = {
                    'DRAFT': colors.HexColor('#FFC107'),
                    'CONFIRMED': colors.HexColor('#28A745'),
                    'CANCELLED': colors.HexColor('#DC3545')
                }.get(status, colors.HexColor('#6C757D'))
                
                table.setStyle(TableStyle([
                    ('BACKGROUND', (4, i), (4, i), status_color),
                    ('TEXTCOLOR', (4, i), (4, i), colors.white)
                ]))
            
            story.append(table)
        else:
            no_data = Paragraph("No receipts found for the selected criteria.", styles['Normal'])
            story.append(no_data)
        
        doc.build(story)
        
        buffer.seek(0)
        return send_file(buffer, as_attachment=True, download_name='receipts_report.pdf', mimetype='application/pdf')
        
    except Exception as e:
        print(f"Error exporting receipts PDF: {e}")
        return jsonify({'error': 'Failed to export PDF', 'details': str(e)}), 500

@app.route('/api/export/receipts/excel', methods=['GET'])
@jwt_required()
def export_receipts_excel():
    """Export receipts to Excel"""
    try:
        from io import BytesIO, StringIO
        import csv
        
        # Try to create proper Excel file using xlsxwriter
        try:
            import xlsxwriter
            excel_available = True
            print("Using xlsxwriter for Excel export")
        except ImportError:
            excel_available = False
            print("xlsxwriter not available, using CSV format")
        
        # Get query parameters
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        status = request.args.get('status')
        
        db = get_db_connection()
        cursor = db.cursor()
        
        # Build query
        query = "SELECT * FROM receipts WHERE 1=1"
        params = []
        
        if date_from:
            query += " AND receipt_date >= %s"
            params.append(date_from)
        if date_to:
            query += " AND receipt_date <= %s"
            params.append(date_to)
        if status:
            query += " AND status = %s"
            params.append(status)
        
        query += " ORDER BY receipt_date DESC"
        
        cursor.execute(query, params)
        receipts = cursor.fetchall()
        
        print(f"DEBUG: Found {len(receipts)} receipts for export")
        print(f"DEBUG: Query: {query}")
        print(f"DEBUG: Params: {params}")
        
        cursor.close()
        db.close()
        
        # Check if we have any data
        if not receipts:
            return jsonify({'error': 'No receipts found for the selected criteria', 'details': 'No data available for export'}), 404
        
        if excel_available:
            try:
                # Create professional Excel file with xlsxwriter
                buffer = BytesIO()
                workbook = xlsxwriter.Workbook(buffer)
                worksheet = workbook.add_worksheet('Receipt Report')
                
                # Define professional formats
                header_format = workbook.add_format({
                    'bold': True,
                    'font_color': 'white',
                    'bg_color': '#28A745',
                    'border': 1,
                    'align': 'center',
                    'valign': 'vcenter',
                    'font_size': 12
                })
                
                title_format = workbook.add_format({
                    'bold': True,
                    'font_size': 16,
                    'font_color': '#28A745',
                    'align': 'center'
                })
                
                date_format = workbook.add_format({
                    'num_format': 'dd/mm/yyyy',
                    'border': 1,
                    'align': 'center'
                })
                
                currency_format = workbook.add_format({
                    'num_format': '$#,##0.00',
                    'border': 1,
                    'align': 'right'
                })
                
                number_format = workbook.add_format({
                    'border': 1,
                    'align': 'center'
                })
                
                text_format = workbook.add_format({
                    'border': 1,
                    'align': 'left'
                })
                
                # Add title
                worksheet.merge_range('A1:H1', 'RECEIPT REPORT', title_format)
                worksheet.merge_range('A2:H2', f'Generated on: {datetime.now().strftime("%d/%m/%Y %H:%M")}', workbook.add_format({'align': 'center', 'italic': True}))
                worksheet.write('A3', '')  # Empty row
                
                # Define column headers with proper names
                headers = [
                    'Receipt #', 'Date', 'Received From', 'Total Amount', 'Notes', 'Status',
                    'Created By', 'Created At'
                ]
                
                # Add headers with formatting
                for col, header in enumerate(headers):
                    worksheet.write(4, col, header, header_format)
                
                # Add data with proper formatting
                if receipts:
                    for row, receipt in enumerate(receipts, 5):
                        # Receipt Number
                        worksheet.write(row, 0, receipt.get('receipt_number', ''), text_format)
                        
                        # Date
                        if receipt.get('receipt_date'):
                            worksheet.write(row, 1, receipt['receipt_date'], date_format)
                        
                        # Received From
                        worksheet.write(row, 2, receipt.get('received_from', ''), text_format)
                        
                        # Total Amount
                        worksheet.write(row, 3, float(receipt.get('total_amount', 0)), currency_format)
                        
                        # Notes
                        worksheet.write(row, 4, receipt.get('notes', ''), text_format)
                        
                        # Status with color coding
                        status = receipt.get('status', '').upper()
                        status_color = {
                            'DRAFT': '#FFC107',
                            'CONFIRMED': '#28A745',
                            'CANCELLED': '#DC3545'
                        }.get(status, '#6C757D')
                        
                        status_cell_format = workbook.add_format({
                            'border': 1,
                            'align': 'center',
                            'bold': True,
                            'bg_color': status_color,
                            'font_color': 'white'
                        })
                        worksheet.write(row, 5, status, status_cell_format)
                        
                        # System Info
                        worksheet.write(row, 6, receipt.get('created_by', ''), number_format)
                        if receipt.get('created_at'):
                            worksheet.write(row, 7, receipt['created_at'], date_format)
                
                # Set column widths for better readability
                column_widths = [15, 12, 25, 15, 30, 12, 10, 15]
                for col, width in enumerate(column_widths):
                    worksheet.set_column(col, col, width)
                
                # Add summary section
                summary_row = len(receipts) + 7
                worksheet.merge_range(f'A{summary_row}:D{summary_row}', 'SUMMARY', workbook.add_format({'bold': True, 'font_size': 14, 'font_color': '#28A745'}))
                
                # Calculate totals
                total_receipts = len(receipts)
                total_amount = sum(float(rec.get('total_amount', 0)) for rec in receipts)
                
                worksheet.write(summary_row + 1, 0, 'Total Receipts:', workbook.add_format({'bold': True}))
                worksheet.write(summary_row + 1, 1, total_receipts, number_format)
                
                worksheet.write(summary_row + 2, 0, 'Total Amount:', workbook.add_format({'bold': True, 'font_size': 12}))
                worksheet.write(summary_row + 2, 1, total_amount, workbook.add_format({'bold': True, 'num_format': '$#,##0.00', 'font_size': 12}))
                
                workbook.close()
                buffer.seek(0)
                print(f"DEBUG: Professional Excel buffer size: {len(buffer.getvalue())} bytes")
                return send_file(buffer, as_attachment=True, download_name='receipts_report.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            except Exception as excel_error:
                print(f"DEBUG: Excel creation failed: {excel_error}")
                print("DEBUG: Falling back to CSV format")
                excel_available = False
        
        if not excel_available:
            # Fallback to CSV
            output = StringIO()
            if receipts:
                fieldnames = receipts[0].keys()
                writer = csv.DictWriter(output, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(receipts)
            
            csv_content = output.getvalue()
            print(f"DEBUG: CSV content length: {len(csv_content)} characters")
            print(f"DEBUG: CSV preview: {csv_content[:200]}...")
            
            return send_file(
                BytesIO(csv_content.encode('utf-8')),
                as_attachment=True,
                download_name='receipts_report.csv',
                mimetype='text/csv'
            )
        
    except Exception as e:
        print(f"Error exporting receipts Excel: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to export Excel', 'details': str(e)}), 500

@app.route('/api/export/receipts/csv', methods=['GET'])
@jwt_required()
def export_receipts_csv():
    """Export receipts to CSV (fallback when pandas is not available)"""
    try:
        import csv
        from io import StringIO, BytesIO
        
        # Get query parameters
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        status = request.args.get('status')
        
        db = get_db_connection()
        cursor = db.cursor()
        
        # Build query
        query = "SELECT * FROM receipts WHERE 1=1"
        params = []
        
        if date_from:
            query += " AND receipt_date >= %s"
            params.append(date_from)
        if date_to:
            query += " AND receipt_date <= %s"
            params.append(date_to)
        if status:
            query += " AND status = %s"
            params.append(status)
        
        query += " ORDER BY receipt_date DESC"
        
        cursor.execute(query, params)
        receipts = cursor.fetchall()
        
        cursor.close()
        db.close()
        
        # Create CSV
        output = StringIO()
        if receipts:
            fieldnames = receipts[0].keys()
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(receipts)
        
        csv_content = output.getvalue()
        return send_file(
            BytesIO(csv_content.encode('utf-8')),
            as_attachment=True,
            download_name='receipts_report.csv',
            mimetype='text/csv'
        )
        
    except Exception as e:
        print(f"Error exporting receipts CSV: {e}")
        return jsonify({'error': 'Failed to export CSV', 'details': str(e)}), 500


# ---------------- RUN APP ----------------
if __name__ == '__main__':
    try:
        # First, ensure the basic user system is set up
        ensure_default_user()  # Make sure default user exists
        ensure_user_module_permissions_table()  # Make sure user module permissions table exists
        
        # Then set up other tables (these can be created on-demand)
        ensure_tickets_table()  # Make sure tickets table exists
        ensure_visas_table()
        ensure_cargo_table()
        ensure_transport_table()
        ensure_financial_tables()
        # ensure_website_content_tables()  # Make sure website content tables exist
        # ensure_invoice_receipt_tables()  # Make sure invoice and receipt tables exist
        
        print("✅ Database initialization completed successfully!")
        print(f"✅ Super Admin user created: {DEFAULT_EMAIL}")
        print(f"✅ Password: {DEFAULT_PASSWORD}")
        
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        print("Please check your MySQL connection and try again.")
        # Still run the app even if initialization fails
        pass
    
    # Get port from environment variable (for production)
    port = int(os.getenv('PORT', 5000))
    
    # Start the Flask server
    app.run(debug=os.getenv('FLASK_ENV') != 'production', host='0.0.0.0', port=port)
