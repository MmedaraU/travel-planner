import sqlite3
import os
from datetime import date, datetime

DB_PATH = "travel_planner.db"


def migrate_db():
    """Add new columns if they don't exist (handles schema upgrades)."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # --- Columns for 'trips' table ---
    c.execute("PRAGMA table_info(trips)")
    existing_trips = [row[1] for row in c.fetchall()]

    if "budget" not in existing_trips:
        c.execute("ALTER TABLE trips ADD COLUMN budget REAL DEFAULT 0")
    if "departure_city" not in existing_trips:
        c.execute("ALTER TABLE trips ADD COLUMN departure_city TEXT")
    if "departure_region" not in existing_trips:
        c.execute("ALTER TABLE trips ADD COLUMN departure_region TEXT")
    if "departure_country" not in existing_trips:
        c.execute("ALTER TABLE trips ADD COLUMN departure_country TEXT")
    if "base_currency" not in existing_trips:
        c.execute("ALTER TABLE trips ADD COLUMN base_currency TEXT DEFAULT 'USD'")
    if "display_currency" not in existing_trips:
        c.execute("ALTER TABLE trips ADD COLUMN display_currency TEXT DEFAULT 'USD'")

    # --- Columns for 'itinerary_items' table ---
    c.execute("PRAGMA table_info(itinerary_items)")
    existing_items = [row[1] for row in c.fetchall()]

    if "is_confirmed" not in existing_items:
        c.execute(
            "ALTER TABLE itinerary_items ADD COLUMN is_confirmed INTEGER DEFAULT 0"
        )
    if "receipt_path" not in existing_items:
        c.execute("ALTER TABLE itinerary_items ADD COLUMN receipt_path TEXT")
    if "cost_currency" not in existing_items:
        c.execute(
            "ALTER TABLE itinerary_items ADD COLUMN cost_currency TEXT DEFAULT 'USD'"
        )
    if "exchange_rate_snapshot" not in existing_items:
        c.execute(
            "ALTER TABLE itinerary_items ADD COLUMN exchange_rate_snapshot REAL DEFAULT 1.0"
        )

    # --- Columns for 'executives' table (new preferences) ---
    c.execute("PRAGMA table_info(executives)")
    existing_execs = [row[1] for row in c.fetchall()]

    new_exec_columns = [
        ("passport_number", "TEXT"),
        ("preferred_airline", "TEXT"),
        ("tsa_precheck", "TEXT"),
        ("meal_preference", "TEXT"),
    ]
    for col_name, col_type in new_exec_columns:
        if col_name not in existing_execs:
            c.execute(f"ALTER TABLE executives ADD COLUMN {col_name} {col_type}")

    # --- Create executive_memberships table ---
    c.execute("""CREATE TABLE IF NOT EXISTS executive_memberships (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        exec_id INTEGER NOT NULL,
        category TEXT NOT NULL,  -- 'airline', 'hotel', 'car'
        program_name TEXT NOT NULL,
        membership_number TEXT NOT NULL,
        FOREIGN KEY (exec_id) REFERENCES executives(id) ON DELETE CASCADE
    )""")

    # --- Create trip_stops table (for multi‑city trips) ---
    c.execute("""CREATE TABLE IF NOT EXISTS trip_stops (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trip_id INTEGER NOT NULL,
        stop_order INTEGER NOT NULL,
        city TEXT NOT NULL,
        country TEXT,
        region TEXT,
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        notes TEXT,
        FOREIGN KEY (trip_id) REFERENCES trips(id) ON DELETE CASCADE
    )""")

    # --- Create categories table (for custom itinerary item types) ---
    c.execute("""CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL
    )""")

    # --- Seed default categories if table is empty ---
    c.execute("SELECT COUNT(*) FROM categories")
    if c.fetchone()[0] == 0:
        default_cats = ["Flight", "Hotel", "Meeting", "Transport"]
        for cat in default_cats:
            c.execute("INSERT INTO categories (name) VALUES (?)", (cat,))

    # --- NEW: Create trip_templates table ---
    c.execute("""CREATE TABLE IF NOT EXISTS trip_templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        departure_city TEXT,
        departure_region TEXT,
        departure_country TEXT,
        display_currency TEXT DEFAULT 'USD',
        base_currency TEXT DEFAULT 'USD',
        stops_json TEXT,  -- JSON array of stops
        items_json TEXT   -- JSON array of itinerary items
    )""")

    conn.commit()
    conn.close()


def init_db():
    """Create all tables if they don't exist, then run migrations."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Companies
    c.execute("""CREATE TABLE IF NOT EXISTS companies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        default_cost_center TEXT,
        policy_notes TEXT
    )""")

    # Executives
    c.execute("""CREATE TABLE IF NOT EXISTS executives (
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
    )""")

    # Trips
    c.execute("""CREATE TABLE IF NOT EXISTS trips (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        exec_id INTEGER,
        destination TEXT NOT NULL,
        start_date TEXT,
        end_date TEXT,
        purpose TEXT,
        status TEXT DEFAULT 'draft',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (exec_id) REFERENCES executives(id)
    )""")

    # Itinerary Items
    c.execute("""CREATE TABLE IF NOT EXISTS itinerary_items (
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
        FOREIGN KEY (trip_id) REFERENCES trips(id) ON DELETE CASCADE
    )""")

    conn.commit()
    conn.close()

    # Run migrations to add new columns and tables
    migrate_db()


