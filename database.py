import sqlite3
import os
import json
from datetime import date, datetime


DB_PATH = "travel_planner.db"


# =========================================================
# MIGRATION
# =========================================================


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
    if "trip_contacts" not in existing_trips:
        c.execute("ALTER TABLE trips ADD COLUMN trip_contacts TEXT")  # JSON array

    # --- Columns for 'itinerary_items' table ---
    c.execute("PRAGMA table_info(itinerary_items)")
    existing_items = [row[1] for row in c.fetchall()]

    if "is_confirmed" not in existing_items:
        c.execute("ALTER TABLE itinerary_items ADD COLUMN is_confirmed INTEGER DEFAULT 0")
    if "receipt_path" not in existing_items:
        c.execute("ALTER TABLE itinerary_items ADD COLUMN receipt_path TEXT")
    if "cost_currency" not in existing_items:
        c.execute("ALTER TABLE itinerary_items ADD COLUMN cost_currency TEXT DEFAULT 'USD'")
    if "timezone" not in existing_items:
        c.execute("ALTER TABLE itinerary_items ADD COLUMN timezone TEXT")

    # --- Columns for 'executives' table ---
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

    # --- Columns for 'executive_memberships' ---
    c.execute("PRAGMA table_info(executive_memberships)")
    existing_membership_cols = [row[1] for row in c.fetchall()]
    new_membership_cols = [
        ("tier", "TEXT"),
        ("alliance", "TEXT"),
        ("airport_code", "TEXT"),
        ("notes", "TEXT"),
    ]
    for col_name, col_type in new_membership_cols:
        if col_name not in existing_membership_cols:
            c.execute(f"ALTER TABLE executive_memberships ADD COLUMN {col_name} {col_type}")

    # --- Create tables if they don't exist ---
    c.execute("""CREATE TABLE IF NOT EXISTS executive_passports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        exec_id INTEGER NOT NULL,
        country TEXT NOT NULL,
        passport_number TEXT NOT NULL,
        expiry_date TEXT,
        issued_date TEXT,
        notes TEXT,
        FOREIGN KEY (exec_id) REFERENCES executives(id) ON DELETE CASCADE
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS executive_memberships (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        exec_id INTEGER NOT NULL,
        category TEXT NOT NULL,
        program_name TEXT NOT NULL,
        membership_number TEXT NOT NULL,
        tier TEXT,
        alliance TEXT,
        airport_code TEXT,
        notes TEXT,
        FOREIGN KEY (exec_id) REFERENCES executives(id) ON DELETE CASCADE
    )""")

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

    c.execute("""CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL
    )""")

    c.execute("SELECT COUNT(*) FROM categories")
    if c.fetchone()[0] == 0:
        default_cats = [
            "Flight", "Hotel", "Meeting", "Transport",
            "Dinner", "Car Rental", "Conference", "Site Visit",
            "Transfer", "Tour", "Wellness", "Activity"
        ]
        for cat in default_cats:
            c.execute("INSERT INTO categories (name) VALUES (?)", (cat,))

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
        stops_json TEXT,
        items_json TEXT
    )""")

    # --- Contacts table (with type and city) ---
    c.execute("PRAGMA table_info(contacts)")
    existing_contact_cols = [row[1] for row in c.fetchall()]
    if "type" not in existing_contact_cols:
        c.execute("ALTER TABLE contacts ADD COLUMN type TEXT DEFAULT 'Local Support'")
    if "city" not in existing_contact_cols:
        c.execute("ALTER TABLE contacts ADD COLUMN city TEXT")

    # --- Delegation tables ---
    c.execute("DROP TABLE IF EXISTS company_participants")
    c.execute("""CREATE TABLE IF NOT EXISTS delegation_members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        email TEXT,
        role TEXT,
        phone TEXT,
        is_active INTEGER DEFAULT 1,
        FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
    )""")

    c.execute("DROP TABLE IF EXISTS item_participants")
    c.execute("""CREATE TABLE IF NOT EXISTS item_delegation (
        item_id INTEGER NOT NULL,
        member_id INTEGER NOT NULL,
        PRIMARY KEY (item_id, member_id),
        FOREIGN KEY (item_id) REFERENCES itinerary_items(id) ON DELETE CASCADE,
        FOREIGN KEY (member_id) REFERENCES delegation_members(id) ON DELETE CASCADE
    )""")

    # --- Item contacts (many-to-many: itinerary items ↔ contacts) ---
    c.execute("""CREATE TABLE IF NOT EXISTS item_contacts (
        item_id INTEGER NOT NULL,
        contact_id INTEGER NOT NULL,
        PRIMARY KEY (item_id, contact_id),
        FOREIGN KEY (item_id) REFERENCES itinerary_items(id) ON DELETE CASCADE,
        FOREIGN KEY (contact_id) REFERENCES contacts(id) ON DELETE CASCADE
    )""")

    # --- Indexes ---
    c.execute("CREATE INDEX IF NOT EXISTS idx_contacts_company ON contacts(company_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_contacts_country ON contacts(country)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_contacts_city ON contacts(city)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_delegation_company ON delegation_members(company_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_item_delegation_item ON item_delegation(item_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_item_contacts_item ON item_contacts(item_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_trip_contacts ON trips(trip_contacts)")

    # --- Add default_contact_ids to companies if missing ---
    c.execute("PRAGMA table_info(companies)")
    existing_company_cols = [row[1] for row in c.fetchall()]
    if "default_contact_ids" not in existing_company_cols:
        c.execute("ALTER TABLE companies ADD COLUMN default_contact_ids TEXT")

    # --- Allow NULL company_id in contacts ---
    # Check if the column is currently NOT NULL
    c.execute("PRAGMA table_info(contacts)")
    columns = c.fetchall()
    for col in columns:
        if col[1] == 'company_id' and col[3] == 0:  # not null
            # Recreate table without NOT NULL constraint
            c.execute("PRAGMA foreign_keys=OFF")
            c.execute("CREATE TABLE contacts_new AS SELECT * FROM contacts")
            c.execute("DROP TABLE contacts")
            c.execute("""
                CREATE TABLE contacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company_id INTEGER,
                    name TEXT NOT NULL,
                    role TEXT,
                    phone TEXT,
                    email TEXT,
                    country TEXT,
                    city TEXT,
                    notes TEXT,
                    is_active INTEGER DEFAULT 1,
                    tags TEXT,
                    type TEXT DEFAULT 'Local Support',
                    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE SET NULL
                )
            """)
            c.execute("INSERT INTO contacts SELECT * FROM contacts_new")
            c.execute("DROP TABLE contacts_new")
            c.execute("PRAGMA foreign_keys=ON")
            break

            # =========================================================
    # VENUES – migrate from per-trip to master table
    # =========================================================
    c.execute("PRAGMA table_info(venues)")
    venue_cols = [row[1] for row in c.fetchall()]

    # Detect old schema (has trip_id) vs new schema (has is_active)
    if "trip_id" in venue_cols and "is_active" not in venue_cols:
        # ---- MIGRATION: old per-trip venues → master venues ----
        print("Migrating venues table to master schema...")

        # 1. Create new master venues table
        c.execute("""CREATE TABLE IF NOT EXISTS venues_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            address TEXT,
            city TEXT,
            country TEXT,
            wifi_ssid TEXT,
            wifi_password TEXT,
            badge_info TEXT,
            dress_code_notes TEXT,
            notes TEXT,
            is_active INTEGER DEFAULT 1
        )""")

        # 2. Copy old venues (deduplicate by name) and build a trip→venue_id map
        c.execute(
            "SELECT id, trip_id, name, address, wifi_ssid, wifi_password, badge_info, dress_code_notes, notes FROM venues"
        )
        old_venues = c.fetchall()
        trip_to_new_venue = {}  # trip_id → new venue id
        name_to_new_venue = {}  # name → new venue id (dedupe)

        for v in old_venues:
            (
                old_id,
                trip_id,
                name,
                address,
                wifi_ssid,
                wifi_password,
                badge_info,
                dress_code,
                notes,
            ) = v
            key = (name or "").strip().lower()
            if key and key in name_to_new_venue:
                # Reuse an existing master venue with same name
                trip_to_new_venue[trip_id] = name_to_new_venue[key]
                continue
            c.execute(
                """INSERT INTO venues_new
                         (name, address, wifi_ssid, wifi_password, badge_info, dress_code_notes, notes)
                         VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    name,
                    address,
                    wifi_ssid,
                    wifi_password,
                    badge_info,
                    dress_code,
                    notes,
                ),
            )
            new_id = c.lastrowid
            trip_to_new_venue[trip_id] = new_id
            if key:
                name_to_new_venue[key] = new_id

        # 3. Drop old venues table, rename new one
        c.execute("DROP TABLE venues")
        c.execute("ALTER TABLE venues_new RENAME TO venues")

        # 4. Add venue_id column to itinerary_items if missing
        c.execute("PRAGMA table_info(itinerary_items)")
        item_cols = [row[1] for row in c.fetchall()]
        if "venue_id" not in item_cols:
            c.execute("ALTER TABLE itinerary_items ADD COLUMN venue_id INTEGER")

        # 5. Link existing session-type items to their trip's venue
        session_types = (
            "Meeting",
            "Conference",
            "Dinner",
            "Site Visit",
            "Tour",
            "Activity",
        )
        placeholders = ",".join(["?"] * len(session_types))
        for trip_id, new_venue_id in trip_to_new_venue.items():
            c.execute(
                f"""UPDATE itinerary_items
                          SET venue_id = ?
                          WHERE trip_id = ?
                            AND item_type IN ({placeholders})
                            AND venue_id IS NULL""",
                (new_venue_id, trip_id, *session_types),
            )

        print("Venues migration complete.")

    else:
        # ---- Fresh install or already migrated ----
        c.execute("""CREATE TABLE IF NOT EXISTS venues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            address TEXT,
            city TEXT,
            country TEXT,
            wifi_ssid TEXT,
            wifi_password TEXT,
            badge_info TEXT,
            dress_code_notes TEXT,
            notes TEXT,
            is_active INTEGER DEFAULT 1
        )""")

        # Ensure venue_id column exists on itinerary_items
        c.execute("PRAGMA table_info(itinerary_items)")
        item_cols = [row[1] for row in c.fetchall()]
        if "venue_id" not in item_cols:
            c.execute("ALTER TABLE itinerary_items ADD COLUMN venue_id INTEGER")

    # Index for performance
    c.execute("CREATE INDEX IF NOT EXISTS idx_venues_name ON venues(name)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_venues_country ON venues(country)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_items_venue ON itinerary_items(venue_id)")

    # =========================================================
    # CURRENCY OVERHAUL – Stage 1: exchange_rates + cost_date
    # =========================================================

    # --- Exchange rates table ---
    c.execute("""CREATE TABLE IF NOT EXISTS exchange_rates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rate_date TEXT NOT NULL,
        base_currency TEXT NOT NULL,
        target_currency TEXT NOT NULL,
        rate REAL NOT NULL,
        source TEXT,
        fetched_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(rate_date, base_currency, target_currency)
    )""")
    c.execute(
        "CREATE INDEX IF NOT EXISTS idx_rates_pair_date "
        "ON exchange_rates(base_currency, target_currency, rate_date)"
    )

    # --- Add cost_date to itinerary_items if missing ---
    c.execute("PRAGMA table_info(itinerary_items)")
    existing_items_now = [row[1] for row in c.fetchall()]
    if "cost_date" not in existing_items_now:
        c.execute("ALTER TABLE itinerary_items ADD COLUMN cost_date TEXT")
        # Backfill: default cost_date to the date part of datetime_start
        c.execute("""UPDATE itinerary_items
                     SET cost_date = SUBSTR(datetime_start, 1, 10)
                     WHERE cost_date IS NULL AND datetime_start IS NOT NULL""")

    # =========================================================
    # PHASE 2 – Reusable Content Infrastructure
    # =========================================================

    # --- Destination Guides (one per country) ---
    c.execute("""CREATE TABLE IF NOT EXISTS destination_guides (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        country TEXT NOT NULL,
        language TEXT,
        currency TEXT,
        emergency_police TEXT,
        emergency_ambulance TEXT,
        emergency_fire TEXT,
        etiquette_notes TEXT,
        phrases TEXT,
        packing_tips TEXT,
        connectivity_notes TEXT,
        recommended_apps TEXT,
        notes TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    c.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_dest_country ON destination_guides(country)"
    )

    # --- Visa Rules (one per passport+destination pair) ---
    c.execute("""CREATE TABLE IF NOT EXISTS visa_rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        passport_nationality TEXT NOT NULL,
        destination_country TEXT NOT NULL,
        visa_required INTEGER DEFAULT 1,
        max_stay_days INTEGER,
        processing_time TEXT,
        fee TEXT,
        notes TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    c.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_visa_pair ON visa_rules(passport_nationality, destination_country)"
    )

    # --- Checklist Templates ---
    c.execute("""CREATE TABLE IF NOT EXISTS checklist_templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        items_json TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")

    # --- Packing Templates ---
    c.execute("""CREATE TABLE IF NOT EXISTS packing_templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT,
        items_json TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")

def init_db():
    """Create all tables if they don't exist, then run migrations."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS companies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        default_cost_center TEXT,
        policy_notes TEXT,
        default_contact_ids TEXT
    )""")

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
        passport_number TEXT,
        preferred_airline TEXT,
        tsa_precheck TEXT,
        meal_preference TEXT,
        FOREIGN KEY (company_id) REFERENCES companies(id)
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS trips (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        exec_id INTEGER,
        destination TEXT NOT NULL,
        start_date TEXT,
        end_date TEXT,
        purpose TEXT,
        status TEXT DEFAULT 'draft',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        budget REAL DEFAULT 0,
        departure_city TEXT,
        departure_region TEXT,
        departure_country TEXT,
        base_currency TEXT DEFAULT 'USD',
        display_currency TEXT DEFAULT 'USD',
        trip_contacts TEXT,
        FOREIGN KEY (exec_id) REFERENCES executives(id)
    )""")

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
        is_confirmed INTEGER DEFAULT 0,
        receipt_path TEXT,
        cost_currency TEXT DEFAULT 'USD',
        timezone TEXT,
        FOREIGN KEY (trip_id) REFERENCES trips(id) ON DELETE CASCADE
    )""")

    # Create contacts table (will have type and city added via migration)
    c.execute("""CREATE TABLE IF NOT EXISTS contacts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        role TEXT,
        phone TEXT,
        email TEXT,
        country TEXT,
        city TEXT,
        notes TEXT,
        is_active INTEGER DEFAULT 1,
        tags TEXT,
        type TEXT DEFAULT 'Local Support',
        FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
    )""")

    conn.commit()
    conn.close()
    migrate_db()

    # =========================================================
    # PHASE 3 – Expenses & Per Diem
    # =========================================================

    # --- Per Diem (one per trip + member) ---
    c.execute("""CREATE TABLE IF NOT EXISTS per_diem (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trip_id INTEGER NOT NULL,
        member_id INTEGER NOT NULL,
        daily_rate REAL DEFAULT 0,
        days INTEGER DEFAULT 0,
        currency TEXT DEFAULT 'USD',
        notes TEXT,
        UNIQUE(trip_id, member_id),
        FOREIGN KEY (trip_id) REFERENCES trips(id) ON DELETE CASCADE,
        FOREIGN KEY (member_id) REFERENCES delegation_members(id) ON DELETE CASCADE
    )""")

    # --- Expenses ---
    c.execute("""CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trip_id INTEGER NOT NULL,
        member_id INTEGER,
        expense_date TEXT NOT NULL,
        category TEXT,
        description TEXT,
        amount REAL DEFAULT 0,
        currency TEXT DEFAULT 'USD',
        receipt_path TEXT,
        notes TEXT,
        is_reimbursable INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (trip_id) REFERENCES trips(id) ON DELETE CASCADE,
        FOREIGN KEY (member_id) REFERENCES delegation_members(id) ON DELETE SET NULL
    )""")

    c.execute("CREATE INDEX IF NOT EXISTS idx_per_diem_trip ON per_diem(trip_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_expenses_trip ON expenses(trip_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_expenses_member ON expenses(member_id)")

    # =========================================================
    # PHASE 4 – Packing Lists & Trip Checklists
    # =========================================================

    # --- Packing Lists (one per trip + member) ---
    c.execute("""CREATE TABLE IF NOT EXISTS packing_lists (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trip_id INTEGER NOT NULL,
        member_id INTEGER NOT NULL,
        template_id INTEGER,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(trip_id, member_id),
        FOREIGN KEY (trip_id) REFERENCES trips(id) ON DELETE CASCADE,
        FOREIGN KEY (member_id) REFERENCES delegation_members(id) ON DELETE CASCADE,
        FOREIGN KEY (template_id) REFERENCES packing_templates(id) ON DELETE SET NULL
    )""")

    # --- Packing Items ---
    c.execute("""CREATE TABLE IF NOT EXISTS packing_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        list_id INTEGER NOT NULL,
        category TEXT,
        item_name TEXT NOT NULL,
        packed INTEGER DEFAULT 0,
        sort_order INTEGER DEFAULT 0,
        FOREIGN KEY (list_id) REFERENCES packing_lists(id) ON DELETE CASCADE
    )""")

    # --- Trip Checklists (one per trip + template, or ad-hoc) ---
    c.execute("""CREATE TABLE IF NOT EXISTS trip_checklists (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trip_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        description TEXT,
        template_id INTEGER,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (trip_id) REFERENCES trips(id) ON DELETE CASCADE,
        FOREIGN KEY (template_id) REFERENCES checklist_templates(id) ON DELETE SET NULL
    )""")

    # --- Trip Checklist Items ---
    c.execute("""CREATE TABLE IF NOT EXISTS trip_checklist_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        checklist_id INTEGER NOT NULL,
        item_text TEXT NOT NULL,
        is_done INTEGER DEFAULT 0,
        sort_order INTEGER DEFAULT 0,
        FOREIGN KEY (checklist_id) REFERENCES trip_checklists(id) ON DELETE CASCADE
    )""")

    c.execute("CREATE INDEX IF NOT EXISTS idx_packing_lists_trip ON packing_lists(trip_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_packing_items_list ON packing_items(list_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_trip_checklists_trip ON trip_checklists(trip_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_trip_checklist_items ON trip_checklist_items(checklist_id)")

    # =========================================================
    # PHASE 5 – Hospitals (city-level emergency info)
    # =========================================================

    c.execute("""CREATE TABLE IF NOT EXISTS hospitals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        city TEXT NOT NULL,
        country TEXT,
        name TEXT NOT NULL,
        address TEXT,
        phone TEXT,
        maps_url TEXT,
        notes TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")

    c.execute("CREATE INDEX IF NOT EXISTS idx_hospitals_city ON hospitals(city)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_hospitals_country ON hospitals(country)")

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


def update_company(
    company_id,
    name,
    default_cost_center=None,
    policy_notes=None,
    default_contact_ids=None,
):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """UPDATE companies 
           SET name = ?, default_cost_center = ?, policy_notes = ?, default_contact_ids = ?
           WHERE id = ?""",
        (name, default_cost_center, policy_notes, default_contact_ids, company_id),
    )
    conn.commit()
    conn.close()


def delete_company(company_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM executives WHERE company_id = ?", (company_id,))
    count = c.fetchone()[0]
    if count > 0:
        conn.close()
        return (
            False,
            f"Cannot delete: {count} executive(s) are still assigned to this company.",
        )
    c.execute("DELETE FROM companies WHERE id = ?", (company_id,))
    conn.commit()
    conn.close()
    return True, "Company deleted successfully."


def get_executives_by_company(company_id):
    """Return all executives belonging to a company."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM executives WHERE company_id = ?", (company_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


# =========================================================
# CONTACTS (with type and city)
# =========================================================


def add_contact(
    company_id,
    name,
    role=None,
    phone=None,
    email=None,
    country=None,
    city=None,
    notes=None,
    tags=None,
    type="Local Support",
):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """INSERT INTO contacts (company_id, name, role, phone, email, country, city, notes, tags, type)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (company_id, name, role, phone, email, country, city, notes, tags, type),
    )
    conn.commit()
    new_id = c.lastrowid
    conn.close()
    return new_id


def get_contacts(company_id=None, active_only=True, country=None):
    """
    Get contacts, optionally filtered by company_id, active status, and country.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    conditions = []
    params = []
    if active_only:
        conditions.append("is_active = 1")
    if company_id is not None:
        conditions.append("company_id = ?")
        params.append(company_id)
    if country is not None:
        conditions.append("country = ?")
        params.append(country)
    query = "SELECT * FROM contacts"
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY company_id, name"
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_contact(contact_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM contacts WHERE id = ?", (contact_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def update_contact(
    contact_id,
    name=None,
    role=None,
    phone=None,
    email=None,
    country=None,
    city=None,
    notes=None,
    tags=None,
    is_active=None,
    type=None,
):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    fields = []
    params = []
    if name is not None:
        fields.append("name = ?")
        params.append(name)
    if role is not None:
        fields.append("role = ?")
        params.append(role)
    if phone is not None:
        fields.append("phone = ?")
        params.append(phone)
    if email is not None:
        fields.append("email = ?")
        params.append(email)
    if country is not None:
        fields.append("country = ?")
        params.append(country)
    if city is not None:
        fields.append("city = ?")
        params.append(city)
    if notes is not None:
        fields.append("notes = ?")
        params.append(notes)
    if tags is not None:
        fields.append("tags = ?")
        params.append(tags)
    if is_active is not None:
        fields.append("is_active = ?")
        params.append(1 if is_active else 0)
    if type is not None:
        fields.append("type = ?")
        params.append(type)
    params.append(contact_id)
    if fields:
        sql = f"UPDATE contacts SET {', '.join(fields)} WHERE id = ?"
        c.execute(sql, params)
        conn.commit()
    conn.close()


def delete_contact(contact_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
    conn.commit()
    conn.close()


def find_duplicate_contacts(company_id, name=None, email=None, phone=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    query = "SELECT * FROM contacts WHERE company_id = ? AND is_active = 1 AND ("
    conditions = []
    params = [company_id]
    if name:
        conditions.append("name = ?")
        params.append(name)
    if email:
        conditions.append("email = ?")
        params.append(email)
    if phone:
        conditions.append("phone = ?")
        params.append(phone)
    if not conditions:
        conn.close()
        return []
    query += " OR ".join(conditions) + ")"
    conn.row_factory = sqlite3.Row
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


# =========================================================
# DELEGATION MEMBERS
# =========================================================


def add_delegation_member(company_id, name, email=None, role=None, phone=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """INSERT INTO delegation_members (company_id, name, email, role, phone)
           VALUES (?, ?, ?, ?, ?)""",
        (company_id, name, email, role, phone),
    )
    conn.commit()
    new_id = c.lastrowid
    conn.close()
    return new_id


def get_delegation_members(company_id=None, active_only=True):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    if company_id is not None:
        if active_only:
            c.execute(
                "SELECT * FROM delegation_members WHERE company_id = ? AND is_active = 1 ORDER BY name",
                (company_id,),
            )
        else:
            c.execute(
                "SELECT * FROM delegation_members WHERE company_id = ? ORDER BY name",
                (company_id,),
            )
    else:
        if active_only:
            c.execute(
                "SELECT * FROM delegation_members WHERE is_active = 1 ORDER BY company_id, name"
            )
        else:
            c.execute("SELECT * FROM delegation_members ORDER BY company_id, name")
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_delegation_member(member_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM delegation_members WHERE id = ?", (member_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def update_delegation_member(
    member_id, name=None, email=None, role=None, phone=None, is_active=None
):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    fields = []
    params = []
    if name is not None:
        fields.append("name = ?")
        params.append(name)
    if email is not None:
        fields.append("email = ?")
        params.append(email)
    if role is not None:
        fields.append("role = ?")
        params.append(role)
    if phone is not None:
        fields.append("phone = ?")
        params.append(phone)
    if is_active is not None:
        fields.append("is_active = ?")
        params.append(1 if is_active else 0)
    params.append(member_id)
    if fields:
        sql = f"UPDATE delegation_members SET {', '.join(fields)} WHERE id = ?"
        c.execute(sql, params)
        conn.commit()
    conn.close()


def delete_delegation_member(member_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM delegation_members WHERE id = ?", (member_id,))
    conn.commit()
    conn.close()


def find_duplicate_delegation_members(company_id, name=None, email=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    query = (
        "SELECT * FROM delegation_members WHERE company_id = ? AND is_active = 1 AND ("
    )
    conditions = []
    params = [company_id]
    if name:
        conditions.append("name = ?")
        params.append(name)
    if email:
        conditions.append("email = ?")
        params.append(email)
    if not conditions:
        conn.close()
        return []
    query += " OR ".join(conditions) + ")"
    conn.row_factory = sqlite3.Row
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


# =========================================================
# ITEM DELEGATION
# =========================================================


def add_item_delegation_member(item_id, member_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO item_delegation (item_id, member_id) VALUES (?, ?)",
        (item_id, member_id),
    )
    conn.commit()
    conn.close()


def remove_item_delegation_member(item_id, member_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "DELETE FROM item_delegation WHERE item_id = ? AND member_id = ?",
        (item_id, member_id),
    )
    conn.commit()
    conn.close()


def get_item_delegation_members(item_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        """
        SELECT m.* FROM delegation_members m
        JOIN item_delegation id ON m.id = id.member_id
        WHERE id.item_id = ?
        ORDER BY m.name
        """,
        (item_id,),
    )
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def set_item_delegation_members(item_id, member_ids):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM item_delegation WHERE item_id = ?", (item_id,))
    for mid in member_ids:
        c.execute(
            "INSERT OR IGNORE INTO item_delegation (item_id, member_id) VALUES (?, ?)",
            (item_id, mid),
        )
    conn.commit()
    conn.close()


# =========================================================
# ITEM CONTACTS
# =========================================================


def add_item_contact(item_id, contact_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO item_contacts (item_id, contact_id) VALUES (?, ?)",
        (item_id, contact_id),
    )
    conn.commit()
    conn.close()


def remove_item_contact(item_id, contact_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "DELETE FROM item_contacts WHERE item_id = ? AND contact_id = ?",
        (item_id, contact_id),
    )
    conn.commit()
    conn.close()


def get_item_contacts(item_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        """
        SELECT c.* FROM contacts c
        JOIN item_contacts ic ON c.id = ic.contact_id
        WHERE ic.item_id = ?
        ORDER BY c.name
        """,
        (item_id,),
    )
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def set_item_contacts(item_id, contact_ids):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM item_contacts WHERE item_id = ?", (item_id,))
    for cid in contact_ids:
        c.execute(
            "INSERT OR IGNORE INTO item_contacts (item_id, contact_id) VALUES (?, ?)",
            (item_id, cid),
        )
    conn.commit()
    conn.close()


# =========================================================
# TRIP CONTACTS
# =========================================================


def get_trip_contacts(trip_id):
    trip = get_trip(trip_id)
    if not trip or not trip.get("trip_contacts"):
        return []
    try:
        contact_ids = json.loads(trip["trip_contacts"])
    except:
        return []
    if not contact_ids:
        return []
    placeholders = ",".join(["?"] * len(contact_ids))
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        f"SELECT * FROM contacts WHERE id IN ({placeholders}) AND is_active = 1",
        contact_ids,
    )
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def update_trip_contacts(trip_id, contact_ids):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "UPDATE trips SET trip_contacts = ? WHERE id = ?",
        (json.dumps(contact_ids), trip_id),
    )
    conn.commit()
    conn.close()


def get_company_default_contacts(company_id):
    comp = get_company(company_id)
    if not comp or not comp.get("default_contact_ids"):
        return []
    try:
        return json.loads(comp["default_contact_ids"])
    except:
        return []


def set_company_default_contacts(company_id, contact_ids):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "UPDATE companies SET default_contact_ids = ? WHERE id = ?",
        (json.dumps(contact_ids), company_id),
    )
    conn.commit()
    conn.close()


# =========================================================
# EXECUTIVE MANAGEMENT (Existing)
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


def get_all_executive_profiles():
    all_execs = get_all_executives()
    profiles = []
    for e_id, name, company in all_execs:
        profile = get_full_executive_profile(e_id)
        if profile:
            mems = get_memberships(e_id)
            mem_str = "; ".join(
                [f"{m['program_name']}: {m['membership_number']}" for m in mems]
            )
            profile["Memberships"] = mem_str
            profile["ID"] = e_id
            profiles.append(profile)
    return profiles


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
# EXECUTIVE PASSPORTS
# =========================================================


def add_passport(
    exec_id, country, passport_number, expiry_date=None, issued_date=None, notes=None
):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """INSERT INTO executive_passports 
           (exec_id, country, passport_number, expiry_date, issued_date, notes)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (exec_id, country, passport_number, expiry_date, issued_date, notes),
    )
    conn.commit()
    new_id = c.lastrowid
    conn.close()
    return new_id


def get_passports(exec_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        "SELECT * FROM executive_passports WHERE exec_id = ? ORDER BY country",
        (exec_id,),
    )
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def delete_passport(passport_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM executive_passports WHERE id = ?", (passport_id,))
    conn.commit()
    conn.close()


def update_passport(
    passport_id,
    country,
    passport_number,
    expiry_date=None,
    issued_date=None,
    notes=None,
):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """UPDATE executive_passports 
           SET country = ?, passport_number = ?, expiry_date = ?, issued_date = ?, notes = ?
           WHERE id = ?""",
        (country, passport_number, expiry_date, issued_date, notes, passport_id),
    )
    conn.commit()
    conn.close()


# =========================================================
# EXECUTIVE MEMBERSHIPS
# =========================================================


def add_membership(
    exec_id,
    category,
    program_name,
    membership_number,
    tier=None,
    alliance=None,
    airport_code=None,
    notes=None,
):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """INSERT INTO executive_memberships 
           (exec_id, category, program_name, membership_number, tier, alliance, airport_code, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            exec_id,
            category,
            program_name,
            membership_number,
            tier,
            alliance,
            airport_code,
            notes,
        ),
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


def update_membership(
    membership_id,
    category,
    program_name,
    membership_number,
    tier=None,
    alliance=None,
    airport_code=None,
    notes=None,
):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """UPDATE executive_memberships 
           SET category = ?, program_name = ?, membership_number = ?, 
               tier = ?, alliance = ?, airport_code = ?, notes = ?
           WHERE id = ?""",
        (
            category,
            program_name,
            membership_number,
            tier,
            alliance,
            airport_code,
            notes,
            membership_id,
        ),
    )
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
# TRIP MANAGEMENT (Updated for trip_contacts and timezone)
# =========================================================


def create_or_get_trip(
    exec_id,
    destination_summary,
    start_date,
    end_date,
    purpose,
    display_currency="USD",
    base_currency="USD",
    status="draft",
    trip_contacts=None,
):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        SELECT id FROM trips
        WHERE exec_id = ? AND destination = ? AND start_date = ? AND status = ?
        ORDER BY created_at DESC LIMIT 1
    """,
        (exec_id, destination_summary, start_date, status),
    )
    row = c.fetchone()
    if row:
        trip_id = row[0]
    else:
        contacts_json = json.dumps(trip_contacts) if trip_contacts else None
        c.execute(
            """
            INSERT INTO trips (exec_id, destination, start_date, end_date, purpose, status,
                               display_currency, base_currency, trip_contacts)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                exec_id,
                destination_summary,
                start_date,
                end_date,
                purpose,
                status,
                display_currency,
                base_currency,
                contacts_json,
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


def delete_trips(trip_ids):
    if not trip_ids:
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    placeholders = ",".join("?" * len(trip_ids))
    c.execute(f"DELETE FROM trips WHERE id IN ({placeholders})", trip_ids)
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
                           base_currency, display_currency, trip_contacts)
        VALUES (?, ?, ?, ?, ?, 'draft', CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?, ?)
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
            original.get("trip_contacts"),
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
            item.get("timezone"),
            item.get("venue_id"),
            item.get("cost_date"),
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
# ITINERARY ITEMS (Updated for timezone)
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
    timezone=None,
    venue_id=None,
    cost_date=None,
):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO itinerary_items 
        (trip_id, item_type, description, datetime_start, datetime_end, location,
         cost, confirmation_code, notes, is_confirmed, cost_currency, timezone, venue_id, cost_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            timezone,
            venue_id,
            cost_date,
        ),
    )
    conn.commit()
    new_id = c.lastrowid
    conn.close()
    return new_id

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
    timezone=None,
    venue_id=None,
    cost_date=None,
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
            timezone = ?,
            venue_id = ?,
            cost_date = ?
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
            timezone,
            venue_id,
            cost_date,
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


