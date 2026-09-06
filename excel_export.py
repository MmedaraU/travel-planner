import io
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter
import database as db
from datetime import datetime


def export_profile_to_excel(exec_id, currency_symbol="$"):
    """
    Export a single executive profile to an Excel file.
    One sheet with executive details and memberships.
    """
    profile = db.get_full_executive_profile(exec_id)
    if not profile:
        return None

    wb = Workbook()
    ws = wb.active
    ws.title = "Executive Profile"

    # Title
    ws["A1"] = "Executive Profile"
    ws["A1"].font = Font(size=14, bold=True)
    ws.merge_cells("A1:D1")

    # Headers
    headers = ["Field", "Value"]
    ws.append(headers)
    for cell in ws[2]:
        cell.font = Font(bold=True)

    # Data rows
    fields = [
        ("Name", profile.get("Name", "")),
        ("Email", profile.get("Email", "")),
        ("Timezone", profile.get("Timezone", "")),
        ("Seat Preference", profile.get("Seat Preference", "")),
        ("Hotel Loyalty", profile.get("Hotel Loyalty", "")),
        ("Frequent Flyer", profile.get("Frequent Flyer", "")),
        ("Dietary", profile.get("Dietary", "")),
        ("Company", profile.get("Company", "")),
        ("Cost Center", profile.get("Cost Center", "")),
        ("Policy Notes", profile.get("Policy Notes", "")),
        ("Passport Number", profile.get("Passport Number", "")),
        ("Preferred Airline", profile.get("Preferred Airline", "")),
        ("TSA PreCheck", profile.get("TSA PreCheck", "")),
        ("Meal Preference", profile.get("Meal Preference", "")),
    ]
    for field, value in fields:
        ws.append([field, value])

    # Memberships
    ws.append([])
    ws.append(["Memberships"])
    mems = db.get_memberships(exec_id)
    if mems:
        ws.append(
            ["Category", "Program", "Number", "Tier", "Alliance", "Airport", "Notes"]
        )
        for m in mems:
            ws.append(
                [
                    m.get("category", ""),
                    m.get("program_name", ""),
                    m.get("membership_number", ""),
                    m.get("tier", ""),
                    m.get("alliance", ""),
                    m.get("airport_code", ""),
                    m.get("notes", ""),
                ]
            )
    else:
        ws.append(["No memberships recorded."])

    # Auto-fit columns
    for col in ws.columns:
        max_length = 0
        column = col[0].column_letter
        for cell in col:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = min(max_length + 2, 50)
        ws.column_dimensions[column].width = adjusted_width

    file_stream = io.BytesIO()
    wb.save(file_stream)
    file_stream.seek(0)
    return file_stream


