from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
import io
from datetime import datetime
import json
import os
import base64
from jinja2 import Environment, FileSystemLoader
import pytz
import database as db
from weasyprint import HTML


def generate_executive_profile_doc(profile_data, exec_id, currency_symbol="$"):
    """
    Generate a Word document with the executive profile in a bulleted list.
    """
    doc = Document()
    doc.add_heading("Executive Profile", 0)

    doc.add_heading("Personal Information", level=1)
    fields = [
        ("Name", profile_data.get("Name") or ""),
        ("Email", profile_data.get("Email") or ""),
        ("Timezone", profile_data.get("Timezone") or ""),
        ("Seat Preference", profile_data.get("Seat Preference") or ""),
        ("Hotel Loyalty", profile_data.get("Hotel Loyalty") or ""),
        ("Frequent Flyer", profile_data.get("Frequent Flyer") or ""),
        ("Dietary", profile_data.get("Dietary") or ""),
        ("Company", profile_data.get("Company") or ""),
        ("Cost Center", profile_data.get("Cost Center") or ""),
        ("Policy Notes", profile_data.get("Policy Notes") or ""),
        ("Passport Number", profile_data.get("Passport Number") or ""),
        ("Preferred Airline", profile_data.get("Preferred Airline") or ""),
        ("TSA PreCheck", profile_data.get("TSA PreCheck") or ""),
        ("Meal Preference", profile_data.get("Meal Preference") or ""),
    ]
    for field, value in fields:
        if value:
            doc.add_paragraph(f"{field}: {value}", style="List Bullet")

    doc.add_heading("Memberships", level=1)
    mems = profile_data.get("Memberships", "")
    if mems:
        doc.add_paragraph(mems, style="List Bullet")
    else:
        doc.add_paragraph("No memberships recorded.")

    doc.add_page_break()
    doc.add_paragraph(f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    doc.add_paragraph("Executive Travel Planner")

    file_stream = io.BytesIO()
    doc.save(file_stream)
    file_stream.seek(0)
    return file_stream


def generate_itinerary_doc(
    exec_data,
    items,
    stops,
    dep_city,
    dep_region,
    dep_country,
    trip_id,
    trip_budget,
    display_symbol,
    display_currency,
    base_currency="USD",
    convert_to_base=False,
):
    """
    Generate a Word document with trip itinerary.
    Includes contacts column.
    """
    doc = Document()
    doc.add_heading(f"Itinerary: {exec_data['name']}", 0)

    # Trip overview
    doc.add_heading("Trip Overview", level=1)
    table = doc.add_table(rows=1, cols=2)
    table.style = "Table Grid"
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = "Detail"
    hdr_cells[1].text = "Value"

    dep_parts = [p for p in [dep_city, dep_region, dep_country] if p]
    departure_display = ", ".join(dep_parts) if dep_parts else "Not specified"
    rows_data = [
        ("Executive", exec_data["name"]),
        ("Departure", departure_display),
        ("Budget", f"{display_symbol}{trip_budget:.2f} {display_currency}"),
        ("Base Currency", base_currency),
    ]
    for label, value in rows_data:
        row_cells = table.add_row().cells
        row_cells[0].text = label
        row_cells[1].text = str(value)

    # Stops
    if stops:
        doc.add_heading("Stops", level=1)
        for stop in stops:
            loc = stop["city"]
            loc_parts = []
            if stop.get("region"):
                loc_parts.append(stop["region"])
            if stop.get("country"):
                loc_parts.append(stop["country"])
            if loc_parts:
                loc += f" ({', '.join(loc_parts)})"
            doc.add_paragraph(
                f"• {loc}: {stop['start_date']} to {stop['end_date']}",
                style="List Bullet",
            )

    # Itinerary items
    if items:
        doc.add_heading("Itinerary", level=1)
        table = doc.add_table(rows=1, cols=6)
        table.style = "Table Grid"
        hdr_cells = table.rows[0].cells
        headers = ["Date/Time", "Type", "Description", "Location", "Contacts", "Cost"]
        for i, h in enumerate(headers):
            hdr_cells[i].text = h
            hdr_cells[i].paragraphs[0].runs[0].bold = True

        for item in items:
            row_cells = table.add_row().cells
            start_dt = datetime.fromisoformat(item["datetime_start"])
            row_cells[0].text = start_dt.strftime("%Y-%m-%d %H:%M")
            row_cells[1].text = item.get("item_type", "")
            row_cells[2].text = item.get("description", "")
            row_cells[3].text = item.get("location", "")
            contacts = db.get_item_contacts(item["id"])
            contact_str = ", ".join([c["name"] for c in contacts]) if contacts else ""
            row_cells[4].text = contact_str
            cost = item.get("cost", 0)
            currency = item.get("cost_currency", "USD")
            row_cells[5].text = f"{cost:.2f} {currency}"

    doc.add_page_break()
    doc.add_paragraph("Generated by Executive Travel Planner")
    file_stream = io.BytesIO()
    doc.save(file_stream)
    file_stream.seek(0)
    return file_stream, f"{exec_data['name']}_itinerary.docx"


def generate_expense_report_doc(
    exec_data,
    items,
    stops,
    dep_city,
    dep_region,
    dep_country,
    trip_id,
    trip_budget,
    trip_purpose,
    display_symbol,
    base_currency="USD",
):
    """
    Generate a Word document with expense report.
    Includes contacts column.
    """
    doc = Document()
    doc.add_heading(f"Expense Report: {trip_purpose}", 0)

    # Summary
    total_spent = sum(item.get("cost", 0) for item in items)
    confirmed_spent = sum(
        item.get("cost", 0) for item in items if item.get("is_confirmed", 0)
    )
    estimated_spent = total_spent - confirmed_spent

    doc.add_heading("Summary", level=1)
    table = doc.add_table(rows=1, cols=2)
    table.style = "Table Grid"
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = "Metric"
    hdr_cells[1].text = "Value"

    rows_data = [
        ("Total Budget", f"{display_symbol}{trip_budget:.2f} {base_currency}"),
        ("Total Spent", f"{display_symbol}{total_spent:.2f} {base_currency}"),
        (
            "Confirmed (Booked)",
            f"{display_symbol}{confirmed_spent:.2f} {base_currency}",
        ),
        (
            "Estimated (Quoted)",
            f"{display_symbol}{estimated_spent:.2f} {base_currency}",
        ),
        (
            "Remaining",
            f"{display_symbol}{trip_budget - total_spent:.2f} {base_currency}",
        ),
    ]
    for label, value in rows_data:
        row_cells = table.add_row().cells
        row_cells[0].text = label
        row_cells[1].text = value

    # Itemized list
    doc.add_heading("Expense Details", level=1)
    if items:
        table = doc.add_table(rows=1, cols=7)
        table.style = "Table Grid"
        hdr_cells = table.rows[0].cells
        headers = [
            "Date/Time",
            "Type",
            "Description",
            "Location",
            "Contacts",
            "Cost",
            "Confirmed",
        ]
        for i, h in enumerate(headers):
            hdr_cells[i].text = h
            hdr_cells[i].paragraphs[0].runs[0].bold = True

        for item in items:
            row_cells = table.add_row().cells
            start_dt = datetime.fromisoformat(item["datetime_start"])
            row_cells[0].text = start_dt.strftime("%Y-%m-%d %H:%M")
            row_cells[1].text = item.get("item_type", "")
            row_cells[2].text = item.get("description", "")
            row_cells[3].text = item.get("location", "")
            contacts = db.get_item_contacts(item["id"])
            contact_str = ", ".join([c["name"] for c in contacts]) if contacts else ""
            row_cells[4].text = contact_str
            cost = item.get("cost", 0)
            currency = item.get("cost_currency", "USD")
            row_cells[5].text = f"{cost:.2f} {currency}"
            row_cells[6].text = "✅" if item.get("is_confirmed", 0) else "❌"
    else:
        doc.add_paragraph("No expenses recorded.")

    doc.add_page_break()
    doc.add_paragraph("Generated by Executive Travel Planner")
    file_stream = io.BytesIO()
    doc.save(file_stream)
    file_stream.seek(0)
    return file_stream, f"{exec_data['name']}_ExpenseReport.docx"


def generate_spending_report_doc(
    filter_label,
    summary_data,
    start_filter,
    end_filter,
    currency_symbol,
    base_currency="USD",
):
    """
    Generate a Word document with spending summary report.
    """
    doc = Document()
    doc.add_heading("Spending Report", 0)

    doc.add_heading("Filters", level=1)
    doc.add_paragraph(f"Executive: {filter_label}")
    if start_filter:
        doc.add_paragraph(f"Start Date: {start_filter}")
    if end_filter:
        doc.add_paragraph(f"End Date: {end_filter}")
    doc.add_paragraph(f"Base Currency (for numeric columns): {base_currency}")

    doc.add_heading("Trip Breakdown", level=1)
    if summary_data:
        table = doc.add_table(rows=1, cols=7)
        table.style = "Table Grid"
        hdr_cells = table.rows[0].cells
        headers = [
            "Executive",
            "Destination",
            "Budget",
            "Total Spent",
            "Confirmed",
            "Status",
            "Currency",
        ]
        for i, h in enumerate(headers):
            hdr_cells[i].text = h
            hdr_cells[i].paragraphs[0].runs[0].bold = True

        for trip in summary_data:
            row_cells = table.add_row().cells
            row_cells[0].text = trip.get("executive_name", "")
            row_cells[1].text = trip.get("destination", "")
            row_cells[2].text = (
                f"{trip.get('budget', 0):.2f} {trip.get('base_currency', 'USD')}"
            )
            row_cells[3].text = (
                f"{trip.get('total_spent', 0):.2f} {trip.get('base_currency', 'USD')}"
            )
            row_cells[4].text = (
                f"{trip.get('confirmed_spent', 0):.2f} {trip.get('base_currency', 'USD')}"
            )
            row_cells[5].text = trip.get("status", "").title()
            row_cells[6].text = trip.get("base_currency", "USD")
    else:
        doc.add_paragraph("No trips found.")

    doc.add_page_break()
    doc.add_paragraph("Generated by Executive Travel Planner")
    file_stream = io.BytesIO()
    doc.save(file_stream)
    file_stream.seek(0)
    return file_stream


def generate_all_executive_profiles_doc(profiles):
    """
    Generate a Word document with a list of all executive profiles.
    """
    doc = Document()
    doc.add_heading("All Executive Profiles", 0)

    for p in profiles:
        name = p.get("Name", "Unknown Executive")
        doc.add_heading(name, level=1)

        fields = [
            ("Email", p.get("Email")),
            ("Company", p.get("Company")),
            ("Timezone", p.get("Timezone")),
            ("Seat Preference", p.get("Seat Preference")),
            ("Passport Number", p.get("Passport Number")),
            ("Memberships", p.get("Memberships")),
            ("Meal Preference", p.get("Meal Preference")),
        ]
        for label, value in fields:
            if value:
                doc.add_paragraph(f"{label}: {value}", style="List Bullet")

        doc.add_paragraph()

    doc.add_page_break()
    doc.add_paragraph("Generated by Executive Travel Planner")
    file_stream = io.BytesIO()
    doc.save(file_stream)
    file_stream.seek(0)
    return file_stream


# ---- Travel Pack HTML ----
def generate_travel_pack_html(trip_id, exec_timezone, display_mode="Home"):
    """
    Generate a self-contained HTML travel pack.
    Includes contacts per item, delegation, venue, and receipts.
    """
    trip = db.get_trip(trip_id)
    if not trip:
        return None
    executive = db.get_executive_profile(trip["exec_id"])
    if not executive:
        executive = {}

    trip_venues = db.get_venues_for_trip(trip_id)
    stops = db.get_trip_stops(trip_id)
    items = db.get_items_for_trip(trip_id)
    contacts = db.get_trip_contacts(trip_id)
    trip_venues = db.get_venues_for_trip(trip_id)
    memberships = db.get_memberships(trip["exec_id"])

    # ---- Delegation: only members assigned to items on this trip ----
    company_id_for_delegation = executive.get("company_id") if executive else None
    delegation = []
    if company_id_for_delegation:
        assigned_ids = set()
        for item in items:
            for m in db.get_item_delegation_members(item["id"]):
                assigned_ids.add(m["id"])
        if assigned_ids:
            all_members = db.get_delegation_members(
                company_id_for_delegation, active_only=True
            )
            delegation = [m for m in all_members if m["id"] in assigned_ids]

    # ---- Budget totals ----
    total_spent = sum(i.get("cost", 0) for i in items)
    confirmed_spent = sum(i.get("cost", 0) for i in items if i.get("is_confirmed", 0))
    estimated_spent = total_spent - confirmed_spent

    # ---- Format items with timezone + participants + contacts ----
    formatted_items = []
    receipts = []
    fallback_tz = pytz.timezone(exec_timezone)

    for item in items:
        item_tz_str = item.get("timezone") or exec_timezone
        try:
            item_tz = pytz.timezone(item_tz_str)
        except Exception:
            item_tz = fallback_tz

        dt_naive = datetime.fromisoformat(item["datetime_start"])
        dt_aware = item_tz.localize(dt_naive)

        if display_mode == "Home":
            display_tz = fallback_tz
        else:
            display_tz = item_tz

        dt_display = dt_aware.astimezone(display_tz)
        formatted_time = dt_display.strftime("%d-%m-%Y %H:%M %Z")

        # Delegation members assigned to this item
        delegation_members = db.get_item_delegation_members(item["id"])
        delegation_names = (
            [m["name"] for m in delegation_members] if delegation_members else []
        )

        # Contacts assigned to this item
        item_contacts = db.get_item_contacts(item["id"])
        contact_names = [c["name"] for c in item_contacts] if item_contacts else []

        # ---- Venue lookup for this item ----
        venue_name_for_item = None
        if item.get("venue_id"):
            v = db.get_venue(item["venue_id"])
            if v:
                venue_name_for_item = v["name"]

        item_dict = {
            "id": item["id"],
            "item_type": item["item_type"],
            "description": item["description"],
            "location": item.get("location", ""),
            "cost": item.get("cost", 0),
            "cost_currency": item.get("cost_currency", "USD"),
            "confirmation_code": item.get("confirmation_code", ""),
            "notes": item.get("notes", ""),
            "is_confirmed": item.get("is_confirmed", 0),
            "formatted_time": formatted_time,
            "participants": delegation_names,  # used for Agenda attendees
            "contacts": contact_names,  # for future use
            "venue_id": item.get("venue_id"),
            "venue_name": venue_name_for_item,
            "venue_id": item.get("venue_id"),
        }
        formatted_items.append(item_dict)

        # Collect receipts
        receipt_path = item.get("receipt_path")
        if receipt_path and os.path.exists(receipt_path):
            with open(receipt_path, "rb") as f:
                image_data = f.read()
                b64 = base64.b64encode(image_data).decode("utf-8")
                ext = os.path.splitext(receipt_path)[1].lower()
                mime = (
                    "image/png"
                    if ext == ".png"
                    else "image/jpeg" if ext in [".jpg", ".jpeg"] else "application/pdf"
                )
                data_uri = f"data:{mime};base64,{b64}"
                receipts.append(
                    {"description": item["description"], "data_uri": data_uri}
                )

    # ---- Build context for Jinja2 ----
    context = {
        "trip": trip,
        "executive": executive,
        "delegation": delegation,  # <-- ADDED (fixes missing Delegation section)
        "stops": stops,
        "items": formatted_items,
        "contacts": contacts,
        "memberships": memberships,
        "total_spent": total_spent,
        "confirmed_spent": confirmed_spent,
        "estimated_spent": estimated_spent,
        "receipts": receipts,
        "trip_venues": trip_venues,
        "now": datetime.now(),
    }

    env = Environment(loader=FileSystemLoader("templates"))
    template = env.get_template("travel_pack.html")
    html = template.render(**context)
    return html


# ---- Company Profile HTML ----
def generate_company_profile_html(company_id):
    """Generate a self‑contained HTML company profile."""
    company = db.get_company(company_id)
    if not company:
        return None
    executives = db.get_executives_by_company(company_id)
    contacts = db.get_contacts(company_id, active_only=True)
    delegation = db.get_delegation_members(company_id, active_only=True)

    context = {
        "company": company,
        "executives": executives,
        "contacts": contacts,
        "participants": delegation,  # template uses 'participants'
        "now": datetime.now(),
    }
    env = Environment(loader=FileSystemLoader("templates"))
    template = env.get_template("company_profile.html")
    return template.render(**context)


# ---- Company Profile Word ----
def generate_company_profile_docx(company_id):
    """Generate a Word document with company profile."""
    company = db.get_company(company_id)
    if not company:
        return None
    executives = db.get_executives_by_company(company_id)
    contacts = db.get_contacts(company_id, active_only=True)
    delegation = db.get_delegation_members(company_id, active_only=True)

    doc = Document()
    doc.add_heading(f"Company Profile: {company['name']}", 0)
    doc.add_paragraph(f"Cost Center: {company.get('default_cost_center') or 'N/A'}")
    if company.get("policy_notes"):
        doc.add_paragraph(f"Policy Notes: {company['policy_notes']}")

    doc.add_heading("Executives", level=1)
    if executives:
        table = doc.add_table(rows=1, cols=5)
        table.style = "Table Grid"
        hdr = table.rows[0].cells
        hdr[0].text = "Name"
        hdr[1].text = "Email"
        hdr[2].text = "Timezone"
        hdr[3].text = "Seat Preference"
        hdr[4].text = "Meal Preference"
        for e in executives:
            row = table.add_row().cells
            row[0].text = e.get("name", "")
            row[1].text = e.get("email", "")
            row[2].text = e.get("timezone", "")
            row[3].text = e.get("seat_preference", "")
            row[4].text = e.get("meal_preference", "")
    else:
        doc.add_paragraph("No executives assigned.")

    doc.add_heading("Contacts", level=1)
    if contacts:
        for c in contacts:
            p = doc.add_paragraph()
            p.add_run(f"{c['name']}").bold = True
            if c.get("role"):
                p.add_run(f" ({c['role']})")
            if c.get("type"):
                p.add_run(f" [{c['type']}]")
            location = c.get("city", "")
            if c.get("country"):
                location += f", {c['country']}" if location else c["country"]
            p.add_run(f"\n📞 {c.get('phone', '')}  ✉️ {c.get('email', '')}")
            if location:
                p.add_run(f"  🌍 {location}")
            if c.get("tags"):
                p.add_run(f"\n🏷️ {c['tags']}")
    else:
        doc.add_paragraph("No contacts.")

    doc.add_heading("Delegation Members", level=1)
    if delegation:
        table = doc.add_table(rows=1, cols=4)
        table.style = "Table Grid"
        hdr = table.rows[0].cells
        hdr[0].text = "Name"
        hdr[1].text = "Email"
        hdr[2].text = "Role"
        hdr[3].text = "Phone"
        for m in delegation:
            row = table.add_row().cells
            row[0].text = m.get("name", "")
            row[1].text = m.get("email", "")
            row[2].text = m.get("role", "")
            row[3].text = m.get("phone", "")
    else:
        doc.add_paragraph("No delegation members.")

    doc.add_paragraph(f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    file_stream = io.BytesIO()
    doc.save(file_stream)
    file_stream.seek(0)
    return file_stream


def generate_travel_pack_pdf(trip_id, exec_timezone, display_mode="Home"):
    """
    Generate a PDF version of the travel pack using WeasyPrint.
    Returns a BytesIO stream.
    """
    html_str = generate_travel_pack_html(trip_id, exec_timezone, display_mode)
    if not html_str:
        return None
    pdf_bytes = HTML(string=html_str).write_pdf()
    return io.BytesIO(pdf_bytes)


def generate_travel_pack_docx(trip_id, exec_timezone, display_mode="Home"):
    """
    Generate a Word (.docx) version of the travel pack.
    Mirrors the HTML travel pack structure with the same sections.
    """
    trip = db.get_trip(trip_id)
    if not trip:
        return None

    executive = db.get_executive_profile(trip["exec_id"])
    if not executive:
        executive = {}

    venue = db.get_venue(trip_id)
    stops = db.get_trip_stops(trip_id)
    items = db.get_items_for_trip(trip_id)
    contacts = db.get_trip_contacts(trip_id)
    trip_venues = db.get_venues_for_trip(trip_id)

    # ---- Delegation: only members assigned to items on this trip ----
    company_id_for_delegation = executive.get("company_id") if executive else None
    delegation = []
    if company_id_for_delegation:
        assigned_ids = set()
        for item in items:
            for m in db.get_item_delegation_members(item["id"]):
                assigned_ids.add(m["id"])
        if assigned_ids:
            all_members = db.get_delegation_members(
                company_id_for_delegation, active_only=True
            )
            delegation = [m for m in all_members if m["id"] in assigned_ids]

    # ---- Budget totals ----
    total_spent = sum(i.get("cost", 0) for i in items)
    confirmed_spent = sum(i.get("cost", 0) for i in items if i.get("is_confirmed", 0))
    estimated_spent = total_spent - confirmed_spent

    # =========================================================
    # BUILD THE DOCUMENT
    # =========================================================
    doc = Document()

    # ---- Cover / Trip Overview ----
    doc.add_heading(trip.get("purpose", "Travel Pack"), 0)

    doc.add_heading("Trip Overview", level=1)
    dep_parts = [
        p for p in [
            trip.get("departure_city"),
            trip.get("departure_region"),
            trip.get("departure_country"),
        ] if p
    ]
    departure_display = ", ".join(dep_parts) if dep_parts else "Not specified"
    dest_display = stops[0]["city"] if stops else "N/A"

    overview_table = doc.add_table(rows=1, cols=2)
    overview_table.style = "Table Grid"
    hdr = overview_table.rows[0].cells
    hdr[0].text = "Detail"
    hdr[1].text = "Value"

    overview_rows = [
        ("From", departure_display),
        ("To", dest_display),
        ("Dates", f"{trip['start_date'][:10]} – {trip['end_date'][:10]}"),
        ("Status", trip.get("status", "").title()),
        ("Budget", f"{trip.get('budget', 0):.2f} {trip.get('base_currency', 'USD')}"),
        ("Total Spent", f"{total_spent:.2f} {trip.get('base_currency', 'USD')}"),
        ("Confirmed", f"{confirmed_spent:.2f} {trip.get('base_currency', 'USD')}"),
        ("Estimated", f"{estimated_spent:.2f} {trip.get('base_currency', 'USD')}"),
    ]
    for label, value in overview_rows:
        row = overview_table.add_row().cells
        row[0].text = label
        row[1].text = str(value)

    # ---- Delegation ----
    if delegation:
        doc.add_heading("Delegation", level=1)
        table = doc.add_table(rows=1, cols=4)
        table.style = "Table Grid"
        hdr = table.rows[0].cells
        hdr[0].text = "Name"
        hdr[1].text = "Role"
        hdr[2].text = "Email"
        hdr[3].text = "Phone"
        for member in delegation:
            row = table.add_row().cells
            row[0].text = member.get("name", "")
            row[1].text = member.get("role", "")
            row[2].text = member.get("email", "")
            row[3].text = member.get("phone", "")

    # ---- Route (Stops) ----
    if stops:
        doc.add_heading("Route", level=1)
        for stop in stops:
            loc = stop["city"]
            loc_parts = []
            if stop.get("region"):
                loc_parts.append(stop["region"])
            if stop.get("country"):
                loc_parts.append(stop["country"])
            if loc_parts:
                loc += f" ({', '.join(loc_parts)})"
            doc.add_paragraph(
                f"{loc}: {stop['start_date'][:10]} to {stop['end_date'][:10]}",
                style="List Bullet",
            )

    # ---- Itinerary (Flights & Transport only) ----
    itinerary_items = [
        item for item in items if item["item_type"] in ["Flight", "Transport"]
    ]
    if itinerary_items:
        doc.add_heading("Itinerary", level=1)
        table = doc.add_table(rows=1, cols=6)
        table.style = "Table Grid"
        hdr = table.rows[0].cells
        headers = ["Date/Time", "Type", "Description", "Location", "Confirmation", "Cost"]
        for i, h in enumerate(headers):
            hdr[i].text = h
            hdr[i].paragraphs[0].runs[0].bold = True

        for item in itinerary_items:
            row = table.add_row().cells
            row[0].text = item["datetime_start"][:16]
            row[1].text = item["item_type"]
            row[2].text = item["description"]
            row[3].text = item.get("location", "")
            row[4].text = item.get("confirmation_code", "") or "—"
            row[5].text = (
                f"{item.get('cost', 0):.2f} {item.get('cost_currency', 'USD')}"
            )

    # ---- Hotels (separate section) ----
    hotels = [item for item in items if item["item_type"] == "Hotel"]
    if hotels:
        doc.add_heading("Hotels", level=1)
        table = doc.add_table(rows=1, cols=5)
        table.style = "Table Grid"
        hdr = table.rows[0].cells
        headers = ["Check-in / Check-out", "Hotel", "Location", "Confirmation", "Cost"]
        for i, h in enumerate(headers):
            hdr[i].text = h
            hdr[i].paragraphs[0].runs[0].bold = True

        for hotel in hotels:
            row = table.add_row().cells
            end_str = hotel["datetime_end"][:16] if hotel.get("datetime_end") else ""
            row[0].text = f"{hotel['datetime_start'][:16]} – {end_str}" if end_str else hotel["datetime_start"][:16]
            row[1].text = hotel["description"]
            row[2].text = hotel.get("location", "")
            row[3].text = hotel.get("confirmation_code", "") or "—"
            row[4].text = (
                f"{hotel.get('cost', 0):.2f} {hotel.get('cost_currency', 'USD')}"
            )

    # ---- Agenda (Meetings, Conferences, Dinners, Site Visits) ----
    agenda_items = [
        item
        for item in items
        if item["item_type"] in ["Meeting", "Conference", "Dinner", "Site Visit"]
    ]
    if agenda_items:
        doc.add_heading("Agenda", level=1)
        table = doc.add_table(rows=1, cols=5)
        table.style = "Table Grid"
        hdr = table.rows[0].cells
        headers = ["Date/Time", "Type", "Description", "Location", "Attendees"]
        for i, h in enumerate(headers):
            hdr[i].text = h
            hdr[i].paragraphs[0].runs[0].bold = True

        for item in agenda_items:
            row = table.add_row().cells
            row[0].text = item["datetime_start"][:16]
            row[1].text = item["item_type"]
            row[2].text = item["description"]
            row[3].text = item.get("location", "")
            # Venue name
            venue_name = ""
            if item.get("venue_id"):
                v = db.get_venue(item["venue_id"])
                if v:
                    venue_name = v["name"]
            row[4].text = venue_name or "—"
            attendees = db.get_item_delegation_members(item["id"])
            attendee_names = ", ".join([a["name"] for a in attendees])
            row[4].text = attendee_names or "—"

    # ---- Venues (unique venues referenced by this trip's items) ----
    if trip_venues:
        doc.add_heading("Venues", level=1)
        for v in trip_venues:
            p = doc.add_paragraph()
            p.add_run(v["name"]).bold = True
            if v.get("address"):
                p.add_run(f"\nAddress: {v['address']}")
            location_parts = [x for x in [v.get("city"), v.get("country")] if x]
            if location_parts:
                p.add_run(f"\nLocation: {', '.join(location_parts)}")
            if v.get("wifi_ssid") or v.get("wifi_password"):
                p.add_run(
                    f"\nWiFi: {v.get('wifi_ssid', '')} / {v.get('wifi_password', '')}"
                )
            if v.get("badge_info"):
                p.add_run(f"\nBadge Info: {v['badge_info']}")
            if v.get("dress_code_notes"):
                p.add_run(f"\nDress Code: {v['dress_code_notes']}")
            if v.get("notes"):
                p.add_run(f"\nNotes: {v['notes']}")
            doc.add_paragraph()  # spacing


    # ---- Local Support Contacts ----
    if contacts:
        doc.add_heading("Local Support", level=1)
        table = doc.add_table(rows=1, cols=5)
        table.style = "Table Grid"
        hdr = table.rows[0].cells
        headers = ["Name", "Role", "Phone", "Email", "Country"]
        for i, h in enumerate(headers):
            hdr[i].text = h
            hdr[i].paragraphs[0].runs[0].bold = True

        for c in contacts:
            row = table.add_row().cells
            row[0].text = c.get("name", "")
            row[1].text = c.get("role", "")
            row[2].text = c.get("phone", "")
            row[3].text = c.get("email", "")
            row[4].text = c.get("country", "")

    # ---- Receipts ----
    receipt_items = [
        item for item in items
        if item.get("receipt_path") and os.path.exists(item["receipt_path"])
    ]
    if receipt_items:
        doc.add_heading("Receipts", level=1)
        for item in receipt_items:
            try:
                doc.add_picture(item["receipt_path"], width=Inches(2))
                doc.add_paragraph(item["description"])
                doc.add_paragraph()  # spacing
            except Exception:
                pass

    # ---- Footer ----
    doc.add_page_break()
    doc.add_paragraph(
        f"Generated by Executive Travel Planner on {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )

    file_stream = io.BytesIO()
    doc.save(file_stream)
    file_stream.seek(0)
    return file_stream