# =========================================================
# BUDGET & SPENDING FUNCTIONS
# =========================================================


def get_spending_summary(exec_id=None, company_id=None, start_date=None, end_date=None):
    """
    Return spending summary per trip.

    Costs are converted to each trip's base currency using the exchange-rate
    table (via currency.convert_amount) and the item's `cost_date` for
    historical accuracy.

    Falls back to the legacy `exchange_rate_snapshot` if conversion fails,
    so the app never crashes on a missing rate.
    """
    # Local import to avoid a circular import at module load time.
    import currency  # noqa: WPS433 (imported here on purpose)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # ---- 1. Get trips matching the filters ----
    trip_query = """
        SELECT
            t.*,
            e.name AS executive_name,
            c.name AS company_name
        FROM trips t
        JOIN executives e ON t.exec_id = e.id
        JOIN companies c ON e.company_id = c.id
        WHERE 1=1
    """
    params = []

    if exec_id:
        trip_query += " AND e.id = ?"
        params.append(exec_id)
    if company_id:
        trip_query += " AND c.id = ?"
        params.append(company_id)
    if start_date:
        trip_query += " AND t.start_date >= ?"
        params.append(start_date)
    if end_date:
        trip_query += " AND t.end_date <= ?"
        params.append(end_date)

    trip_query += " ORDER BY t.start_date DESC"

    c.execute(trip_query, params)
    trips = c.fetchall()

    # ---- 2. For each trip, convert item costs to its base currency ----
    summary = []
    for trip in trips:
        trip_id = trip["id"]
        base_cur = (trip["base_currency"] or "USD").upper()

        c.execute(
            "SELECT * FROM itinerary_items WHERE trip_id = ?",
            (trip_id,),
        )
        items = c.fetchall()

        total = 0.0
        confirmed = 0.0
        estimated = 0.0

        for item in items:
            cost = item["cost"] or 0
            cost_cur = (item["cost_currency"] or "USD").upper()

            # Determine the date used for historical conversion.
            on_date = item["cost_date"]
            if not on_date and item["datetime_start"]:
                on_date = item["datetime_start"][:10]  # "YYYY-MM-DD"

            # Try the new conversion pipeline first.
            try:
                converted = currency.convert_amount(
                    cost, cost_cur, base_cur, on_date
                )
            except Exception:
                # No rate available anywhere — fall back to treating the
                # amount as already being in the trip's base currency so
                # the dashboard never crashes on missing data.
                converted = float(cost)

            total += converted
            if item["is_confirmed"]:
                confirmed += converted
            else:
                estimated += converted

        summary.append(
            {
                "trip_id": trip_id,
                "executive_name": trip["executive_name"],
                "company_name": trip["company_name"],
                "destination": trip["destination"],
                "start_date": trip["start_date"],
                "end_date": trip["end_date"],
                "budget": trip["budget"] or 0,
                "status": trip["status"],
                "base_currency": base_cur,
                "display_currency": trip["display_currency"],
                "total_spent": total,
                "confirmed_spent": confirmed,
                "estimated_spent": estimated,
            }
        )

    conn.close()
    return summary


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
    c.execute("DELETE FROM executive_passports WHERE exec_id = ?", (exec_id,))
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
             display_currency, base_currency, trip_contacts)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                None,  # trip_contacts not imported from JSON
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
                 timezone, cost_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    None,
                    item.get("cost_date")
                    or (
                        item.get("datetime_start", "")[:10]
                        if item.get("datetime_start")
                        else None
                    ),
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
    import json

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

