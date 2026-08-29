from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from datetime import datetime
import io
import os
import database as db


def generate_itinerary_doc(
    executive,
    items,
    destination,
    trip_id,
    trip_budget,
    currency_symbol="$",
    currency_code="USD",
):
    """
    Generate a .docx itinerary with spending summary.
    Saves to folder AND returns BytesIO for download.
    """
    doc = Document()

    # Title
    title = doc.add_heading(f'Itinerary for {executive["name"]}', 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    sub = doc.add_paragraph(
        f'Destination: {destination}   |   Timezone: {executive["timezone"]}'
    )
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph()

    # Executive preferences summary
    doc.add_heading("Executive Profile", level=1)
    doc.add_paragraph(f"Seat: {executive.get('seat_preference', 'Not set')}")
    doc.add_paragraph(f"Hotel Loyalty: {executive.get('hotel_loyalty', 'Not set')}")
    doc.add_paragraph(f"Dietary: {executive.get('dietary_restrictions', 'None')}")
    doc.add_paragraph(f"Meal Preference: {executive.get('meal_preference', 'Not set')}")
    doc.add_paragraph()

    # Daily Agenda
    doc.add_heading("Daily Agenda", level=1)
    for item in items:
        start_str = datetime.fromisoformat(item["datetime_start"]).strftime("%H:%M")
        end_str = (
            datetime.fromisoformat(item["datetime_end"]).strftime("%H:%M")
            if item["datetime_end"]
            else "TBD"
        )
        cost_str = f"{currency_symbol}{item['cost']:.2f}" if item.get("cost") else ""
        status_icon = "✅" if item.get("is_confirmed") else "📌"

        p = doc.add_paragraph(style="List Bullet")
        p.add_run(f"{start_str} – {end_str}  |  ").bold = True
        p.add_run(f"{status_icon} {item['description']} ({item['item_type']})")
        if cost_str:
            p.add_run(f"  |  Cost: {cost_str}")
        if item.get("confirmation_code"):
            p.add_run(f"  |  Conf: {item['confirmation_code']}")

    # Conflicts
    from utils import detect_conflicts

    conflicts = detect_conflicts(items)
    if conflicts:
        doc.add_heading("⚠️ Conflicts Detected", level=1)
        for c in conflicts:
            doc.add_paragraph(c, style="List Bullet")

    # --- Spending Summary (Currency-aware) ---
    doc.add_page_break()
    doc.add_heading("💰 Trip Spending Summary", level=1)

    spending = db.get_trip_spending(trip_id)

    table = doc.add_table(rows=3, cols=2)
    table.style = "Light Grid Accent 1"
    table.cell(0, 0).text = "Category"
    table.cell(0, 1).text = "Amount"
    table.cell(1, 0).text = "Total Estimated (Quoted)"
    table.cell(1, 1).text = f"{currency_symbol}{spending['total_estimated']:.2f}"
    table.cell(2, 0).text = "Total Confirmed (Booked)"
    table.cell(2, 1).text = f"{currency_symbol}{spending['total_confirmed']:.2f}"

    doc.add_paragraph(
        f"\nTotal Trip Spend: {currency_symbol}{spending['total_all']:.2f}"
    )
    if trip_budget > 0:
        remaining = trip_budget - spending["total_all"]
        doc.add_paragraph(
            f"Budget: {currency_symbol}{trip_budget:.2f}  |  Remaining: {currency_symbol}{remaining:.2f}"
        )

    # Footer
    footer = doc.add_paragraph()
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer_run = footer.add_run(
        f'Generated on {datetime.now().strftime("%B %d, %Y at %I:%M %p")}  |  Currency: {currency_code}'
    )
    footer_run.font.size = Pt(9)
    footer_run.font.italic = True

    # Save to folder
    os.makedirs("generated_itineraries", exist_ok=True)
    filename = f"generated_itineraries/{executive['name']}_{destination}_{datetime.now().strftime('%Y%m%d_%H%M')}.docx"
    doc.save(filename)

    # Return BytesIO for download
    file_stream = io.BytesIO()
    doc.save(file_stream)
    file_stream.seek(0)
    return file_stream, filename


def generate_executive_profile_doc(profile_data, exec_id, currency_symbol="$"):
    """
    Generate a .docx executive profile with memberships.
    Returns BytesIO stream.
    """
    doc = Document()

    # Title
    title = doc.add_heading(f'Executive Profile: {profile_data["Name"]}', 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    sub = doc.add_paragraph(f'Company: {profile_data["Company"]}')
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph()

    # Table with all preferences
    table = doc.add_table(rows=10, cols=2)
    table.style = "Light Grid Accent 1"

    rows_data = [
        ("📧 Email", profile_data.get("Email", "Not set")),
        ("🕐 Timezone", profile_data.get("Timezone", "Not set")),
        ("💺 Seat Preference", profile_data.get("Seat Preference", "Not set")),
        ("✈️ Preferred Airline", profile_data.get("Preferred Airline", "Not set")),
        ("🛂 Passport Number", profile_data.get("Passport Number", "Not set")),
        ("✅ TSA PreCheck", profile_data.get("TSA PreCheck", "Not set")),
        ("🥗 Meal Preference", profile_data.get("Meal Preference", "Not set")),
        ("🏨 Hotel Loyalty", profile_data.get("Hotel Loyalty", "Not set")),
        ("✈️ Frequent Flyer #", profile_data.get("Frequent Flyer", "Not set")),
        ("🥗 Dietary Restrictions", profile_data.get("Dietary", "None")),
    ]

    for i, (label, value) in enumerate(rows_data):
        table.cell(i, 0).text = label
        table.cell(i, 1).text = value

    doc.add_paragraph()

    # --- Memberships Section ---
    memberships = db.get_memberships(exec_id)

    if memberships:
        doc.add_heading("✈️ Memberships", level=1)

        # Group by category
        airline_mems = [m for m in memberships if m["category"] == "airline"]
        hotel_mems = [m for m in memberships if m["category"] == "hotel"]
        car_mems = [m for m in memberships if m["category"] == "car"]

        if airline_mems:
            doc.add_paragraph("**Airlines:**", style="List Bullet")
            for m in airline_mems:
                doc.add_paragraph(
                    f"{m['program_name']}: {m['membership_number']}",
                    style="List Bullet 2",
                )

        if hotel_mems:
            doc.add_paragraph("**Hotels:**", style="List Bullet")
            for m in hotel_mems:
                doc.add_paragraph(
                    f"{m['program_name']}: {m['membership_number']}",
                    style="List Bullet 2",
                )

        if car_mems:
            doc.add_paragraph("**Car Rentals:**", style="List Bullet")
            for m in car_mems:
                doc.add_paragraph(
                    f"{m['program_name']}: {m['membership_number']}",
                    style="List Bullet 2",
                )

    # Company & Finance Details
    doc.add_heading("Company & Finance Details", level=1)
    doc.add_paragraph(f"Cost Center: {profile_data.get('Cost Center', 'Not set')}")
    doc.add_paragraph(f"Policy Notes: {profile_data.get('Policy Notes', 'None')}")

    # Footer
    footer = doc.add_paragraph()
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer_run = footer.add_run(
        f'Generated on {datetime.now().strftime("%B %d, %Y at %I:%M %p")}'
    )
    footer_run.font.size = Pt(9)
    footer_run.font.italic = True

    file_stream = io.BytesIO()
    doc.save(file_stream)
    file_stream.seek(0)
    return file_stream


def generate_spending_report_doc(
    filter_name, summary_data, start_date, end_date, currency_symbol="$"
):
    """Generate a standalone spending report Word document."""
    from datetime import datetime

    doc = Document()

    title = doc.add_heading("Executive Travel Spending Report", 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    sub = doc.add_paragraph(f"Executive: {filter_name}")
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph(f"Date Range: {start_date or 'All'} to {end_date or 'All'}")
    doc.add_paragraph()

    # Aggregates
    total_budget = sum(t["budget"] for t in summary_data)
    total_spent = sum(t["total_spent"] for t in summary_data)
    total_confirmed = sum(t["confirmed_spent"] for t in summary_data)
    total_estimated = sum(t["estimated_spent"] for t in summary_data)

    doc.add_heading("Aggregate Summary", level=1)
    doc.add_paragraph(f"Total Trips: {len(summary_data)}")
    doc.add_paragraph(f"Total Budget: {currency_symbol}{total_budget:,.2f}")
    doc.add_paragraph(f"Total Spent: {currency_symbol}{total_spent:,.2f}")
    doc.add_paragraph(
        f"Total Confirmed (Booked): {currency_symbol}{total_confirmed:,.2f}"
    )
    doc.add_paragraph(
        f"Total Estimated (Quoted): {currency_symbol}{total_estimated:,.2f}"
    )
    doc.add_paragraph()

    # Trip-level breakdown table
    doc.add_heading("Trip-Level Breakdown", level=1)
    table = doc.add_table(rows=1, cols=7)
    table.style = "Light Grid Accent 1"
    hdr = table.rows[0].cells
    headers = [
        "Executive",
        "Company",
        "Destination",
        "Budget",
        "Total Spent",
        "Confirmed",
        "Status",
    ]
    for i, h in enumerate(headers):
        hdr[i].text = h

    for trip in summary_data:
        row_cells = table.add_row().cells
        row_cells[0].text = trip["executive_name"]
        row_cells[1].text = trip["company_name"]
        row_cells[2].text = trip["destination"]
        row_cells[3].text = f"{currency_symbol}{trip['budget']:.2f}"
        row_cells[4].text = f"{currency_symbol}{trip['total_spent']:.2f}"
        row_cells[5].text = f"{currency_symbol}{trip['confirmed_spent']:.2f}"
        row_cells[6].text = trip["status"]

    footer = doc.add_paragraph()
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer_run = footer.add_run(
        f'Generated on {datetime.now().strftime("%B %d, %Y at %I:%M %p")}'
    )
    footer_run.font.size = Pt(9)
    footer_run.font.italic = True

    file_stream = io.BytesIO()
    doc.save(file_stream)
    file_stream.seek(0)
    return file_stream


# =========================================================
# NEW: Expense Report with Receipt Attachments
# =========================================================


def generate_expense_report_doc(
    executive,
    items,
    trip_id,
    trip_budget,
    destination,
    start_date,
    end_date,
    currency_symbol="$",
):
    """
    Generate a detailed expense report with receipts embedded.
    Items are grouped by day.
    """
    from datetime import datetime
    import os
    from docx.shared import Inches

    doc = Document()

    # --- Header ---
    title = doc.add_heading("Executive Expense Report", 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    sub = doc.add_paragraph(
        f"{executive['name']}  |  {executive.get('company_name', '')}"
    )
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph(f"Trip: {destination}  |  {start_date} to {end_date}")
    doc.add_paragraph()

    # --- Group items by day ---
    sorted_items = sorted(
        items, key=lambda x: datetime.fromisoformat(x["datetime_start"])
    )
    days = {}
    for item in sorted_items:
        date_key = datetime.fromisoformat(item["datetime_start"]).strftime("%Y-%m-%d")
        if date_key not in days:
            days[date_key] = []
        days[date_key].append(item)

    # --- Daily breakdown ---
    grand_total = 0
    confirmed_total = 0
    estimated_total = 0

    for date_key, day_items in days.items():
        doc.add_heading(
            f"📅 {datetime.strptime(date_key, '%Y-%m-%d').strftime('%A, %B %d, %Y')}",
            level=1,
        )

        # Create a table per day: Time, Description, Type, Cost, Receipt
        table = doc.add_table(rows=1, cols=5)
        table.style = "Light Grid Accent 1"
        hdr = table.rows[0].cells
        hdr[0].text = "Time"
        hdr[1].text = "Description"
        hdr[2].text = "Type"
        hdr[3].text = f"Cost ({currency_symbol})"
        hdr[4].text = "Receipt"

        day_total = 0
        for item in day_items:
            time_str = datetime.fromisoformat(item["datetime_start"]).strftime("%H:%M")
            cost = item.get("cost", 0)
            day_total += cost
            grand_total += cost
            if item.get("is_confirmed"):
                confirmed_total += cost
            else:
                estimated_total += cost

            row_cells = table.add_row().cells
            row_cells[0].text = time_str
            row_cells[1].text = (
                f"{item['description']} ({item.get('confirmation_code', '')})"
            )
            row_cells[2].text = item["item_type"]
            row_cells[3].text = f"{currency_symbol}{cost:.2f}"

            # --- Receipt column: embed image or show placeholder ---
            receipt_path = item.get("receipt_path")
            if receipt_path and os.path.exists(receipt_path):
                # Add a small thumbnail (max 1.2 inches wide)
                try:
                    # Embed image directly into the cell
                    p = row_cells[4].paragraphs[0]
                    r = p.add_run()
                    r.add_picture(receipt_path, width=Inches(1.2))
                    # Add filename below image
                    p = row_cells[4].add_paragraph()
                    p.add_run(os.path.basename(receipt_path)).font.size = Pt(6)
                except Exception:
                    row_cells[4].text = f"📎 {os.path.basename(receipt_path)}"
            else:
                row_cells[4].text = "—"

        # Day total row
        total_row = table.add_row().cells
        total_row[0].text = ""
        total_row[1].text = ""
        total_row[2].text = "**Day Total**"
        total_row[3].text = f"{currency_symbol}{day_total:.2f}"
        total_row[4].text = ""

    # --- Grand Totals ---
    doc.add_page_break()
    doc.add_heading("💰 Summary Totals", level=1)

    summary_table = doc.add_table(rows=3, cols=2)
    summary_table.style = "Light Grid Accent 1"
    summary_table.cell(0, 0).text = "Category"
    summary_table.cell(0, 1).text = "Amount"
    summary_table.cell(1, 0).text = "Total Confirmed (Booked)"
    summary_table.cell(1, 1).text = f"{currency_symbol}{confirmed_total:.2f}"
    summary_table.cell(2, 0).text = "Total Estimated (Quoted)"
    summary_table.cell(2, 1).text = f"{currency_symbol}{estimated_total:.2f}"

    doc.add_paragraph(f"\n**Grand Total: {currency_symbol}{grand_total:.2f}**")

    if trip_budget > 0:
        remaining = trip_budget - grand_total
        doc.add_paragraph(
            f"Budget: {currency_symbol}{trip_budget:.2f}  |  Remaining: {currency_symbol}{remaining:.2f}"
        )

    # Footer
    footer = doc.add_paragraph()
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer_run = footer.add_run(
        f'Generated on {datetime.now().strftime("%B %d, %Y at %I:%M %p")}'
    )
    footer_run.font.size = Pt(9)
    footer_run.font.italic = True

    # Save to folder
    os.makedirs("generated_expense_reports", exist_ok=True)
    filename = f"generated_expense_reports/{executive['name']}_{destination}_ExpenseReport_{datetime.now().strftime('%Y%m%d_%H%M')}.docx"
    doc.save(filename)

    # Return BytesIO for download
    file_stream = io.BytesIO()
    doc.save(file_stream)
    file_stream.seek(0)
    return file_stream, filename