# =========================================================
# COMPANY MANAGEMENT
# =========================================================
def add_company(name, default_cost_center=None, policy_notes=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO companies (name, default_cost_center, policy_notes) VALUES (?, ?, ?)",
        (name, default_cost_center, policy_notes),
    )
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


# =========================================================
# EXECUTIVE MANAGEMENT
# =========================================================
def add_executive(
    company_id,
    name,
    email,
    timezone,
    seat_preference,
    hotel_loyalty,
    frequent_flyer_number,
    dietary_restrictions,
    passport_number=None,
    preferred_airline=None,
    tsa_precheck=None,
    meal_preference=None,
):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO executives 
        (company_id, name, email, timezone, seat_preference, hotel_loyalty,
         frequent_flyer_number, dietary_restrictions, passport_number,
         preferred_airline, tsa_precheck, meal_preference)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            company_id,
            name,
            email,
            timezone,
            seat_preference,
            hotel_loyalty,
            frequent_flyer_number,
            dietary_restrictions,
            passport_number,
            preferred_airline,
            tsa_precheck,
            meal_preference,
        ),
    )
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
    c.execute(
        """
        SELECT e.*, c.name as company_name, c.default_cost_center, c.policy_notes
        FROM executives e
        JOIN companies c ON e.company_id = c.id
        WHERE e.id = ?
    """,
        (exec_id,),
    )
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def get_full_executive_profile(exec_id):
    raw = get_executive_profile(exec_id)
    if not raw:
        return None
    return {
        "Name": raw.get("name", ""),
        "Email": raw.get("email", ""),
        "Timezone": raw.get("timezone", ""),
        "Seat Preference": raw.get("seat_preference", ""),
        "Hotel Loyalty": raw.get("hotel_loyalty", ""),
        "Frequent Flyer": raw.get("frequent_flyer_number", ""),
        "Dietary": raw.get("dietary_restrictions", ""),
        "Company": raw.get("company_name", ""),
        "Cost Center": raw.get("default_cost_center", ""),
        "Policy Notes": raw.get("policy_notes", ""),
        "Passport Number": raw.get("passport_number", ""),
        "Preferred Airline": raw.get("preferred_airline", ""),
        "TSA PreCheck": raw.get("tsa_precheck", ""),
        "Meal Preference": raw.get("meal_preference", ""),
    }


def update_executive(
    exec_id,
    company_id,
    name,
    email,
    timezone,
    seat_preference,
    hotel_loyalty,
    frequent_flyer_number,
    dietary_restrictions,
    passport_number,
    preferred_airline,
    tsa_precheck,
    meal_preference,
):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        UPDATE executives SET
            company_id = ?,
            name = ?,
            email = ?,
            timezone = ?,
            seat_preference = ?,
            hotel_loyalty = ?,
            frequent_flyer_number = ?,
            dietary_restrictions = ?,
            passport_number = ?,
            preferred_airline = ?,
            tsa_precheck = ?,
            meal_preference = ?
        WHERE id = ?
    """,
        (
            company_id,
            name,
            email,
            timezone,
            seat_preference,
            hotel_loyalty,
            frequent_flyer_number,
            dietary_restrictions,
            passport_number,
            preferred_airline,
            tsa_precheck,
            meal_preference,
            exec_id,
        ),
    )
    conn.commit()
    conn.close()


# =========================================================
# EXECUTIVE MEMBERSHIPS
# =========================================================
def add_membership(exec_id, category, program_name, membership_number):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO executive_memberships (exec_id, category, program_name, membership_number)
        VALUES (?, ?, ?, ?)
    """,
        (exec_id, category, program_name, membership_number),
    )
    conn.commit()
    new_id = c.lastrowid
    conn.close()
    return new_id