# =========================================================
# DATABASE EXPORT
# =========================================================


def get_all_rows(table_name):
    """Return all rows from a given table as a list of dicts."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(f"SELECT * FROM {table_name}")
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def export_all_data():
    """Export all tables as a dict of table_name -> list of rows."""
    tables = [
        "companies",
        "executives",
        "contacts",
        "delegation_members",
        "trips",
        "itinerary_items",
        "trip_stops",
        "trip_templates",
        "categories",
        "executive_memberships",
        "executive_passports",
        "item_delegation",
        "item_contacts",
        "packing_lists",
        "packing_items",
        "trip_checklists",
        "trip_checklist_items",
        "hospitals",
        "exchange_rates",
    ]
    data = {}
    for table in tables:
        data[table] = get_all_rows(table)
    return data


def apply_trip_template(
    template_id, exec_id, new_purpose, start_date, end_date, budget=0
):
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
                None,           # timezone
                None,           # venue_id
                start_date.isoformat(),  # cost_date
            )



    return trip_id


# =========================================================
# VENUES (Master Table)
# =========================================================


def add_venue(
    name,
    address=None,
    city=None,
    country=None,
    wifi_ssid=None,
    wifi_password=None,
    badge_info=None,
    dress_code_notes=None,
    notes=None,
):
    """Create a new reusable venue."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """INSERT INTO venues
                 (name, address, city, country, wifi_ssid, wifi_password,
                  badge_info, dress_code_notes, notes)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            name,
            address,
            city,
            country,
            wifi_ssid,
            wifi_password,
            badge_info,
            dress_code_notes,
            notes,
        ),
    )
    conn.commit()
    new_id = c.lastrowid
    conn.close()
    return new_id


