import database as db
from datetime import datetime, timedelta
import os
import json


# ------------------------------------------------------------
# 1. WIPE EXISTING DATA (optional – comment out if you want to keep data)
# ------------------------------------------------------------
def wipe_database():
    """Delete the database file and re-initialize."""
    if os.path.exists("travel_planner.db"):
        os.remove("travel_planner.db")
        print("🗑️ Old database deleted.")
    db.init_db()
    print("✅ New database initialized.")


# Uncomment the next line if you want to wipe data every time:
# wipe_database()

# ------------------------------------------------------------
# 2. INITIALISE DATABASE (if not wiped)
# ------------------------------------------------------------
db.init_db()

# ------------------------------------------------------------
# 3. COMPANIES
# ------------------------------------------------------------
companies = [
    {
        "name": "Nexus Ventures",
        "cost_center": "CC-2026-TECH",
        "policy": "Business class for >6hr flights.",
    },
    {
        "name": "Apex Financial",
        "cost_center": "CC-2026-FIN",
        "policy": "Economy only, no exceptions.",
    },
    {
        "name": "Global Innovations",
        "cost_center": "CC-2026-GLOB",
        "policy": "Flexible policy.",
    },
]

company_ids = {}
for comp in companies:
    existing = db.get_all_companies()
    existing_names = [c[1] for c in existing]
    if comp["name"] not in existing_names:
        cid = db.add_company(comp["name"], comp["cost_center"], comp["policy"])
        company_ids[comp["name"]] = cid
    else:
        for c in existing:
            if c[1] == comp["name"]:
                company_ids[comp["name"]] = c[0]
                break

# ------------------------------------------------------------
# 4. EXECUTIVES (including a duplicate email)
# ------------------------------------------------------------
executives = [
    {
        "name": "Sarah Chen",
        "email": "sarah@nexusventures.com",
        "timezone": "Europe/London",
        "seat": "Window",
        "hotel": "Marriott Bonvoy Ambassador",
        "ff": "BA-1234567",
        "diet": "Vegetarian",
        "passport": "GB123456789",
        "airline": "British Airways",
        "tsa": "KTN000111",
        "meal": "Vegetarian",
        "company": "Nexus Ventures",
    },
    {
        "name": "Marcus Sterling",
        "email": "marcus@apexfinancial.com",
        "timezone": "America/New_York",
        "seat": "Aisle",
        "hotel": "Hilton Honors Diamond",
        "ff": "AA-7890123",
        "diet": "Gluten-free",
        "passport": "US987654321",
        "airline": "American Airlines",
        "tsa": "KTN555666",
        "meal": "Gluten-Free",
        "company": "Apex Financial",
    },
    {
        "name": "Priya Sharma",
        "email": "priya@apexfinancial.com",
        "timezone": "Asia/Singapore",
        "seat": "Window",
        "hotel": "IHG Rewards Platinum",
        "ff": "SQ-3456789",
        "diet": "None",
        "passport": "SG567890123",
        "airline": "Singapore Airlines",
        "tsa": "N/A",
        "meal": "Kosher",
        "company": "Apex Financial",
    },
    # DUPLICATE EMAIL – to test duplicate detection
    {
        "name": "Sarah Chen (duplicate)",
        "email": "sarah@nexusventures.com",  # same email as first
        "timezone": "America/New_York",
        "seat": "Aisle",
        "hotel": "None",
        "ff": "N/A",
        "diet": "None",
        "passport": "N/A",
        "airline": "None",
        "tsa": "N/A",
        "meal": "No Preference",
        "company": "Global Innovations",
    },
]