def get_memberships(exec_id, category=None):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    if category:
        c.execute(
            """
            SELECT * FROM executive_memberships
            WHERE exec_id = ? AND category = ?
            ORDER BY program_name
        """,
            (exec_id, category),
        )
    else:
        c.execute(
            """
            SELECT * FROM executive_memberships
            WHERE exec_id = ?
            ORDER BY category, program_name
        """,
            (exec_id,),
        )
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def delete_membership(membership_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM executive_memberships WHERE id = ?", (membership_id,))
    conn.commit()
    conn.close()


def delete_all_memberships(exec_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM executive_memberships WHERE exec_id = ?", (exec_id,))
    conn.commit()
    conn.close()


# =========================================================
# CATEGORY MANAGEMENT
# =========================================================
def add_category(name):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO categories (name) VALUES (?)", (name,))
        conn.commit()
        new_id = c.lastrowid
        conn.close()
        return new_id
    except sqlite3.IntegrityError:
        conn.close()
        return None


def get_all_categories():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, name FROM categories ORDER BY name")
    rows = c.fetchall()
    conn.close()
    return rows


def delete_category(category_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM categories WHERE id = ?", (category_id,))
    conn.commit()
    conn.close()


# =========================================================
# TRIP MANAGEMENT
# =========================================================
def create_or_get_trip(
    exec_id,
    destination_summary,
    start_date,
    end_date,
    purpose,
    display_currency="USD",
    base_currency="USD",
):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        SELECT id FROM trips
        WHERE exec_id = ? AND destination = ? AND start_date = ? AND status = 'draft'
        ORDER BY created_at DESC LIMIT 1
    """,
        (exec_id, destination_summary, start_date),
    )
    row = c.fetchone()
    if row:
        trip_id = row[0]
    else:
        c.execute(
            """
            INSERT INTO trips (exec_id, destination, start_date, end_date, purpose, status,
                               display_currency, base_currency)
            VALUES (?, ?, ?, ?, ?, 'draft', ?, ?)
        """,
            (
                exec_id,
                destination_summary,
                start_date,
                end_date,
                purpose,
                display_currency,
                base_currency,
            ),
        )
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


def update_trip_departure_details(trip_id, city, region, country):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        UPDATE trips 
        SET departure_city = ?, departure_region = ?, departure_country = ? 
        WHERE id = ?
    """,
        (city, region, country, trip_id),
    )
    conn.commit()
    conn.close()


def update_trip_purpose(trip_id, purpose):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE trips SET purpose = ? WHERE id = ?", (purpose, trip_id))
    conn.commit()
    conn.close()


def update_trip_dates(trip_id, start_date, end_date, destination):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "UPDATE trips SET start_date = ?, end_date = ?, destination = ? WHERE id = ?",
        (start_date, end_date, destination, trip_id),
    )
    conn.commit()
    conn.close()


def update_trip_base_currency(trip_id, base_currency):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "UPDATE trips SET base_currency = ? WHERE id = ?", (base_currency, trip_id)
    )
    conn.commit()
    conn.close()


def update_trip_display_currency(trip_id, display_currency):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "UPDATE trips SET display_currency = ? WHERE id = ?",
        (display_currency, trip_id),
    )
    conn.commit()
    conn.close()


def update_trip_currencies(trip_id, base_currency, display_currency):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "UPDATE trips SET base_currency = ?, display_currency = ? WHERE id = ?",
        (base_currency, display_currency, trip_id),
    )
    conn.commit()
    conn.close()