def get_venues(country=None, active_only=True):
    """Return all venues, optionally filtered by country."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    conditions = []
    params = []
    if active_only:
        conditions.append("is_active = 1")
    if country:
        conditions.append("country = ?")
        params.append(country)
    query = "SELECT * FROM venues"
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY name"
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_venue(venue_id):
    """Return a single venue by ID."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM venues WHERE id = ?", (venue_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def update_venue(
    venue_id,
    name=None,
    address=None,
    city=None,
    country=None,
    wifi_ssid=None,
    wifi_password=None,
    badge_info=None,
    dress_code_notes=None,
    notes=None,
    is_active=None,
):
    """Update an existing venue."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    fields = []
    params = []
    for col, val in [
        ("name", name),
        ("address", address),
        ("city", city),
        ("country", country),
        ("wifi_ssid", wifi_ssid),
        ("wifi_password", wifi_password),
        ("badge_info", badge_info),
        ("dress_code_notes", dress_code_notes),
        ("notes", notes),
    ]:
        if val is not None:
            fields.append(f"{col} = ?")
            params.append(val)
    if is_active is not None:
        fields.append("is_active = ?")
        params.append(1 if is_active else 0)
    if not fields:
        conn.close()
        return
    params.append(venue_id)
    sql = f"UPDATE venues SET {', '.join(fields)} WHERE id = ?"
    c.execute(sql, params)
    conn.commit()
    conn.close()


def delete_venue(venue_id):
    """Delete a venue (also clears references in itinerary_items)."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "UPDATE itinerary_items SET venue_id = NULL WHERE venue_id = ?", (venue_id,)
    )
    c.execute("DELETE FROM venues WHERE id = ?", (venue_id,))
    conn.commit()
    conn.close()