exec_ids = {}
for exec_data in executives:
    company_id = company_ids[exec_data["company"]]
    existing_execs = db.get_all_executives()
    exists = False
    for e in existing_execs:
        # e[0] = id, e[1] = name, e[2] = company name
        if e[1] == exec_data["name"] and e[2] == exec_data["company"]:
            exec_ids[exec_data["name"]] = e[0]
            exists = True
            print(f"⚠️ Executive '{exec_data['name']}' already exists. Skipping.")
            break
    if not exists:
        eid = db.add_executive(
            company_id=company_id,
            name=exec_data["name"],
            email=exec_data["email"],
            timezone=exec_data["timezone"],
            seat_preference=exec_data["seat"],
            hotel_loyalty=exec_data["hotel"],
            frequent_flyer_number=exec_data["ff"],
            dietary_restrictions=exec_data["diet"],
            passport_number=exec_data["passport"],
            preferred_airline=exec_data["airline"],
            tsa_precheck=exec_data["tsa"],
            meal_preference=exec_data["meal"],
        )
        exec_ids[exec_data["name"]] = eid
        print(f"✅ Added executive: {exec_data['name']}")

# ------------------------------------------------------------
# 5. EXECUTIVE MEMBERSHIPS
# ------------------------------------------------------------
memberships = [
    {
        "exec": "Sarah Chen",
        "category": "airline",
        "program": "Delta SkyMiles",
        "number": "DL-4567890",
    },
    {
        "exec": "Sarah Chen",
        "category": "hotel",
        "program": "Hilton Honors",
        "number": "HH-9876543",
    },
    {
        "exec": "Marcus Sterling",
        "category": "airline",
        "program": "United MileagePlus",
        "number": "UA-5556667",
    },
    {
        "exec": "Marcus Sterling",
        "category": "car",
        "program": "Hertz Gold",
        "number": "HZ-1234567",
    },
    {
        "exec": "Priya Sharma",
        "category": "airline",
        "program": "Cathay Pacific",
        "number": "CX-2345678",
    },
    {
        "exec": "Priya Sharma",
        "category": "hotel",
        "program": "Accor Live Limitless",
        "number": "ALL-8765432",
    },
]

for m in memberships:
    if m["exec"] not in exec_ids:
        print(f"⚠️ Executive '{m['exec']}' not found. Skipping membership.")
        continue
    exec_id = exec_ids[m["exec"]]
    existing_mems = db.get_memberships(exec_id)
    exists = any(
        mem["program_name"] == m["program"] and mem["membership_number"] == m["number"]
        for mem in existing_mems
    )
    if not exists:
        db.add_membership(exec_id, m["category"], m["program"], m["number"])
        print(f"✅ Added membership: {m['exec']} - {m['program']}")

# ------------------------------------------------------------
# 6. CUSTOM CATEGORIES
# ------------------------------------------------------------
extra_cats = ["Conference", "Site Visit", "Workshop", "Car Rental"]
existing_cats = [cat[1] for cat in db.get_all_categories()]
for cat in extra_cats:
    if cat not in existing_cats:
        db.add_category(cat)
        print(f"✅ Added category: {cat}")