def delete_trip(trip_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM trips WHERE id = ?", (trip_id,))
    conn.commit()
    conn.close()


def duplicate_trip(trip_id, exec_id):
    original = get_trip(trip_id)
    if not original:
        return None

    new_purpose = original["purpose"]
    if not new_purpose.endswith(" (Copy)"):
        new_purpose += " (Copy)"
    else:
        new_purpose += " (Copy)"

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO trips (exec_id, destination, start_date, end_date, purpose, status,
                           created_at, budget, departure_city, departure_region, departure_country,
                           base_currency, display_currency)
        VALUES (?, ?, ?, ?, ?, 'draft', CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?)
    """,
        (
            exec_id,
            original["destination"],
            original["start_date"],
            original["end_date"],
            new_purpose,
            original.get("budget", 0),
            original.get("departure_city", ""),
            original.get("departure_region", ""),
            original.get("departure_country", ""),
            original.get("base_currency", "USD"),
            original.get("display_currency", "USD"),
        ),
    )
    new_trip_id = c.lastrowid
    conn.commit()
    conn.close()

    stops = get_trip_stops(trip_id)
    for stop in stops:
        add_trip_stop(
            new_trip_id,
            stop["stop_order"],
            stop["city"],
            stop["country"],
            stop["region"],
            stop["start_date"],
            stop["end_date"],
            stop.get("notes", ""),
        )

    items = get_items_for_trip(trip_id)
    for item in items:
        add_itinerary_item(
            new_trip_id,
            item["item_type"],
            item["description"],
            item["datetime_start"],
            item["datetime_end"],
            item["location"],
            item["cost"],
            item["confirmation_code"],
            item["notes"],
            item.get("is_confirmed", 0),
            item.get("cost_currency", "USD"),
            item.get("exchange_rate_snapshot", 1.0),
        )

    return new_trip_id


# =========================================================
# TRIP STOPS
# =========================================================
def add_trip_stop(
    trip_id, stop_order, city, country, region, start_date, end_date, notes=None
):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO trip_stops (trip_id, stop_order, city, country, region, start_date, end_date, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (trip_id, stop_order, city, country, region, start_date, end_date, notes),
    )
    conn.commit()
    new_id = c.lastrowid
    conn.close()
    return new_id


def get_trip_stops(trip_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        """
        SELECT * FROM trip_stops
        WHERE trip_id = ?
        ORDER BY stop_order ASC
    """,
        (trip_id,),
    )
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def update_trip_stop(stop_id, city, country, region, start_date, end_date, notes):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        UPDATE trip_stops 
        SET city = ?, country = ?, region = ?, start_date = ?, end_date = ?, notes = ?
        WHERE id = ?
    """,
        (city, country, region, start_date, end_date, notes, stop_id),
    )
    conn.commit()
    conn.close()


def delete_trip_stop(stop_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM trip_stops WHERE id = ?", (stop_id,))
    conn.commit()
    conn.close()


def delete_all_trip_stops(trip_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM trip_stops WHERE trip_id = ?", (trip_id,))
    conn.commit()
    conn.close()


# =========================================================
# ITINERARY ITEMS
# =========================================================
def add_itinerary_item(
    trip_id,
    item_type,
    description,
    datetime_start,
    datetime_end,
    location,
    cost,
    confirmation_code,
    notes,
    is_confirmed=0,
    cost_currency="USD",
    exchange_rate_snapshot=1.0,
):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO itinerary_items 
        (trip_id, item_type, description, datetime_start, datetime_end, location,
         cost, confirmation_code, notes, is_confirmed, cost_currency, exchange_rate_snapshot)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            trip_id,
            item_type,
            description,
            datetime_start,
            datetime_end,
            location,
            cost,
            confirmation_code,
            notes,
            is_confirmed,
            cost_currency,
            exchange_rate_snapshot,
        ),
    )
    conn.commit()
    conn.close()


