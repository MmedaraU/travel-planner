import database as db
from datetime import datetime, timedelta

# ------------------------------------------------------------
# 1. INITIALISE DATABASE (creates tables if missing)
# ------------------------------------------------------------
db.init_db()

# ------------------------------------------------------------
# 2. COMPANIES
# ------------------------------------------------------------
db.add_company(
    "Nexus Ventures", "CC-2026-TECH", "Business class allowed for flights > 6 hrs"
)
db.add_company("Apex Financial", "CC-2026-FIN", "Economy only, no exceptions")
db.add_company(
    "Omni Consulting", "CC-2026-CONS", "Premium economy for all international travel"
)
db.add_company(
    "GreenLeaf Energy", "CC-2026-ENERGY", "Cabin class based on flight duration"
)

# ------------------------------------------------------------
# 3. EXECUTIVES (with preferences and travel documents)
# ------------------------------------------------------------
# Executive 1: CEO of Nexus Ventures
db.add_executive(
    company_id=1,
    name="Elena V. Petrova",
    email="elena@nexusventures.com",
    timezone="Europe/London",
    seat_preference="Window",
    hotel_loyalty="Marriott Bonvoy Ambassador Elite",
    frequent_flyer_number="BA-1234567",
    dietary_restrictions="None",
    passport_number="GB123456789",
    preferred_airline="British Airways",
    tsa_precheck="KTN000111",
    meal_preference="Vegetarian",
)

# Executive 2: CFO of Apex Financial (based in NY)
db.add_executive(
    company_id=2,
    name="Marcus T. Sterling",
    email="marcus@apexfinancial.com",
    timezone="America/New_York",
    seat_preference="Aisle",
    hotel_loyalty="Hilton Honors Diamond",
    frequent_flyer_number="AA-7890123",
    dietary_restrictions="Gluten-free",
    passport_number="US987654321",
    preferred_airline="American Airlines",
    tsa_precheck="KTN555666",
    meal_preference="Gluten-Free",
)

# Executive 3: Partner at Omni Consulting (based in Singapore)
db.add_executive(
    company_id=3,
    name="Priya K. Sharma",
    email="priya@omniconsult.com",
    timezone="Asia/Singapore",
    seat_preference="Window",
    hotel_loyalty="IHG Rewards Platinum",
    frequent_flyer_number="SQ-3456789",
    dietary_restrictions="None",
    passport_number="SG567890123",
    preferred_airline="Singapore Airlines",
    tsa_precheck="N/A",
    meal_preference="Kosher",
)

# Executive 4: CTO of GreenLeaf Energy (based in Lagos)
db.add_executive(
    company_id=4,
    name="Chidi O. Okonkwo",
    email="chidi@greenleaf.energy",
    timezone="Africa/Lagos",
    seat_preference="Aisle",
    hotel_loyalty="Radisson Rewards Gold",
    frequent_flyer_number="EK-9012345",
    dietary_restrictions="Halal",
    passport_number="NG234567890",
    preferred_airline="Emirates",
    tsa_precheck="N/A",
    meal_preference="Halal",
)

# ------------------------------------------------------------
# 4. EXECUTIVE MEMBERSHIPS (multiple loyalty programmes)
# ------------------------------------------------------------
# Elena – additional memberships
db.add_membership(
    exec_id=1,
    category="airline",
    program_name="Delta SkyMiles",
    membership_number="DL-4567890",
)
db.add_membership(
    exec_id=1,
    category="hotel",
    program_name="Hilton Honors",
    membership_number="HH-9876543",
)

# Marcus – additional memberships
db.add_membership(
    exec_id=2,
    category="airline",
    program_name="United MileagePlus",
    membership_number="UA-5556667",
)
db.add_membership(
    exec_id=2, category="car", program_name="Hertz Gold", membership_number="HZ-1234567"
)

# Priya – additional memberships
db.add_membership(
    exec_id=3,
    category="airline",
    program_name="Cathay Pacific",
    membership_number="CX-2345678",
)
db.add_membership(
    exec_id=3,
    category="hotel",
    program_name="Accor Live Limitless",
    membership_number="ALL-8765432",
)

# Chidi – additional memberships
db.add_membership(
    exec_id=4,
    category="hotel",
    program_name="Marriott Bonvoy",
    membership_number="MB-3456789",
)

# ------------------------------------------------------------
# 5. CUSTOM CATEGORIES (optional, but adds flavour)
# ------------------------------------------------------------
db.add_category("Conference")
db.add_category("Site Visit")
db.add_category("Workshop")