def get_venues_for_trip(trip_id):
    """Return the unique venues referenced by items on a given trip."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        """SELECT DISTINCT v.*
                 FROM venues v
                 JOIN itinerary_items i ON i.venue_id = v.id
                 WHERE i.trip_id = ? AND v.is_active = 1
                 ORDER BY v.name""",
        (trip_id,),
    )
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def find_duplicate_venues(name=None, address=None):
    """Check for existing venue with the same name or address."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    conditions = []
    params = []
    if name:
        conditions.append("name = ?")
        params.append(name)
    if address:
        conditions.append("address = ?")
        params.append(address)
    if not conditions:
        conn.close()
        return []
    query = f"SELECT * FROM venues WHERE is_active = 1 AND ({' OR '.join(conditions)})"
    conn.row_factory = sqlite3.Row
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


# =========================================================
# DESTINATION GUIDES
# =========================================================


def add_destination_guide(
    country,
    language=None,
    currency=None,
    emergency_police=None,
    emergency_ambulance=None,
    emergency_fire=None,
    etiquette_notes=None,
    phrases=None,
    packing_tips=None,
    connectivity_notes=None,
    recommended_apps=None,
    notes=None,
):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """INSERT INTO destination_guides
                 (country, language, currency, emergency_police, emergency_ambulance,
                  emergency_fire, etiquette_notes, phrases, packing_tips,
                  connectivity_notes, recommended_apps, notes)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            country,
            language,
            currency,
            emergency_police,
            emergency_ambulance,
            emergency_fire,
            etiquette_notes,
            phrases,
            packing_tips,
            connectivity_notes,
            recommended_apps,
            notes,
        ),
    )
    conn.commit()
    new_id = c.lastrowid
    conn.close()
    return new_id


def get_destination_guides(active_only=True):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    q = "SELECT * FROM destination_guides"
    if active_only:
        q += " WHERE is_active = 1"
    q += " ORDER BY country"
    c.execute(q)
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_destination_guide(guide_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM destination_guides WHERE id = ?", (guide_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def get_destination_guide_by_country(country):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        "SELECT * FROM destination_guides WHERE country = ? AND is_active = 1",
        (country,),
    )
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def update_destination_guide(guide_id, **kwargs):
    if not kwargs:
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    fields = []
    params = []
    for k, v in kwargs.items():
        fields.append(f"{k} = ?")
        params.append(v)
    params.append(guide_id)
    c.execute(f"UPDATE destination_guides SET {', '.join(fields)} WHERE id = ?", params)
    conn.commit()
    conn.close()


def delete_destination_guide(guide_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM destination_guides WHERE id = ?", (guide_id,))
    conn.commit()
    conn.close()


# =========================================================
# VISA RULES
# =========================================================


def add_visa_rule(
    passport_nationality,
    destination_country,
    visa_required=1,
    max_stay_days=None,
    processing_time=None,
    fee=None,
    notes=None,
):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """INSERT INTO visa_rules
                 (passport_nationality, destination_country, visa_required,
                  max_stay_days, processing_time, fee, notes)
                 VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            passport_nationality,
            destination_country,
            visa_required,
            max_stay_days,
            processing_time,
            fee,
            notes,
        ),
    )
    conn.commit()
    new_id = c.lastrowid
    conn.close()
    return new_id