# ------------------------------------------------------------
# 7. HELPER: Create a trip with full options (currencies, etc.)
# ------------------------------------------------------------
def create_trip_with_details(
    exec_name,
    purpose,
    status,
    stops_data,
    items_data,
    budget=5000,
    display_currency="USD",
    base_currency="USD",
):
    if exec_name not in exec_ids:
        print(f"⚠️ Executive '{exec_name}' not found. Skipping trip '{purpose}'.")
        return None
    exec_id = exec_ids[exec_name]
    first_stop = stops_data[0]
    last_stop = stops_data[-1]
    overall_start = first_stop["start_date"].isoformat()
    overall_end = last_stop["end_date"].isoformat()
    stop_names = [s["city"] for s in stops_data]
    dest_summary = " → ".join(stop_names)

    # Check if a trip with same purpose and exec exists (to avoid duplicates)
    existing = db.get_trip_by_purpose_and_date(
        exec_id, purpose, overall_start, overall_end
    )
    if existing:
        trip_id = existing
        print(f"⚠️ Trip '{purpose}' already exists. Updating instead.")
    else:
        trip_id = db.create_or_get_trip(
            exec_id,
            dest_summary,
            overall_start,
            overall_end,
            purpose,
            display_currency,
            base_currency,
        )
    db.update_trip_budget(trip_id, budget)
    db.update_trip_status(trip_id, status)

    # Set departure details (use first stop's city as departure for demo)
    db.update_trip_departure_details(
        trip_id,
        departure_city=stops_data[0]["city"],
        departure_region=stops_data[0].get("region", ""),
        departure_country=stops_data[0].get("country", ""),
    )

    # Add stops
    db.delete_all_trip_stops(trip_id)
    for idx, stop in enumerate(stops_data, 1):
        db.add_trip_stop(
            trip_id,
            stop_order=idx,
            city=stop["city"],
            country=stop.get("country", ""),
            region=stop.get("region", ""),
            start_date=stop["start_date"].isoformat(),
            end_date=stop["end_date"].isoformat(),
            notes=stop.get("notes", ""),
        )

    # Add itinerary items
    for item in items_data:
        # For duplicate detection, we may pass cost_currency and snapshot_rate
        cost_currency = item.get("cost_currency", "USD")
        snapshot_rate = item.get("snapshot_rate", 1.0)
        db.add_itinerary_item(
            trip_id,
            item_type=item["type"],
            description=item["description"],
            datetime_start=item["start"].isoformat(),
            datetime_end=item["end"].isoformat() if item.get("end") else None,
            location=item.get("location", ""),
            cost=item.get("cost", 0),
            confirmation_code=item.get("code", ""),
            notes=item.get("notes", ""),
            is_confirmed=1 if item.get("confirmed", False) else 0,
            cost_currency=cost_currency,
            exchange_rate_snapshot=snapshot_rate,
        )
    print(f"✅ Created/updated trip: {purpose} ({status}) for {exec_name}")
    return trip_id


# ------------------------------------------------------------
# 8. SAMPLE DATES (relative to today)
# ------------------------------------------------------------
now = datetime.now()

# ------------------------------------------------------------
# 9. TRIP 1: DRAFT – Sarah Chen (Nexus Ventures) – with duplicate item
# ------------------------------------------------------------
stops_sarah = [
    {
        "city": "London",
        "country": "United Kingdom",
        "region": "England",
        "start_date": now + timedelta(days=10),
        "end_date": now + timedelta(days=12),
    },
    {
        "city": "Paris",
        "country": "France",
        "region": "Île-de-France",
        "start_date": now + timedelta(days=13),
        "end_date": now + timedelta(days=15),
    },
]
# Duplicate item: same description, time, cost – to trigger duplicate detection
items_sarah = [
    {
        "type": "Flight",
        "description": "BA 178 London → Paris",
        "start": now + timedelta(days=13, hours=8),
        "end": now + timedelta(days=13, hours=9, minutes=30),
        "location": "LHR",
        "cost": 120.50,
        "confirmed": False,
        "code": "BA178-ABC",
        "notes": "Economy",
        "cost_currency": "GBP",
        "snapshot_rate": 1.25,
    },
    # DUPLICATE – exact same details (will trigger duplicate item warning)
    {
        "type": "Flight",
        "description": "BA 178 London → Paris",
        "start": now + timedelta(days=13, hours=8),
        "end": now + timedelta(days=13, hours=9, minutes=30),
        "location": "LHR",
        "cost": 120.50,
        "confirmed": False,
        "code": "BA178-DEF",
        "notes": "Economy",
        "cost_currency": "GBP",
        "snapshot_rate": 1.25,
    },
    {
        "type": "Hotel",
        "description": "Marriott Champs-Élysées",
        "start": now + timedelta(days=13, hours=14),
        "end": now + timedelta(days=15, hours=11),
        "location": "Paris",
        "cost": 450.00,
        "confirmed": False,
        "code": "MAR-4567",
        "notes": "Standard room",
        "cost_currency": "EUR",
        "snapshot_rate": 1.10,
    },
]
trip1_id = create_trip_with_details(
    exec_name="Sarah Chen",
    purpose="Q3 Innovation Summit",
    status="draft",
    stops_data=stops_sarah,
    items_data=items_sarah,
    budget=2000,
    display_currency="EUR",
    base_currency="USD",
)