def get_items_for_trip(trip_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        """
        SELECT * FROM itinerary_items
        WHERE trip_id = ?
        ORDER BY datetime_start ASC
    """,
        (trip_id,),
    )
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def update_itinerary_item(
    item_id,
    item_type,
    description,
    datetime_start,
    datetime_end,
    location,
    cost,
    confirmation_code,
    notes,
    is_confirmed,
    cost_currency="USD",
    exchange_rate_snapshot=1.0,
):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        UPDATE itinerary_items SET
            item_type = ?,
            description = ?,
            datetime_start = ?,
            datetime_end = ?,
            location = ?,
            cost = ?,
            confirmation_code = ?,
            notes = ?,
            is_confirmed = ?,
            cost_currency = ?,
            exchange_rate_snapshot = ?
        WHERE id = ?
    """,
        (
            item_type,
            description,
            datetime_start,
            datetime_end,
            location,
            cost,
            confirmation_code,
            notes,
            is_confirmed,
            cost_currency,
            exchange_rate_snapshot,
            item_id,
        ),
    )
    conn.commit()
    conn.close()


def delete_itinerary_item(item_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM itinerary_items WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()


def update_receipt_path(item_id, file_path):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "UPDATE itinerary_items SET receipt_path = ? WHERE id = ?", (file_path, item_id)
    )
    conn.commit()
    conn.close()


# =========================================================
# BUDGET & SPENDING FUNCTIONS
# =========================================================
def get_trip_spending(trip_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT COALESCE(SUM(cost), 0) FROM itinerary_items WHERE trip_id = ?",
        (trip_id,),
    )
    total_all = c.fetchone()[0]

    c.execute(
        "SELECT COALESCE(SUM(cost), 0) FROM itinerary_items WHERE trip_id = ? AND is_confirmed = 1",
        (trip_id,),
    )
    total_confirmed = c.fetchone()[0]

    c.execute(
        "SELECT COALESCE(SUM(cost), 0) FROM itinerary_items WHERE trip_id = ? AND is_confirmed = 0",
        (trip_id,),
    )
    total_estimated = c.fetchone()[0]

    conn.close()
    return {
        "total_all": total_all,
        "total_confirmed": total_confirmed,
        "total_estimated": total_estimated,
    }


def get_spending_summary(exec_id=None, company_id=None, start_date=None, end_date=None):
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
            t.base_currency,
            t.display_currency,
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


# =========================================================
# EXECUTIVE DELETION FUNCTIONS
# =========================================================
def get_executive_trip_count(exec_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM trips WHERE exec_id = ?", (exec_id,))
    count = c.fetchone()[0]
    conn.close()
    return count


def delete_executive(exec_id, force=False):
    import os
    import shutil

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    trip_count = get_executive_trip_count(exec_id)

    if trip_count > 0 and not force:
        conn.close()
        return (
            False,
            f"Cannot delete: Executive has {trip_count} trip(s). Delete trips first or use force delete.",
        )

    if force:
        c.execute("SELECT id FROM trips WHERE exec_id = ?", (exec_id,))
        trip_ids = [row[0] for row in c.fetchall()]

        for trip_id in trip_ids:
            trip_folder = f"receipts/trip_{trip_id}"
            if os.path.exists(trip_folder):
                shutil.rmtree(trip_folder)

        c.execute(
            """
            DELETE FROM itinerary_items 
            WHERE trip_id IN (SELECT id FROM trips WHERE exec_id = ?)
        """,
            (exec_id,),
        )
        c.execute(
            """
            DELETE FROM trip_stops 
            WHERE trip_id IN (SELECT id FROM trips WHERE exec_id = ?)
        """,
            (exec_id,),
        )
        c.execute("DELETE FROM trips WHERE exec_id = ?", (exec_id,))

    c.execute("DELETE FROM executive_memberships WHERE exec_id = ?", (exec_id,))
    c.execute("DELETE FROM executives WHERE id = ?", (exec_id,))

    conn.commit()
    conn.close()

    return True, f"Executive and {trip_count} trip(s) deleted successfully."


# =========================================================
# IMPORT / MERGE FUNCTIONS
# =========================================================
def _find_or_create_company(name):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id FROM companies WHERE name = ?", (name,))
    row = c.fetchone()
    if row:
        company_id = row[0]
    else:
        c.execute("INSERT INTO companies (name) VALUES (?)", (name,))
        company_id = c.lastrowid
        conn.commit()
    conn.close()
    return company_id


def merge_database_data(data):
    import json

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    added_execs = 0
    added_trips = 0
    added_stops = 0
    added_items = 0

    for exec_data in data.get("executives", []):
        email = exec_data.get("email")
        if not email:
            continue
        c.execute("SELECT id FROM executives WHERE email = ?", (email,))
        if c.fetchone():
            continue

        company_name = exec_data.get("company_name")
        if company_name:
            company_id = _find_or_create_company(company_name)
        else:
            continue

        c.execute(
            """
            INSERT INTO executives 
            (company_id, name, email, timezone, seat_preference, hotel_loyalty,
             frequent_flyer_number, dietary_restrictions, passport_number,
             preferred_airline, tsa_precheck, meal_preference)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                company_id,
                exec_data.get("name"),
                email,
                exec_data.get("timezone", "America/New_York"),
                exec_data.get("seat_preference"),
                exec_data.get("hotel_loyalty"),
                exec_data.get("frequent_flyer_number"),
                exec_data.get("dietary_restrictions"),
                exec_data.get("passport_number"),
                exec_data.get("preferred_airline"),
                exec_data.get("tsa_precheck"),
                exec_data.get("meal_preference"),
            ),
        )
        added_execs += 1
        conn.commit()

    for trip_data in data.get("trips", []):
        exec_email = trip_data.get("executive_email")
        if not exec_email:
            continue
        c.execute("SELECT id FROM executives WHERE email = ?", (exec_email,))
        row = c.fetchone()
        if not row:
            continue
        exec_id = row[0]

        dest = trip_data.get("destination")
        start = trip_data.get("start_date")
        if not dest or not start:
            continue
        c.execute(
            "SELECT id FROM trips WHERE exec_id = ? AND destination = ? AND start_date = ?",
            (exec_id, dest, start),
        )
        if c.fetchone():
            continue

        c.execute(
            """
            INSERT INTO trips 
            (exec_id, destination, start_date, end_date, purpose, status,
             budget, departure_city, departure_region, departure_country,
             display_currency, base_currency)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                exec_id,
                dest,
                start,
                trip_data.get("end_date"),
                trip_data.get("purpose"),
                trip_data.get("status", "draft"),
                trip_data.get("budget", 0),
                trip_data.get("departure_city"),
                trip_data.get("departure_region"),
                trip_data.get("departure_country"),
                trip_data.get("display_currency", "USD"),
                trip_data.get("base_currency", "USD"),
            ),
        )
        trip_id = c.lastrowid
        added_trips += 1
        conn.commit()

        for stop in trip_data.get("stops", []):
            c.execute(
                """
                INSERT INTO trip_stops 
                (trip_id, stop_order, city, country, region, start_date, end_date, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    trip_id,
                    stop.get("stop_order", 0),
                    stop.get("city"),
                    stop.get("country"),
                    stop.get("region"),
                    stop.get("start_date"),
                    stop.get("end_date"),
                    stop.get("notes"),
                ),
            )
            added_stops += 1
            conn.commit()

        for item in trip_data.get("items", []):
            c.execute(
                """
                INSERT INTO itinerary_items 
                (trip_id, item_type, description, datetime_start, datetime_end,
                 location, cost, cost_currency, is_confirmed, confirmation_code, notes,
                 exchange_rate_snapshot)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    trip_id,
                    item.get("type"),
                    item.get("description"),
                    item.get("datetime_start"),
                    item.get("datetime_end"),
                    item.get("location"),
                    item.get("cost", 0),
                    item.get("cost_currency", "USD"),
                    1 if item.get("is_confirmed") else 0,
                    item.get("confirmation_code"),
                    item.get("notes"),
                    1.0,
                ),
            )
            added_items += 1
            conn.commit()

    conn.close()
    return f"✅ Imported {added_execs} executives, {added_trips} trips, {added_stops} stops, {added_items} items."


def import_executives_from_csv(reader):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    added = 0
    skipped = 0

    for row in reader:
        email = row.get("email")
        if not email:
            continue
        c.execute("SELECT id FROM executives WHERE email = ?", (email,))
        if c.fetchone():
            skipped += 1
            continue

        company_name = row.get("company_name")
        if company_name:
            company_id = _find_or_create_company(company_name)
        else:
            continue

        c.execute(
            """
            INSERT INTO executives 
            (company_id, name, email, timezone, seat_preference, hotel_loyalty,
             frequent_flyer_number, dietary_restrictions, passport_number,
             preferred_airline, tsa_precheck, meal_preference)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                company_id,
                row.get("name"),
                email,
                row.get("timezone", "America/New_York"),
                row.get("seat_preference"),
                row.get("hotel_loyalty"),
                row.get("frequent_flyer_number"),
                row.get("dietary_restrictions"),
                row.get("passport_number"),
                row.get("preferred_airline"),
                row.get("tsa_precheck"),
                row.get("meal_preference"),
            ),
        )
        added += 1
        conn.commit()

    conn.close()
    return f"✅ Added {added} executives. Skipped {skipped} duplicates."