def get_visa_rules(active_only=True):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    q = "SELECT * FROM visa_rules"
    if active_only:
        q += " WHERE is_active = 1"
    q += " ORDER BY passport_nationality, destination_country"
    c.execute(q)
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_visa_rule(rule_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM visa_rules WHERE id = ?", (rule_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def get_visa_rule_for_pair(passport_nationality, destination_country):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        """SELECT * FROM visa_rules
                 WHERE passport_nationality = ? AND destination_country = ? AND is_active = 1""",
        (passport_nationality, destination_country),
    )
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def update_visa_rule(rule_id, **kwargs):
    if not kwargs:
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    fields = []
    params = []
    for k, v in kwargs.items():
        fields.append(f"{k} = ?")
        params.append(v)
    params.append(rule_id)
    c.execute(f"UPDATE visa_rules SET {', '.join(fields)} WHERE id = ?", params)
    conn.commit()
    conn.close()


def delete_visa_rule(rule_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM visa_rules WHERE id = ?", (rule_id,))
    conn.commit()
    conn.close()


# =========================================================
# CHECKLIST TEMPLATES
# =========================================================


def add_checklist_template(name, description=None, items_json="[]"):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """INSERT INTO checklist_templates (name, description, items_json)
                 VALUES (?, ?, ?)""",
        (name, description, items_json),
    )
    conn.commit()
    new_id = c.lastrowid
    conn.close()
    return new_id


def get_checklist_templates(active_only=True):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    q = "SELECT * FROM checklist_templates"
    if active_only:
        q += " WHERE is_active = 1"
    q += " ORDER BY name"
    c.execute(q)
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_checklist_template(template_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM checklist_templates WHERE id = ?", (template_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def update_checklist_template(template_id, **kwargs):
    if not kwargs:
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    fields = []
    params = []
    for k, v in kwargs.items():
        fields.append(f"{k} = ?")
        params.append(v)
    params.append(template_id)
    c.execute(
        f"UPDATE checklist_templates SET {', '.join(fields)} WHERE id = ?", params
    )
    conn.commit()
    conn.close()


def delete_checklist_template(template_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM checklist_templates WHERE id = ?", (template_id,))
    conn.commit()
    conn.close()


# =========================================================
# PACKING TEMPLATES
# =========================================================


def add_packing_template(name, category=None, items_json="[]"):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """INSERT INTO packing_templates (name, category, items_json)
                 VALUES (?, ?, ?)""",
        (name, category, items_json),
    )
    conn.commit()
    new_id = c.lastrowid
    conn.close()
    return new_id


def get_packing_templates(active_only=True):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    q = "SELECT * FROM packing_templates"
    if active_only:
        q += " WHERE is_active = 1"
    q += " ORDER BY name"
    c.execute(q)
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_packing_template(template_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM packing_templates WHERE id = ?", (template_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def update_packing_template(template_id, **kwargs):
    if not kwargs:
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    fields = []
    params = []
    for k, v in kwargs.items():
        fields.append(f"{k} = ?")
        params.append(v)
    params.append(template_id)
    c.execute(f"UPDATE packing_templates SET {', '.join(fields)} WHERE id = ?", params)
    conn.commit()
    conn.close()


def delete_packing_template(template_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM packing_templates WHERE id = ?", (template_id,))
    conn.commit()
    conn.close()

# =========================================================
# PER DIEM
# =========================================================

def set_per_diem(trip_id, member_id, daily_rate, days, currency="USD", notes=None):
    """Upsert per-diem settings for a trip member."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id FROM per_diem WHERE trip_id = ? AND member_id = ?",
              (trip_id, member_id))
    row = c.fetchone()
    if row:
        c.execute("""UPDATE per_diem
                     SET daily_rate = ?, days = ?, currency = ?, notes = ?
                     WHERE id = ?""",
                  (daily_rate, days, currency, notes, row[0]))
    else:
        c.execute("""INSERT INTO per_diem
                     (trip_id, member_id, daily_rate, days, currency, notes)
                     VALUES (?, ?, ?, ?, ?, ?)""",
                  (trip_id, member_id, daily_rate, days, currency, notes))
    conn.commit()
    conn.close()