def export_itinerary_to_excel(items, trip_data, currency_symbol, base_currency="USD"):
    """
    Export itinerary items to an Excel file.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Itinerary"

    # Title
    ws["A1"] = f"Itinerary: {trip_data.get('purpose', 'Trip')}"
    ws["A1"].font = Font(size=14, bold=True)
    ws.merge_cells("A1:F1")

    # Headers
    headers = [
        "Date/Time",
        "Type",
        "Description",
        "Location",
        "Cost (Original)",
        "Confirmed",
    ]
    ws.append(headers)
    for cell in ws[2]:
        cell.font = Font(bold=True)

    for item in items:
        start_dt = (
            datetime.fromisoformat(item["datetime_start"])
            if item.get("datetime_start")
            else None
        )
        date_str = start_dt.strftime("%Y-%m-%d %H:%M") if start_dt else ""
        ws.append(
            [
                date_str,
                item.get("item_type", ""),
                item.get("description", ""),
                item.get("location", ""),
                f"{item.get('cost', 0):.2f} {item.get('cost_currency', 'USD')}",
                "Yes" if item.get("is_confirmed", 0) else "No",
            ]
        )

    # Auto-fit columns
    for col in ws.columns:
        max_length = 0
        column = col[0].column_letter
        for cell in col:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = min(max_length + 2, 50)
        ws.column_dimensions[column].width = adjusted_width

    file_stream = io.BytesIO()
    wb.save(file_stream)
    file_stream.seek(0)
    return file_stream


def export_expense_to_excel(items, trip_data, currency_symbol, base_currency="USD"):
    """
    Export expense report to Excel.
    Similar to itinerary but with summary.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Expense Report"

    # Title
    ws["A1"] = f"Expense Report: {trip_data.get('purpose', 'Trip')}"
    ws["A1"].font = Font(size=14, bold=True)
    ws.merge_cells("A1:G1")

    # Summary
    total_spent = sum(item.get("cost", 0) for item in items)
    confirmed_spent = sum(
        item.get("cost", 0) for item in items if item.get("is_confirmed", 0)
    )
    estimated_spent = total_spent - confirmed_spent
    trip_budget = trip_data.get("budget", 0)

    summary_data = [
        ("Total Budget", f"{trip_budget:.2f} {base_currency}"),
        ("Total Spent", f"{total_spent:.2f} {base_currency}"),
        ("Confirmed (Booked)", f"{confirmed_spent:.2f} {base_currency}"),
        ("Estimated (Quoted)", f"{estimated_spent:.2f} {base_currency}"),
        ("Remaining", f"{trip_budget - total_spent:.2f} {base_currency}"),
    ]
    ws.append([])
    for label, value in summary_data:
        ws.append([label, value])
    ws.append([])

    # Details
    headers = [
        "Date/Time",
        "Type",
        "Description",
        "Location",
        "Cost (Original)",
        "Confirmed",
    ]
    ws.append(headers)
    for cell in ws[ws.max_row]:
        cell.font = Font(bold=True)

    for item in items:
        start_dt = (
            datetime.fromisoformat(item["datetime_start"])
            if item.get("datetime_start")
            else None
        )
        date_str = start_dt.strftime("%Y-%m-%d %H:%M") if start_dt else ""
        ws.append(
            [
                date_str,
                item.get("item_type", ""),
                item.get("description", ""),
                item.get("location", ""),
                f"{item.get('cost', 0):.2f} {item.get('cost_currency', 'USD')}",
                "Yes" if item.get("is_confirmed", 0) else "No",
            ]
        )

    # Auto-fit
    for col in ws.columns:
        max_length = 0
        column = col[0].column_letter
        for cell in col:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = min(max_length + 2, 50)
        ws.column_dimensions[column].width = adjusted_width

    file_stream = io.BytesIO()
    wb.save(file_stream)
    file_stream.seek(0)
    return file_stream


def export_spending_to_excel(summary_data, currency_symbol, base_currency="USD"):
    """
    Export spending summary to Excel.
    Columns: Executive, Company, Destination, Budget, Total Spent, Confirmed, Estimated, Status, Currency.
    Amounts are numeric without symbols; the Currency column indicates the trip's base currency.
    Headers indicate amounts are in base currency.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Spending Summary"

    # Title
    ws["A1"] = "Spending Summary"
    ws["A1"].font = Font(size=14, bold=True)
    ws.merge_cells("A1:I1")

    # Headers
    headers = [
        "Executive",
        "Company",
        "Destination",
        "Budget (Base Currency)",
        "Total Spent (Base Currency)",
        "Confirmed (Base Currency)",
        "Estimated (Base Currency)",
        "Status",
        "Currency",
    ]
    ws.append(headers)
    for cell in ws[2]:
        cell.font = Font(bold=True)

    # Data rows
    for trip in summary_data:
        trip_base_currency = trip.get("base_currency", base_currency)
        ws.append(
            [
                trip.get("executive_name", ""),
                trip.get("company_name", ""),
                trip.get("destination", ""),
                f"{trip.get('budget', 0):.2f}",
                f"{trip.get('total_spent', 0):.2f}",
                f"{trip.get('confirmed_spent', 0):.2f}",
                f"{trip.get('estimated_spent', 0):.2f}",
                trip.get("status", "").title(),
                trip_base_currency,
            ]
        )

    # Auto-fit columns
    for col in ws.columns:
        max_length = 0
        column = col[0].column_letter
        for cell in col:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = min(max_length + 2, 50)
        ws.column_dimensions[column].width = adjusted_width

    file_stream = io.BytesIO()
    wb.save(file_stream)
    file_stream.seek(0)
    return file_stream