# =========================================================
# TRIP TEMPLATES
# =========================================================
def save_trip_as_template(trip_id, template_name, description=None):
    """
    Save an existing trip's structure as a template.
    Returns the new template ID.
    """
    import json
    from datetime import datetime

    trip = get_trip(trip_id)
    if not trip:
        return None

    stops = get_trip_stops(trip_id)
    items = get_items_for_trip(trip_id)

    stops_data = []
    for stop in stops:
        stops_data.append(
            {
                "city": stop.get("city", ""),
                "country": stop.get("country", ""),
                "region": stop.get("region", ""),
                "notes": stop.get("notes", ""),
            }
        )

    items_data = []
    for item in items:
        items_data.append(
            {
                "item_type": item.get("item_type", ""),
                "description": item.get("description", ""),
                "location": item.get("location", ""),
                "cost_currency": item.get("cost_currency", "USD"),
                "is_confirmed": item.get("is_confirmed", 0),
                "confirmation_code": item.get("confirmation_code", ""),
                "notes": item.get("notes", ""),
            }
        )

    stops_json = json.dumps(stops_data, indent=2)
    items_json = json.dumps(items_data, indent=2)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO trip_templates 
        (name, description, departure_city, departure_region, departure_country,
         display_currency, base_currency, stops_json, items_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            template_name,
            description,
            trip.get("departure_city", ""),
            trip.get("departure_region", ""),
            trip.get("departure_country", ""),
            trip.get("display_currency", "USD"),
            trip.get("base_currency", "USD"),
            stops_json,
            items_json,
        ),
    )
    new_id = c.lastrowid
    conn.commit()
    conn.close()
    return new_id