def get_per_diem(trip_id, member_id=None):
    """Get per-diem rows for a trip (optionally a specific member)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    if member_id:
        c.execute("SELECT * FROM per_diem WHERE trip_id = ? AND member_id = ?",
                  (trip_id, member_id))
        row = c.fetchone()
        conn.close()
        return dict(row) if row else None
    c.execute("SELECT * FROM per_diem WHERE trip_id = ? ORDER BY member_id",
              (trip_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def delete_per_diem(per_diem_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM per_diem WHERE id = ?", (per_diem_id,))
    conn.commit()
    conn.close()


# =========================================================
# EXPENSES
# =========================================================

def add_expense(trip_id, member_id, expense_date, category=None,
                description=None, amount=0, currency="USD",
                receipt_path=None, notes=None, is_reimbursable=1):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""INSERT INTO expenses
                 (trip_id, member_id, expense_date, category, description,
                  amount, currency, receipt_path, notes, is_reimbursable)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
              (trip_id, member_id, expense_date, category, description,
               amount, currency, receipt_path, notes, is_reimbursable))
    conn.commit()
    new_id = c.lastrowid
    conn.close()
    return new_id


def get_expenses(trip_id, member_id=None):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    if member_id:
        c.execute("""SELECT * FROM expenses
                     WHERE trip_id = ? AND member_id = ?
                     ORDER BY expense_date DESC, id DESC""",
                  (trip_id, member_id))
    else:
        c.execute("""SELECT * FROM expenses
                     WHERE trip_id = ?
                     ORDER BY expense_date DESC, id DESC""",
                  (trip_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_expense(expense_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def update_expense(expense_id, **kwargs):
    if not kwargs:
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    fields = []
    params = []
    for k, v in kwargs.items():
        fields.append(f"{k} = ?")
        params.append(v)
    params.append(expense_id)
    c.execute(f"UPDATE expenses SET {', '.join(fields)} WHERE id = ?", params)
    conn.commit()
    conn.close()


def delete_expense(expense_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
    conn.commit()
    conn.close()


def get_expense_summary(trip_id):
    """
    Return per-member totals combining per-diem allowance and actual expenses.

    Output:
    [
        {
            "member_id": 1,
            "name": "Adaeze Okonkwo",
            "role": "CEO",
            "daily_rate": 180,
            "days": 6,
            "currency": "USD",
            "allowance": 1080,
            "spent": 750,
            "remaining": 330,
            "entry_count": 5,
        },
        ...
    ]
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Get all members referenced by per_diem OR expenses
    c.execute("""
        SELECT DISTINCT m.id, m.name, m.role
        FROM delegation_members m
        WHERE m.id IN (
            SELECT member_id FROM per_diem WHERE trip_id = ?
            UNION
            SELECT member_id FROM expenses WHERE trip_id = ? AND member_id IS NOT NULL
        )
    """, (trip_id, trip_id))
    members = c.fetchall()

    summary = []
    for m in members:
        # Per diem
        c.execute("SELECT daily_rate, days, currency FROM per_diem WHERE trip_id = ? AND member_id = ?",
                  (trip_id, m["id"]))
        pd_row = c.fetchone()
        daily_rate = pd_row["daily_rate"] if pd_row else 0
        days = pd_row["days"] if pd_row else 0
        currency = pd_row["currency"] if pd_row else "USD"
        allowance = (daily_rate or 0) * (days or 0)

        # Expenses
        c.execute("SELECT COALESCE(SUM(amount), 0) as total, COUNT(*) as cnt FROM expenses WHERE trip_id = ? AND member_id = ?",
                  (trip_id, m["id"]))
        exp_row = c.fetchone()
        spent = exp_row["total"] or 0
        entry_count = exp_row["cnt"] or 0

        summary.append({
            "member_id": m["id"],
            "name": m["name"],
            "role": m["role"],
            "daily_rate": daily_rate,
            "days": days,
            "currency": currency,
            "allowance": allowance,
            "spent": spent,
            "remaining": allowance - spent,
            "entry_count": entry_count,
        })

    conn.close()
    return summary


