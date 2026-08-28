import database as db

db.init_db()

# Add a company
db.add_company("Acme Corp", "CC-2025-MKT", "Economy for flights under 4 hours")
db.add_company("Beta Inc", "CC-2025-SALES", "Business class allowed for transatlantic")

# Add executives
db.add_executive(
    company_id=1,
    name="Sarah Chen",
    email="sarah@acme.com",
    timezone="America/Los_Angeles",
    seat_preference="Window",
    hotel_loyalty="Marriott Bonvoy Gold",
    frequent_flyer_number="UA-123456",
    dietary_restrictions="Gluten-free",
    passport_number="US123456789",
    preferred_airline="United",
    tsa_precheck="KTN987654",
    meal_preference="Gluten-Free"
)

db.add_executive(
    company_id=2,
    name="James Okafor",
    email="james@beta.com",
    timezone="Africa/Lagos",
    seat_preference="Aisle",
    hotel_loyalty="Hilton Honors Diamond",
    frequent_flyer_number="BA-789012",
    dietary_restrictions="None",
    passport_number="NG987654321",
    preferred_airline="British Airways",
    tsa_precheck="N/A",
    meal_preference="Kosher"
)

print("✅ Sample executives and companies added successfully!")