def get_trip_templates():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT id, name, description, created_at, departure_city, departure_region,
               departure_country, display_currency, base_currency
        FROM trip_templates
        ORDER BY name
    """)
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_trip_template(template_id):
    import json

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        """
        SELECT * FROM trip_templates
        WHERE id = ?
    """,
        (template_id,),
    )
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    template = dict(row)
    template["stops"] = json.loads(template.get("stops_json", "[]"))
    template["items"] = json.loads(template.get("items_json", "[]"))
    return template


def delete_trip_template(template_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM trip_templates WHERE id = ?", (template_id,))
    conn.commit()
    conn.close()
    return True


def apply_trip_template(
    template_id, exec_id, new_purpose, start_date, end_date, budget=0
):
    """Apply a template to create a new draft trip. Returns the new trip ID."""
    template = get_trip_template(template_id)
    if not template:
        return None

    stops = template.get("stops", [])
    stop_names = [s["city"] for s in stops if s.get("city")]
    dest_summary = " → ".join(stop_names) if stop_names else "Template Trip"

    trip_id = create_or_get_trip(
        exec_id,
        dest_summary,
        start_date.isoformat(),
        end_date.isoformat(),
        new_purpose,
        template.get("display_currency", "USD"),
        template.get("base_currency", "USD"),
    )

    # Update budget and departure
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE trips SET budget = ? WHERE id = ?", (budget, trip_id))
    conn.commit()
    conn.close()

    update_trip_departure_details(
        trip_id,
        template.get("departure_city", ""),
        template.get("departure_region", ""),
        template.get("departure_country", ""),
    )

    # Add stops
    stop_order = 0
    for stop in stops:
        stop_order += 1
        add_trip_stop(
            trip_id,
            stop_order,
            stop.get("city", ""),
            stop.get("country", ""),
            stop.get("region", ""),
            start_date.isoformat(),
            end_date.isoformat(),
            stop.get("notes", ""),
        )

    # Add items
    for item in template.get("items", []):
        add_itinerary_item(
            trip_id,
            item.get("item_type", ""),
            item.get("description", ""),
            start_date.isoformat() + "T08:00:00",
            start_date.isoformat() + "T09:00:00",
            item.get("location", ""),
            0,
            item.get("confirmation_code", ""),
            item.get("notes", ""),
            0,
            item.get("cost_currency", "USD"),
            1.0,
        )

    return trip_id