# ------------------------------------------------------------
# 6. SAMPLE TRIPS (with stops and itinerary items)
# ------------------------------------------------------------
def create_sample_trip(
    exec_id, purpose, stops_data, items_data, budget=5000, status="draft"
):
    """
    Helper to create a trip with stops and itinerary items.
    stops_data: list of dicts with city, country, region, start_date, end_date, notes
    items_data: list of dicts with type, description, start, end, location, cost, confirmed, code, notes
    """
    # Determine overall date range
    first_stop = stops_data[0]
    last_stop = stops_data[-1]
    start_date = first_stop["start_date"].isoformat()
    end_date = last_stop["end_date"].isoformat()

    # Build destination summary
    stop_names = [s["city"] for s in stops_data]
    dest_summary = " → ".join(stop_names)

    # Create trip
    trip_id = db.create_or_get_trip(
        exec_id, dest_summary, start_date, end_date, purpose
    )
    db.update_trip_budget(trip_id, budget)
    db.update_trip_status(trip_id, status)

    # Add departure details (use first stop as departure? In real app, departure is separate; for demo we'll set a dummy)
    # We'll set departure as "London" for the first executive, etc. – but we can skip to keep it simple.
    db.update_trip_departure_details(
        trip_id,
        departure_city="London",
        departure_region="UK",
        departure_country="United Kingdom",
    )

    # Add stops
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
        db.add_itinerary_item(
            trip_id,
            item_type=item["type"],
            description=item["description"],
            datetime_start=item["start"].isoformat(),
            datetime_end=item["end"].isoformat(),
            location=item.get("location", ""),
            cost=item.get("cost", 0),
            confirmation_code=item.get("code", ""),
            notes=item.get("notes", ""),
            is_confirmed=1 if item.get("confirmed", False) else 0,
        )

    return trip_id


# ---- TRIP 1: Elena (Nexus Ventures) - UK/USA roadshow ----
now = datetime.now()
stops_elena = [
    {
        "city": "London",
        "country": "United Kingdom",
        "region": "England",
        "start_date": now + timedelta(days=10),
        "end_date": now + timedelta(days=12),
    },
    {
        "city": "New York",
        "country": "United States",
        "region": "NY",
        "start_date": now + timedelta(days=13),
        "end_date": now + timedelta(days=15),
    },
    {
        "city": "San Francisco",
        "country": "United States",
        "region": "CA",
        "start_date": now + timedelta(days=16),
        "end_date": now + timedelta(days=18),
    },
]
items_elena = [
    {
        "type": "Flight",
        "description": "BA 178 London→New York",
        "start": now + timedelta(days=13, hours=8),
        "end": now + timedelta(days=13, hours=11),
        "location": "LHR",
        "cost": 1200,
        "confirmed": True,
        "code": "BA178-ABC",
        "notes": "Premium Economy",
    },
    {
        "type": "Hotel",
        "description": "Marriott Marquis NY",
        "start": now + timedelta(days=13, hours=15),
        "end": now + timedelta(days=15, hours=11),
        "location": "Times Square",
        "cost": 680,
        "confirmed": True,
        "code": "MAR-4567",
        "notes": "Suite",
    },
    {
        "type": "Flight",
        "description": "UA 345 NY→San Francisco",
        "start": now + timedelta(days=16, hours=9),
        "end": now + timedelta(days=16, hours=12),
        "location": "JFK",
        "cost": 550,
        "confirmed": False,
        "code": "UA345-XYZ",
        "notes": "Economy",
    },
    {
        "type": "Meeting",
        "description": "Investor Presentation",
        "start": now + timedelta(days=14, hours=10),
        "end": now + timedelta(days=14, hours=12),
        "location": "Nexus NY Office",
        "cost": 0,
        "confirmed": True,
        "code": "",
        "notes": "Board room A",
    },
    {
        "type": "Meeting",
        "description": "Tech Demo SF",
        "start": now + timedelta(days=17, hours=14),
        "end": now + timedelta(days=17, hours=16),
        "location": "Moscone Center",
        "cost": 0,
        "confirmed": True,
        "code": "",
        "notes": "Workshop",
    },
]
create_sample_trip(
    exec_id=1,
    purpose="Investor Roadshow USA",
    stops_data=stops_elena,
    items_data=items_elena,
    budget=4500,
    status="approved",
)

