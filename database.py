import sqlite3
import os
from datetime import date, datetime

DB_PATH = "travel_planner.db"

def migrate_db():
    """Add new columns if they don't exist (handles schema upgrades)."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # --- Columns for 'trips' table ---
    trip_columns = [("budget", "REAL DEFAULT 0")]
    
    # --- Columns for 'itinerary_items' table ---
    item_columns = [("is_confirmed", "INTEGER DEFAULT 0")]
    
    # --- Columns for 'executives' table (new preferences) ---
    exec_columns = [
        ("passport_number", "TEXT"),
        ("preferred_airline", "TEXT"),
        ("tsa_precheck", "TEXT"),
        ("meal_preference", "TEXT")
    ]
    
    # Get existing columns for each table
    c.execute("PRAGMA table_info(trips)")
    existing_trips = [row[1] for row in c.fetchall()]
    
    c.execute("PRAGMA table_info(itinerary_items)")
    existing_items = [row[1] for row in c.fetchall()]
    
    c.execute("PRAGMA table_info(executives)")
    existing_execs = [row[1] for row in c.fetchall()]
    
    # Add missing columns
    for col_name, col_type in trip_columns:
        if col_name not in existing_trips:
            c.execute(f"ALTER TABLE trips ADD COLUMN {col_name} {col_type}")
    
    for col_name, col_type in item_columns:
        if col_name not in existing_items:
            c.execute(f"ALTER TABLE itinerary_items ADD COLUMN {col_name} {col_type}")
    
    for col_name, col_type in exec_columns:
        if col_name not in existing_execs:
            c.execute(f"ALTER TABLE executives ADD COLUMN {col_name} {col_type}")
    
    conn.commit()
    conn.close()

def init_db():
    """Create all tables if they don't exist, then run migrations."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Companies
    c.execute('''CREATE TABLE IF NOT EXISTS companies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        default_cost_center TEXT,
        policy_notes TEXT
    )''')
    
    # Executives
    c.execute('''CREATE TABLE IF NOT EXISTS executives (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER,
        name TEXT NOT NULL,
        email TEXT,
        timezone TEXT DEFAULT 'America/New_York',
        seat_preference TEXT,
        hotel_loyalty TEXT,
        frequent_flyer_number TEXT,
        dietary_restrictions TEXT,
        FOREIGN KEY (company_id) REFERENCES companies(id)
    )''')
    
    # Trips
    c.execute('''CREATE TABLE IF NOT EXISTS trips (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        exec_id INTEGER,
        destination TEXT NOT NULL,
        start_date TEXT,
        end_date TEXT,
        purpose TEXT,
        status TEXT DEFAULT 'draft',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (exec_id) REFERENCES executives(id)
    )''')
    
    # Itinerary Items
    c.execute('''CREATE TABLE IF NOT EXISTS itinerary_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trip_id INTEGER,
        item_type TEXT,
        datetime_start TEXT,
        datetime_end TEXT,
        description TEXT,
        location TEXT,
        cost REAL,
        confirmation_code TEXT,
        notes TEXT,
        FOREIGN KEY (trip_id) REFERENCES trips(id)
    )''')
    
    conn.commit()
    conn.close()
    
    # Run migrations to add new columns
    migrate_db()

# --- COMPANY MANAGEMENT ---

def add_company(name, default_cost_center=None, policy_notes=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO companies (name, default_cost_center, policy_notes)
        VALUES (?, ?, ?)
    """, (name, default_cost_center, policy_notes))
    conn.commit()
    new_id = c.lastrowid
    conn.close()
    return new_id

def get_all_companies():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, name FROM companies ORDER BY name")
    rows = c.fetchall()
    conn.close()
    return rows

def get_company(company_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM companies WHERE id = ?", (company_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

# --- EXECUTIVE MANAGEMENT ---

def add_executive(company_id, name, email, timezone, seat_preference, hotel_loyalty,
                  frequent_flyer_number, dietary_restrictions, passport_number=None,
                  preferred_airline=None, tsa_precheck=None, meal_preference=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO executives 
        (company_id, name, email, timezone, seat_preference, hotel_loyalty,
         frequent_flyer_number, dietary_restrictions, passport_number,
         preferred_airline, tsa_precheck, meal_preference)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (company_id, name, email, timezone, seat_preference, hotel_loyalty,
          frequent_flyer_number, dietary_restrictions, passport_number,
          preferred_airline, tsa_precheck, meal_preference))
    conn.commit()
    new_id = c.lastrowid
    conn.close()
    return new_id

def get_all_executives():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT e.id, e.name, c.name 
        FROM executives e
        JOIN companies c ON e.company_id = c.id
    """)
    rows = c.fetchall()
    conn.close()
    return rows