# ------------------------------------------------------------
# 10. TRIP 2: APPROVED – Marcus Sterling (Apex Financial) – with similar expenses
# ------------------------------------------------------------
stops_marcus = [
    {
        "city": "New York",
        "country": "United States",
        "region": "NY",
        "start_date": now + timedelta(days=20),
        "end_date": now + timedelta(days=22),
    },
    {
        "city": "Dubai",
        "country": "United Arab Emirates",
        "region": "Dubai",
        "start_date": now + timedelta(days=23),
        "end_date": now + timedelta(days=25),
    },
]
# Similar expenses: same day, same type, close amount -> trigger fuzzy duplicate detection
items_marcus = [
    {
        "type": "Flight",
        "description": "Emirates EK 202 New York → Dubai",
        "start": now + timedelta(days=23, hours=7),
        "end": now + timedelta(days=23, hours=14),
        "location": "JFK",
        "cost": 1400.00,
        "confirmed": True,
        "code": "EK202-456",
        "notes": "Business Class",
        "cost_currency": "USD",
        "snapshot_rate": 1.0,
    },
    {
        "type": "Meeting",
        "description": "Finance Summit Keynote",
        "start": now + timedelta(days=24, hours=9),
        "end": now + timedelta(days=24, hours=11),
        "location": "Dubai World Trade Centre",
        "cost": 0,
        "confirmed": True,
        "code": "",
        "notes": "Main stage",
        "cost_currency": "USD",
        "snapshot_rate": 1.0,
    },
    # Similar expense: another meeting on same day, similar cost (near zero)
    {
        "type": "Meeting",
        "description": "Finance Summit Breakout",
        "start": now + timedelta(days=24, hours=11, minutes=30),
        "end": now + timedelta(days=24, hours=13),
        "location": "Dubai World Trade Centre",
        "cost": 0,
        "confirmed": True,
        "code": "",
        "notes": "Breakout",
        "cost_currency": "USD",
        "snapshot_rate": 1.0,
    },
]
trip2_id = create_trip_with_details(
    exec_name="Marcus Sterling",
    purpose="APAC Finance Tour",
    status="approved",
    stops_data=stops_marcus,
    items_data=items_marcus,
    budget=8000,
    display_currency="USD",
    base_currency="USD",
)

# ------------------------------------------------------------
# 11. TRIP 3: FINAL – Priya Sharma (Apex Financial) – with duplicate receipt
# ------------------------------------------------------------
stops_priya = [
    {
        "city": "Singapore",
        "country": "Singapore",
        "region": "Singapore",
        "start_date": now + timedelta(days=5),
        "end_date": now + timedelta(days=7),
    },
    {
        "city": "Bangkok",
        "country": "Thailand",
        "region": "Bangkok",
        "start_date": now + timedelta(days=8),
        "end_date": now + timedelta(days=10),
    },
]
items_priya = [
    {
        "type": "Flight",
        "description": "SQ 116 Singapore → Bangkok",
        "start": now + timedelta(days=8, hours=8),
        "end": now + timedelta(days=8, hours=10),
        "location": "SIN",
        "cost": 300.00,
        "confirmed": True,
        "code": "SQ116-123",
        "notes": "Economy",
        "cost_currency": "SGD",
        "snapshot_rate": 0.75,
    },
    {
        "type": "Hotel",
        "description": "Siam Kempinski Bangkok",
        "start": now + timedelta(days=8, hours=12),
        "end": now + timedelta(days=10, hours=12),
        "location": "Bangkok",
        "cost": 450.00,
        "confirmed": True,
        "code": "SK-789",
        "notes": "Executive Room",
        "cost_currency": "THB",
        "snapshot_rate": 0.03,
    },
]
trip3_id = create_trip_with_details(
    exec_name="Priya Sharma",
    purpose="ASEAN Strategy Workshops",
    status="final",
    stops_data=stops_priya,
    items_data=items_priya,
    budget=2500,
    display_currency="SGD",
    base_currency="USD",
)