def get_trip_delegation_members(trip_id):
    """Return delegation members assigned to this trip's items."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT DISTINCT m.*
        FROM delegation_members m
        JOIN item_delegation id ON m.id = id.member_id
        JOIN itinerary_items i ON i.id = id.item_id
        WHERE i.trip_id = ?
        ORDER BY m.name
    """, (trip_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


# =========================================================
# PACKING LISTS
# =========================================================


def create_packing_list(trip_id, member_id, template_id=None):
    """Create a packing list for a trip member. Returns list_id (existing if already present)."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT id FROM packing_lists WHERE trip_id = ? AND member_id = ?",
        (trip_id, member_id),
    )
    row = c.fetchone()
    if row:
        conn.close()
        return row[0]
    c.execute(
        """INSERT INTO packing_lists (trip_id, member_id, template_id)
                 VALUES (?, ?, ?)""",
        (trip_id, member_id, template_id),
    )
    conn.commit()
    new_id = c.lastrowid
    conn.close()
    return new_id


def get_packing_list(trip_id, member_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        """SELECT * FROM packing_lists
                 WHERE trip_id = ? AND member_id = ?""",
        (trip_id, member_id),
    )
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def get_packing_lists_for_trip(trip_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""SELECT * FROM packing_lists WHERE trip_id = ?""", (trip_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def delete_packing_list(list_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM packing_lists WHERE id = ?", (list_id,))
    conn.commit()
    conn.close()


def add_packing_item(list_id, item_name, category=None, sort_order=0):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """INSERT INTO packing_items (list_id, category, item_name, sort_order)
                 VALUES (?, ?, ?, ?)""",
        (list_id, category, item_name, sort_order),
    )
    conn.commit()
    new_id = c.lastrowid
    conn.close()
    return new_id


def get_packing_items(list_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        """SELECT * FROM packing_items
                 WHERE list_id = ?
                 ORDER BY sort_order ASC, id ASC""",
        (list_id,),
    )
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def toggle_packing_item(item_id, packed):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "UPDATE packing_items SET packed = ? WHERE id = ?",
        (1 if packed else 0, item_id),
    )
    conn.commit()
    conn.close()


def delete_packing_item(item_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM packing_items WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()


def apply_packing_template(trip_id, member_id, template_id):
    """
    Apply a packing template to a member's packing list.
    Creates the list if needed, then adds items from the template.
    Existing items with the same name are skipped.
    """
    tpl = get_packing_template(template_id)
    if not tpl:
        return 0
    list_id = create_packing_list(trip_id, member_id, template_id)
    try:
        items_to_add = json.loads(tpl.get("items_json") or "[]")
    except Exception:
        items_to_add = []

    existing = {item["item_name"].lower() for item in get_packing_items(list_id)}

    added = 0
    for i, name in enumerate(items_to_add):
        if name.lower() in existing:
            continue
        add_packing_item(
            list_id,
            item_name=name,
            category=tpl.get("category"),
            sort_order=i,
        )
        added += 1
    return added


# =========================================================
# TRIP CHECKLISTS
# =========================================================


def create_trip_checklist(trip_id, name, description=None, template_id=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """INSERT INTO trip_checklists (trip_id, name, description, template_id)
                 VALUES (?, ?, ?, ?)""",
        (trip_id, name, description, template_id),
    )
    conn.commit()
    new_id = c.lastrowid
    conn.close()
    return new_id


def get_trip_checklists(trip_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        """SELECT * FROM trip_checklists
                 WHERE trip_id = ?
                 ORDER BY created_at ASC""",
        (trip_id,),
    )
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_trip_checklist(checklist_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM trip_checklists WHERE id = ?", (checklist_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def update_trip_checklist(checklist_id, name=None, description=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    fields = []
    params = []
    if name is not None:
        fields.append("name = ?")
        params.append(name)
    if description is not None:
        fields.append("description = ?")
        params.append(description)
    if not fields:
        conn.close()
        return
    params.append(checklist_id)
    c.execute(f"UPDATE trip_checklists SET {', '.join(fields)} WHERE id = ?", params)
    conn.commit()
    conn.close()


def delete_trip_checklist(checklist_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM trip_checklists WHERE id = ?", (checklist_id,))
    conn.commit()
    conn.close()


def add_checklist_item(checklist_id, item_text, sort_order=0):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """INSERT INTO trip_checklist_items
                 (checklist_id, item_text, sort_order)
                 VALUES (?, ?, ?)""",
        (checklist_id, item_text, sort_order),
    )
    conn.commit()
    new_id = c.lastrowid
    conn.close()
    return new_id


def get_checklist_items(checklist_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        """SELECT * FROM trip_checklist_items
                 WHERE checklist_id = ?
                 ORDER BY sort_order ASC, id ASC""",
        (checklist_id,),
    )
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def toggle_checklist_item(item_id, is_done):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "UPDATE trip_checklist_items SET is_done = ? WHERE id = ?",
        (1 if is_done else 0, item_id),
    )
    conn.commit()
    conn.close()


def delete_checklist_item(item_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM trip_checklist_items WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()


def apply_checklist_template(trip_id, template_id):
    """
    Create a new trip checklist from a template and seed it with items.
    Returns the new checklist_id.
    """
    tpl = get_checklist_template(template_id)
    if not tpl:
        return None
    checklist_id = create_trip_checklist(
        trip_id,
        name=tpl["name"],
        description=tpl.get("description"),
        template_id=template_id,
    )
    try:
        items = json.loads(tpl.get("items_json") or "[]")
    except Exception:
        items = []
    for i, text in enumerate(items):
        add_checklist_item(checklist_id, text, sort_order=i)
    return checklist_id
# =========================================================
# HOSPITALS
# =========================================================


def add_hospital(
    city, country, name, address=None, phone=None, maps_url=None, notes=None
):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """INSERT INTO hospitals
                 (city, country, name, address, phone, maps_url, notes)
                 VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (city, country, name, address, phone, maps_url, notes),
    )
    conn.commit()
    new_id = c.lastrowid
    conn.close()
    return new_id


def get_hospitals(city=None, country=None, active_only=True):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    conditions = []
    params = []
    if active_only:
        conditions.append("is_active = 1")
    if city:
        conditions.append("city = ?")
        params.append(city)
    if country:
        conditions.append("country = ?")
        params.append(country)
    query = "SELECT * FROM hospitals"
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY country, city, name"
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_hospital(hospital_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM hospitals WHERE id = ?", (hospital_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def update_hospital(hospital_id, **kwargs):
    if not kwargs:
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    fields = []
    params = []
    for k, v in kwargs.items():
        fields.append(f"{k} = ?")
        params.append(v)
    params.append(hospital_id)
    c.execute(f"UPDATE hospitals SET {', '.join(fields)} WHERE id = ?", params)
    conn.commit()
    conn.close()


def delete_hospital(hospital_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM hospitals WHERE id = ?", (hospital_id,))
    conn.commit()
    conn.close()


def get_hospitals_for_trip(trip_id):
    """Return hospitals for the cities of a trip's stops."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        """SELECT DISTINCT h.*
                 FROM hospitals h
                 JOIN trip_stops s ON LOWER(s.city) = LOWER(h.city)
                 WHERE s.trip_id = ? AND h.is_active = 1
                 ORDER BY s.stop_order, h.name""",
        (trip_id,),
    )
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


# =========================================================
# EXCHANGE RATES (Stage 1 – storage helpers only)
# =========================================================


def save_exchange_rate(rate_date, base_currency, target_currency, rate, source=None):
    """
    Insert or replace an exchange rate row.
    `rate` means: 1 base_currency = `rate` target_currency.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """INSERT OR REPLACE INTO exchange_rates
           (rate_date, base_currency, target_currency, rate, source)
           VALUES (?, ?, ?, ?, ?)""",
        (rate_date, base_currency, target_currency, rate, source),
    )
    conn.commit()
    conn.close()


def get_exchange_rate(rate_date, base_currency, target_currency):
    """
    Return a single exchange_rates row (dict) or None.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        """SELECT * FROM exchange_rates
           WHERE rate_date = ? AND base_currency = ? AND target_currency = ?""",
        (rate_date, base_currency, target_currency),
    )
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def get_nearest_exchange_rate(rate_date, base_currency, target_currency, days=7):
    """
    Return the rate closest to `rate_date` within ±`days`.
    Prefers the closest by absolute date difference.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        """SELECT * FROM exchange_rates
           WHERE base_currency = ? AND target_currency = ?
             AND rate_date BETWEEN date(?, ?) AND date(?, ?)
           ORDER BY ABS(julianday(rate_date) - julianday(?))
           LIMIT 1""",
        (
            base_currency,
            target_currency,
            rate_date,
            f"-{days} days",
            rate_date,
            f"+{days} days",
            rate_date,
        ),
    )
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None