def get_executive_profile(exec_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT e.*, c.name as company_name, c.default_cost_center, c.policy_notes
        FROM executives e
        JOIN companies c ON e.company_id = c.id
        WHERE e.id = ?
    """, (exec_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def get_full_executive_profile(exec_id):
    raw = get_executive_profile(exec_id)
    if not raw:
        return None
    return {
        "Name": raw.get('name', ''),
        "Email": raw.get('email', ''),
        "Timezone": raw.get('timezone', ''),
        "Seat Preference": raw.get('seat_preference', ''),
        "Hotel Loyalty": raw.get('hotel_loyalty', ''),
        "Frequent Flyer": raw.get('frequent_flyer_number', ''),
        "Dietary": raw.get('dietary_restrictions', ''),
        "Company": raw.get('company_name', ''),
        "Cost Center": raw.get('default_cost_center', ''),
        "Policy Notes": raw.get('policy_notes', ''),
        "Passport Number": raw.get('passport_number', ''),
        "Preferred Airline": raw.get('preferred_airline', ''),
        "TSA PreCheck": raw.get('tsa_precheck', ''),
        "Meal Preference": raw.get('meal_preference', '')
    }

# --- TRIP MANAGEMENT ---

def create_or_get_trip(exec_id, destination, start_date, end_date, purpose):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT id FROM trips
        WHERE exec_id = ? AND destination = ? AND start_date = ? AND status = 'draft'
        ORDER BY created_at DESC LIMIT 1
    """, (exec_id, destination, start_date))
    row = c.fetchone()
    if row:
        trip_id = row[0]
    else:
        c.execute("""
            INSERT INTO trips (exec_id, destination, start_date, end_date, purpose, status)
            VALUES (?, ?, ?, ?, ?, 'draft')
        """, (exec_id, destination, start_date, end_date, purpose))
        trip_id = c.lastrowid
        conn.commit()
    conn.close()
    return trip_id

def get_trip(trip_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM trips WHERE id = ?", (trip_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def update_trip_budget(trip_id, budget):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE trips SET budget = ? WHERE id = ?", (budget, trip_id))
    conn.commit()
    conn.close()

def update_trip_status(trip_id, status):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE trips SET status = ? WHERE id = ?", (status, trip_id))
    conn.commit()
    conn.close()

# --- ITINERARY ITEMS ---

def add_itinerary_item(trip_id, item_type, description, datetime_start, datetime_end,
                       location, cost, confirmation_code, notes, is_confirmed=0):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO itinerary_items 
        (trip_id, item_type, description, datetime_start, datetime_end, location,
         cost, confirmation_code, notes, is_confirmed)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (trip_id, item_type, description, datetime_start, datetime_end, location,
          cost, confirmation_code, notes, is_confirmed))
    conn.commit()
    conn.close()

def get_items_for_trip(trip_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT * FROM itinerary_items
        WHERE trip_id = ?
        ORDER BY datetime_start ASC
    """, (trip_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# --- BUDGET & SPENDING FUNCTIONS ---

def get_trip_spending(trip_id):
    """Calculate total estimated, confirmed, and overall spend for a trip."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute("SELECT COALESCE(SUM(cost), 0) FROM itinerary_items WHERE trip_id = ?", (trip_id,))
    total_all = c.fetchone()[0]
    
    c.execute("SELECT COALESCE(SUM(cost), 0) FROM itinerary_items WHERE trip_id = ? AND is_confirmed = 1", (trip_id,))
    total_confirmed = c.fetchone()[0]
    
    c.execute("SELECT COALESCE(SUM(cost), 0) FROM itinerary_items WHERE trip_id = ? AND is_confirmed = 0", (trip_id,))
    total_estimated = c.fetchone()[0]
    
    conn.close()
    return {
        'total_all': total_all,
        'total_confirmed': total_confirmed,
        'total_estimated': total_estimated
    }

def get_spending_summary(exec_id=None, company_id=None, start_date=None, end_date=None):
    """Aggregate spending across trips with optional filters."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    query = """
        SELECT 
            t.id as trip_id,
            e.name as executive_name,
            c.name as company_name,
            t.destination,
            t.start_date,
            t.end_date,
            t.budget,
            t.status,
            COALESCE(SUM(i.cost), 0) as total_spent,
            COALESCE(SUM(CASE WHEN i.is_confirmed = 1 THEN i.cost ELSE 0 END), 0) as confirmed_spent,
            COALESCE(SUM(CASE WHEN i.is_confirmed = 0 THEN i.cost ELSE 0 END), 0) as estimated_spent
        FROM trips t
        JOIN executives e ON t.exec_id = e.id
        JOIN companies c ON e.company_id = c.id
        LEFT JOIN itinerary_items i ON t.id = i.trip_id
        WHERE 1=1
    """
    params = []
    
    if exec_id:
        query += " AND e.id = ?"
        params.append(exec_id)
    if company_id:
        query += " AND c.id = ?"
        params.append(company_id)
    if start_date:
        query += " AND t.start_date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND t.end_date <= ?"
        params.append(end_date)
    
    query += " GROUP BY t.id ORDER BY t.start_date DESC"
    
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]