# Simulate duplicate receipts: attach same receipt file to two items in trip3
if trip3_id:
    items = db.get_items_for_trip(trip3_id)
    if len(items) >= 2:
        # Create a dummy receipt folder and file
        os.makedirs("receipts", exist_ok=True)
        trip_folder = f"receipts/trip_{trip3_id}"
        os.makedirs(trip_folder, exist_ok=True)
        receipt_path = os.path.join(trip_folder, "dummy_receipt.pdf")
        # Write a dummy file
        with open(receipt_path, "w") as f:
            f.write("Dummy receipt content")
        # Attach to first two items
        for i in range(2):
            db.update_receipt_path(items[i]["id"], receipt_path)
        print(
            f"✅ Attached duplicate receipt to items {items[0]['id']} and {items[1]['id']}"
        )

# ------------------------------------------------------------
# 12. TRIP 4: OVERLAPPING DRAFT – Sarah Chen (to test duplicate trip detection)
# ------------------------------------------------------------
# This trip has same purpose and overlapping dates with Trip 1
stops_overlap = [
    {
        "city": "London",
        "country": "United Kingdom",
        "region": "England",
        "start_date": now + timedelta(days=11),
        "end_date": now + timedelta(days=13),
    },
]
items_overlap = [
    {
        "type": "Meeting",
        "description": "Internal Review",
        "start": now + timedelta(days=11, hours=10),
        "end": now + timedelta(days=11, hours=12),
        "location": "London Office",
        "cost": 0,
        "confirmed": False,
        "code": "",
        "notes": "",
    },
]
create_trip_with_details(
    exec_name="Sarah Chen",
    purpose="Q3 Innovation Summit",  # same purpose as Trip 1
    status="draft",
    stops_data=stops_overlap,
    items_data=items_overlap,
    budget=500,
    display_currency="GBP",
    base_currency="USD",
)


# ------------------------------------------------------------
# 13. SAVE TRIP TEMPLATES from existing trips
# ------------------------------------------------------------
def save_template_from_trip(trip_id, template_name, description=None):
    existing = db.get_trip_templates()
    for t in existing:
        if t["name"] == template_name:
            print(f"⚠️ Template '{template_name}' already exists. Skipping.")
            return
    new_id = db.save_trip_as_template(trip_id, template_name, description)
    if new_id:
        print(f"✅ Saved template: {template_name}")
    else:
        print(f"❌ Failed to save template: {template_name}")


# Save a template from Sarah's trip (Trip 1)
if trip1_id:
    save_template_from_trip(
        trip1_id,
        template_name="Sarah Chen - Q3 Summit Template",
        description="Two-city trip (London → Paris) with flight and hotel.",
    )

# Save a template from Marcus's trip (Trip 2)
if trip2_id:
    save_template_from_trip(
        trip2_id,
        template_name="Marcus Sterling - APAC Finance Template",
        description="New York → Dubai with meetings.",
    )

# ------------------------------------------------------------
# 14. FINISH
# ------------------------------------------------------------
print("\n" + "=" * 60)
print("✅ Seed data loaded successfully!")
print("=" * 60)
print(f"   - Companies: {len(companies)}")
print(f"   - Executives: {len(executives)} (including one duplicate email)")
print("   - Trips: 4 (Draft, Approved, Final, Overlapping Draft)")
print("   - Duplicate scenarios:")
print("     - Duplicate item in Trip 1 (same description/time/cost)")
print("     - Similar expenses in Trip 2 (same day, same type, near-zero cost)")
print("     - Duplicate receipts in Trip 3 (same file attached to two items)")
print("     - Overlapping trip (Trip 4) with same purpose as Trip 1")
print("   - Templates: 2 saved from Trip 1 and Trip 2")
print("=" * 60)
print("\n🚀 You can now run: streamlit run app.py")