# ---- TRIP 2: Marcus (Apex Financial) - APAC finance conference ----
stops_marcus = [
    {
        "city": "New York",
        "country": "United States",
        "region": "NY",
        "start_date": now + timedelta(days=20),
        "end_date": now + timedelta(days=21),
    },
    {
        "city": "Dubai",
        "country": "United Arab Emirates",
        "region": "Dubai",
        "start_date": now + timedelta(days=22),
        "end_date": now + timedelta(days=24),
    },
    {
        "city": "Singapore",
        "country": "Singapore",
        "region": "Singapore",
        "start_date": now + timedelta(days=25),
        "end_date": now + timedelta(days=28),
    },
]
items_marcus = [
    {
        "type": "Flight",
        "description": "Emirates EK 202 NY→Dubai",
        "start": now + timedelta(days=22, hours=7),
        "end": now + timedelta(days=22, hours=14),
        "location": "JFK",
        "cost": 1400,
        "confirmed": True,
        "code": "EK202-456",
        "notes": "Business Class",
    },
    {
        "type": "Hotel",
        "description": "Burj Al Arab",
        "start": now + timedelta(days=22, hours=16),
        "end": now + timedelta(days=24, hours=12),
        "location": "Dubai",
        "cost": 1200,
        "confirmed": True,
        "code": "BAA-789",
        "notes": "Ocean Suite",
    },
    {
        "type": "Flight",
        "description": "Singapore Airlines SQ 345 Dubai→Singapore",
        "start": now + timedelta(days=25, hours=9),
        "end": now + timedelta(days=25, hours=14),
        "location": "DXB",
        "cost": 800,
        "confirmed": False,
        "code": "SQ345-ABC",
        "notes": "Economy",
    },
    {
        "type": "Meeting",
        "description": "Finance Summit Keynote",
        "start": now + timedelta(days=26, hours=9),
        "end": now + timedelta(days=26, hours=11),
        "location": "Marina Bay Sands",
        "cost": 0,
        "confirmed": True,
        "code": "",
        "notes": "Main stage",
    },
]
create_sample_trip(
    exec_id=2,
    purpose="APAC Finance Summit",
    stops_data=stops_marcus,
    items_data=items_marcus,
    budget=8000,
    status="final",
)

# ---- TRIP 3: Priya (Omni Consulting) - ASEAN client visits ----
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
        "description": "SQ 116 Singapore→Bangkok",
        "start": now + timedelta(days=8, hours=8),
        "end": now + timedelta(days=8, hours=10),
        "location": "SIN",
        "cost": 300,
        "confirmed": True,
        "code": "SQ116-123",
        "notes": "Economy",
    },
    {
        "type": "Hotel",
        "description": "Siam Kempinski Bangkok",
        "start": now + timedelta(days=8, hours=12),
        "end": now + timedelta(days=10, hours=12),
        "location": "Bangkok",
        "cost": 450,
        "confirmed": True,
        "code": "SK-789",
        "notes": "Executive Room",
    },
    {
        "type": "Meeting",
        "description": "Client Discovery Workshop",
        "start": now + timedelta(days=9, hours=9),
        "end": now + timedelta(days=9, hours=17),
        "location": "Bangkok Office",
        "cost": 0,
        "confirmed": True,
        "code": "",
        "notes": "Full day",
    },
]
create_sample_trip(
    exec_id=3,
    purpose="ASEAN Client Workshops",
    stops_data=stops_priya,
    items_data=items_priya,
    budget=2500,
    status="draft",
)

# ---- TRIP 4: Chidi (GreenLeaf Energy) - West Africa site visits ----
stops_chidi = [
    {
        "city": "Lagos",
        "country": "Nigeria",
        "region": "Lagos",
        "start_date": now + timedelta(days=30),
        "end_date": now + timedelta(days=32),
    },
    {
        "city": "Accra",
        "country": "Ghana",
        "region": "Greater Accra",
        "start_date": now + timedelta(days=33),
        "end_date": now + timedelta(days=35),
    },
    {
        "city": "Abidjan",
        "country": "Côte d'Ivoire",
        "region": "Abidjan",
        "start_date": now + timedelta(days=36),
        "end_date": now + timedelta(days=38),
    },
]
items_chidi = [
    {
        "type": "Flight",
        "description": "Air Peace 789 Lagos→Accra",
        "start": now + timedelta(days=33, hours=8),
        "end": now + timedelta(days=33, hours=10),
        "location": "LOS",
        "cost": 250,
        "confirmed": True,
        "code": "P4-789",
        "notes": "Economy",
    },
    {
        "type": "Hotel",
        "description": "Kempinski Accra",
        "start": now + timedelta(days=33, hours=12),
        "end": now + timedelta(days=35, hours=12),
        "location": "Accra",
        "cost": 380,
        "confirmed": True,
        "code": "KA-987",
        "notes": "Deluxe Room",
    },
    {
        "type": "Transport",
        "description": "Car Rental – Accra to Abidjan",
        "start": now + timedelta(days=35, hours=8),
        "end": now + timedelta(days=35, hours=16),
        "location": "Accra",
        "cost": 150,
        "confirmed": False,
        "code": "HZ-456",
        "notes": "SUV with driver",
    },
    {
        "type": "Meeting",
        "description": "Solar Plant Site Inspection",
        "start": now + timedelta(days=34, hours=10),
        "end": now + timedelta(days=34, hours=14),
        "location": "Accra",
        "cost": 0,
        "confirmed": True,
        "code": "",
        "notes": "Engineers present",
    },
]
create_sample_trip(
    exec_id=4,
    purpose="West Africa Solar Sites",
    stops_data=stops_chidi,
    items_data=items_chidi,
    budget=4000,
    status="approved",
)

print(
    "✅ Sample data loaded successfully! You now have 4 companies, 4 executives, and 4 sample trips with stops and items."
)
