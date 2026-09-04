import streamlit as st
import database as db
import doc_generator
import utils
from datetime import datetime
import csv
import io
import pytz
import os
import pycountry
from excel_export import (
    export_profile_to_excel,
    export_itinerary_to_excel,
    export_expense_to_excel,
    export_spending_to_excel,
)
from currency import get_snapshot_rate, convert, get_exchange_rates, get_currency_symbol


# --- Safe Helper ---
def safe_index(options, value, default="No Preference"):
    if value is None:
        value = default
    try:
        return options.index(value)
    except ValueError:
        return options.index(default)


# --- Timezone Dropdown Helper ---
def get_timezone_dropdown_options():
    display_names = []
    tz_map = {}
    for tz in sorted(pytz.common_timezones):
        try:
            now = datetime.now(pytz.timezone(tz))
            abbr = now.strftime("%Z")
            if not abbr:
                abbr = now.strftime("%z")
            display = f"{tz} ({abbr})"
        except Exception:
            display = tz
        display_names.append(display)
        tz_map[display] = tz
    return display_names, tz_map


# --- Date Format Helper ---
def format_date_display(date_str):
    if not date_str:
        return ""
    try:
        dt = datetime.fromisoformat(date_str)
        return dt.strftime("%d-%m-%Y")
    except:
        return date_str


def format_datetime_display(dt_str):
    if not dt_str:
        return ""
    try:
        dt = datetime.fromisoformat(dt_str)
        return dt.strftime("%d-%m-%Y %H:%M")
    except:
        return dt_str


# --- Page Config ---
st.set_page_config(page_title="Executive Travel Planner", layout="wide")

# --- Custom CSS for Light Blue Focus ---
st.markdown(
    """
<style>
    .stTextInput input:focus, .stNumberInput input:focus, .stDateInput input:focus {
        border-color: #87CEEB !important;
        box-shadow: 0 0 0 0.2rem rgba(135, 206, 235, 0.4) !important;
    }
    .stTextInput input:hover, .stNumberInput input:hover, .stDateInput input:hover {
        border-color: #87CEEB !important;
    }
    .stTextArea textarea:focus {
        border-color: #87CEEB !important;
        box-shadow: 0 0 0 0.2rem rgba(135, 206, 235, 0.4) !important;
    }
    .stTextArea textarea:hover {
        border-color: #87CEEB !important;
    }
    .stSelectbox div[data-baseweb="select"]:hover {
        border-color: #87CEEB !important;
    }
    .stSelectbox div[data-baseweb="select"]:focus-within {
        border-color: #87CEEB !important;
        box-shadow: 0 0 0 0.2rem rgba(135, 206, 235, 0.4) !important;
    }
</style>
""",
    unsafe_allow_html=True,
)

# --- Initialize upload counter for receipts ---
if "upload_counter" not in st.session_state:
    st.session_state.upload_counter = 0

st.title("✈️ Executive Travel Planner")

# --- Init DB ---
db.init_db()

# --- SIDEBAR: EXECUTIVE SELECTION ---
st.sidebar.header("👤 Select Executive")

# --- SIDEBAR: Manage Executives & Companies ---
with st.sidebar.expander("⚙️ Manage Executives & Companies"):
    # Add Company
    st.subheader("🏢 Add Company")
    with st.form("add_company_form", clear_on_submit=True):
        comp_name = st.text_input("Company Name", key="comp_name")
        comp_cc = st.text_input("Default Cost Center (optional)", key="comp_cc")
        comp_policy = st.text_area("Policy Notes (optional)", key="comp_policy")
        if st.form_submit_button("Add Company"):
            if comp_name:
                db.add_company(comp_name, comp_cc, comp_policy)
                st.success(f"Company '{comp_name}' added!")
                st.rerun()
            else:
                st.warning("Company Name is required.")
    st.divider()

    # Add Executive
    st.subheader("👤 Add Executive")
    companies = db.get_all_companies()
    company_options = {name: id for id, name in companies}
    tz_display_names, tz_map = get_timezone_dropdown_options()
    default_display = next(
        (n for n in tz_display_names if "America/New_York" in n), tz_display_names[0]
    )

    with st.form("add_exec_form", clear_on_submit=True):
        exec_name = st.text_input("Full Name*", key="exec_name")
        exec_email = st.text_input("Email", key="exec_email")
        if companies:
            sel_company = st.selectbox(
                "Company*", list(company_options.keys()), key="exec_company"
            )
            sel_company_id = company_options[sel_company]
        else:
            st.warning("Add a company first.")
            sel_company_id = None

        sel_tz = st.selectbox(
            "Timezone",
            tz_display_names,
            index=tz_display_names.index(default_display),
            key="exec_tz",
        )
        exec_tz = tz_map[sel_tz]
        exec_seat = st.selectbox(
            "Seat Preference",
            ["No Preference", "Aisle", "Window", "Middle"],
            key="exec_seat",
        )
        exec_hotel = st.text_input("Hotel Loyalty Program", key="exec_hotel")
        exec_ff = st.text_input("Frequent Flyer Number", key="exec_ff")
        exec_diet = st.text_input("Dietary Restrictions", key="exec_diet")
        exec_passport = st.text_input("Passport Number", key="exec_passport")
        exec_airline = st.text_input("Preferred Airline", key="exec_airline")
        exec_tsa = st.text_input("TSA PreCheck", key="exec_tsa")
        exec_meal = st.selectbox(
            "Meal Preference",
            ["No Preference", "Vegetarian", "Vegan", "Kosher", "Halal", "Gluten-Free"],
            key="exec_meal",
        )

        if st.form_submit_button("Add Executive"):
            if exec_name and sel_company_id:
                db.add_executive(
                    sel_company_id,
                    exec_name,
                    exec_email,
                    exec_tz,
                    exec_seat if exec_seat != "No Preference" else "",
                    exec_hotel,
                    exec_ff,
                    exec_diet,
                    exec_passport,
                    exec_airline,
                    exec_tsa,
                    exec_meal if exec_meal != "No Preference" else "",
                )
                st.success(f"Executive '{exec_name}' added!")
                st.rerun()
            else:
                st.warning("Name and Company are required.")

# --- Sidebar: Manage Categories ---
st.sidebar.divider()
with st.sidebar.expander("🏷️ Manage Categories"):
    st.caption("Custom types for itinerary items (e.g., 'Car Rental').")
    with st.form("add_cat_form", clear_on_submit=True):
        new_cat = st.text_input("New Category Name", key="new_cat")
        if st.form_submit_button("➕ Add Category"):
            if new_cat:
                result = db.add_category(new_cat.strip())
                if result:
                    st.success(f"Added '{new_cat}'")
                    st.rerun()
                else:
                    st.warning("Category already exists.")

    existing_cats = db.get_all_categories()
    if existing_cats:
        st.write("**Existing:**")
        for cat_id, cat_name in existing_cats:
            col1, col2 = st.columns([4, 1])
            col1.write(f"- {cat_name}")
            if col2.button("❌", key=f"del_cat_{cat_id}"):
                db.delete_category(cat_id)
                st.rerun()

# --- Load Executives ---
executives = db.get_all_executives()
if not executives:
    st.sidebar.warning("No executives found.")
    st.stop()

exec_options = {f"{name} (ID: {id})": id for id, name, _ in executives}
selected_label = st.sidebar.selectbox("Choose Executive", list(exec_options.keys()))
exec_id = exec_options[selected_label]
profile = db.get_executive_profile(exec_id)

# --- Profile Display ---
if profile:
    st.sidebar.subheader("📋 Profile")
    st.sidebar.write(f"**Company:** {profile.get('company_name', 'N/A')}")
    st.sidebar.write(f"**Timezone:** {profile.get('timezone', 'N/A')}")
    st.sidebar.write(f"**Seat:** {profile.get('seat_preference', 'N/A')}")
    memberships = db.get_memberships(exec_id)
    if memberships:
        st.sidebar.write("**✈️ Memberships:**")
        for m in memberships:
            emoji = (
                "✈️"
                if m["category"] == "airline"
                else "🏨" if m["category"] == "hotel" else "🚗"
            )
            st.sidebar.write(f"  {emoji} {m['program_name']}: {m['membership_number']}")

    if st.sidebar.button("✏️ Edit Executive"):
        st.session_state["editing_exec"] = True

    # --- DELETE EXECUTIVE BUTTON ---
    st.sidebar.divider()
    if st.sidebar.button("🗑️ Delete Executive", type="primary"):
        st.session_state["show_delete_exec_confirm"] = True

# --- Sidebar: Export Profile (CSV, Word, Excel) ---
st.sidebar.divider()
st.sidebar.subheader("📤 Export Profile")
col_csv, col_doc, col_excel = st.sidebar.columns(3)

with col_csv:
    if st.button("📊 CSV"):
        profile_data = db.get_full_executive_profile(exec_id)
        if profile_data:
            mems = db.get_memberships(exec_id)
            mem_str = "; ".join(
                [f"{m['program_name']}: {m['membership_number']}" for m in mems]
            )
            profile_data["Memberships"] = mem_str
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=profile_data.keys())
            writer.writeheader()
            writer.writerow(profile_data)
            st.download_button(
                "⬇️ Download",
                data=output.getvalue(),
                file_name=f"{profile_data['Name']}_profile.csv",
                mime="text/csv",
                key="csv_download",
            )

with col_doc:
    if st.button("📄 Word"):
        profile_data = db.get_full_executive_profile(exec_id)
        if profile_data:
            doc_stream = doc_generator.generate_executive_profile_doc(
                profile_data, exec_id, get_currency_symbol("USD")  # default symbol
            )
            st.download_button(
                "⬇️ Download",
                data=doc_stream,
                file_name=f"{profile_data['Name']}_Profile.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml",
                key="docx_download",
            )

with col_excel:
    if st.button("📊 Excel"):
        profile_data = db.get_full_executive_profile(exec_id)
        if profile_data:
            excel_stream = export_profile_to_excel(
                exec_id, get_currency_symbol("USD")
            )
            if excel_stream:
                st.download_button(
                    label="⬇️ Download",
                    data=excel_stream,
                    file_name=f"{profile_data['Name']}_Profile.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="excel_download",
                )

# =========================================================
# MAIN AREA: TRIP SETUP (with per‑trip currencies)
# =========================================================
st.header("📅 Trip Setup")

# --- Check if we're editing an existing trip ---
is_editing = "current_trip_id" in st.session_state
trip_status = None
is_draft = False
trip_data = None
trip_id = None

if is_editing:
    trip_id = st.session_state["current_trip_id"]
    trip_data = db.get_trip(trip_id)
    if trip_data:
        trip_status = trip_data.get("status", "draft")
        is_draft = trip_status == "draft"
        # Pre-populate the session state stops from the database if not already there
        if "trip_stops" not in st.session_state or not st.session_state["trip_stops"]:
            st.session_state["trip_stops"] = db.get_trip_stops(trip_id)
    else:
        # If trip doesn't exist, clear the session state
        st.session_state.pop("current_trip_id", None)
        is_editing = False

# --- If not editing, make sure trip_stops is initialized ---
if not is_editing and "trip_stops" not in st.session_state:
    st.session_state["trip_stops"] = []

# --- CRITICAL FIX: When creating a new trip, the form should be editable ---
if not is_editing:
    is_draft = True  # <-- This enables the form for new trip creation

# --- Trip Name / Purpose ---
trip_purpose = st.text_input(
    "Trip Name / Purpose (e.g., 'Q3 Sales Tour')",
    value=trip_data.get("purpose", "") if is_editing and trip_data else "",
    disabled=not is_draft,
)

# --- Departure ---
st.subheader("📍 Departure City / Home Base")
col_dep_city, col_dep_region = st.columns(2)
with col_dep_city:
    departure_city = st.text_input(
        "City*",
        value=trip_data.get("departure_city", "") if is_editing and trip_data else "",
        disabled=not is_draft,
        key="departure_city",
        help="Where is the executive departing from?",
    )
with col_dep_region:
    departure_region = st.text_input(
        "Region / State (optional)",
        value=trip_data.get("departure_region", "") if is_editing and trip_data else "",
        disabled=not is_draft,
        key="departure_region",
    )

country_list = sorted([c.name for c in pycountry.countries])
departure_country = st.selectbox(
    "Country (optional)",
    options=[""] + country_list,
    index=(
        (["", *country_list].index(trip_data.get("departure_country", "")))
        if is_editing and trip_data and trip_data.get("departure_country")
        else 0
    ),
    disabled=not is_draft,
    key="departure_country_select",
)

# --- Stops ---
st.subheader("📍 Trip Stops (Destinations)")

# Display existing stops
if st.session_state["trip_stops"]:
    st.write("**Stops in this trip:**")
    for idx, stop in enumerate(st.session_state["trip_stops"]):
        col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 2, 1])
        with col1:
            st.write(f"**{idx + 1}.** {stop['city']}")
        with col2:
            loc_parts = []
            if stop.get("region"):
                loc_parts.append(stop["region"])
            if stop.get("country"):
                loc_parts.append(stop["country"])
            st.write(", ".join(loc_parts) if loc_parts else "")
        with col3:
            st.write(
                f"{format_date_display(stop['start_date'])} → {format_date_display(stop['end_date'])}"
            )
        with col4:
            st.write(stop.get("notes", "")[:30])
        with col5:
            if st.button("🗑️", key=f"del_stop_{idx}"):
                st.session_state["trip_stops"].pop(idx)
                st.rerun()

# Add stop form – disabled for non-drafts
with st.expander("➕ Add Destination Stop"):
    col_city, col_country = st.columns(2)
    with col_city:
        new_city = st.text_input("City*", key="new_stop_city", disabled=not is_draft)
    with col_country:
        new_country = st.selectbox(
            "Country (optional)",
            options=[""] + country_list,
            index=0,
            key="new_stop_country",
            disabled=not is_draft,
        )
    col_region, col_notes = st.columns(2)
    with col_region:
        new_region = st.text_input(
            "Region / State (optional)", key="new_stop_region", disabled=not is_draft
        )
    with col_notes:
        new_stop_notes = st.text_input(
            "Notes (optional)", key="new_stop_notes", disabled=not is_draft
        )
    col_start, col_end = st.columns(2)
    with col_start:
        new_start = st.date_input(
            "Start Date*",
            value=datetime.now(),
            key="new_stop_start",
            disabled=not is_draft,
        )
    with col_end:
        new_end = st.date_input(
            "End Date*", value=datetime.now(), key="new_stop_end", disabled=not is_draft
        )

    if st.button("➕ Add Stop", key="add_stop_button", disabled=not is_draft):
        if new_city and new_start and new_end:
            st.session_state["trip_stops"].append(
                {
                    "city": new_city,
                    "country": new_country,
                    "region": new_region,
                    "start_date": new_start.isoformat(),
                    "end_date": new_end.isoformat(),
                    "notes": new_stop_notes,
                }
            )
            st.success(
                f"Added: {new_city}" + (f", {new_country}" if new_country else "")
            )
            st.rerun()
        else:
            st.warning("City, Start Date, and End Date are required.")

# --- Budget ---
budget = st.number_input(
    f"💰 Trip Budget",
    min_value=0.0,
    step=100.0,
    value=float(trip_data.get("budget", 0)) if is_editing and trip_data else 0.0,
    disabled=not is_draft,
    key="trip_budget",
)

# --- PER‑TRIP CURRENCIES (only editable for Drafts) ---
st.subheader("💱 Trip Currencies")
col_currency1, col_currency2 = st.columns(2)

# Display Currency
display_currency_options = ["USD", "EUR", "GBP", "NGN", "JPY", "BRL"]
if is_editing and trip_data:
    current_display = trip_data.get("display_currency", "USD")
else:
    current_display = "USD"

with col_currency1:
    trip_display_currency = st.selectbox(
        "Display Currency (for this trip)",
        options=display_currency_options,
        index=display_currency_options.index(current_display) if current_display in display_currency_options else 0,
        disabled=not is_draft,
        key="trip_display_currency",
        help="The currency symbol used for display in this trip. Does not affect stored amounts.",
    )

# Base Currency
base_currency_options = ["USD", "EUR", "GBP", "NGN", "JPY", "BRL", "CAD", "AUD", "CHF", "CNY", "INR"]
if is_editing and trip_data:
    current_base = trip_data.get("base_currency", "USD")
else:
    current_base = "USD"

with col_currency2:
    trip_base_currency = st.selectbox(
        "Base Currency (for reporting & conversion)",
        options=base_currency_options,
        index=base_currency_options.index(current_base) if current_base in base_currency_options else 0,
        disabled=not is_draft,
        key="trip_base_currency",
        help="All foreign-currency expenses are converted to this currency using snapshot rates.",
    )

# --- Create / Update Button ---
if is_editing:
    if is_draft:
        if st.button("🚀 Update Draft", key="update_trip"):
            if trip_purpose and st.session_state["trip_stops"]:
                first_stop = st.session_state["trip_stops"][0]
                last_stop = st.session_state["trip_stops"][-1]
                overall_start = first_stop["start_date"]
                overall_end = last_stop["end_date"]
                stop_cities = [stop["city"] for stop in st.session_state["trip_stops"]]
                dest_summary = " → ".join(stop_cities)

                # Update the existing trip directly – no new trip created
                db.update_trip_purpose(trip_id, trip_purpose)
                db.update_trip_dates(trip_id, overall_start, overall_end, dest_summary)
                db.update_trip_budget(trip_id, budget)
                db.update_trip_departure_details(
                    trip_id, departure_city, departure_region, departure_country
                )
                # Update per-trip currencies
                db.update_trip_currencies(trip_id, trip_base_currency, trip_display_currency)

                # Update stops – delete all and re-add
                db.delete_all_trip_stops(trip_id)
                for idx, stop in enumerate(st.session_state["trip_stops"]):
                    db.add_trip_stop(
                        trip_id,
                        idx + 1,
                        stop["city"],
                        stop.get("country", ""),
                        stop.get("region", ""),
                        stop["start_date"],
                        stop["end_date"],
                        stop.get("notes", ""),
                    )

                st.session_state["trip_destination_summary"] = dest_summary
                st.success(f"Trip '{trip_purpose}' updated successfully!")
                st.rerun()
            else:
                st.warning("Enter a Trip Name and add at least one stop.")
    else:
        st.warning(
            f"⚠️ This trip is **{trip_status.title()}** and cannot be edited directly. Use the 'Revert to Draft' button below or Duplicate it."
        )
else:
    # New trip creation
    if st.button("🚀 Create Trip", key="create_trip"):
        if trip_purpose and st.session_state["trip_stops"]:
            first_stop = st.session_state["trip_stops"][0]
            last_stop = st.session_state["trip_stops"][-1]
            overall_start = first_stop["start_date"]
            overall_end = last_stop["end_date"]
            stop_cities = [stop["city"] for stop in st.session_state["trip_stops"]]
            dest_summary = " → ".join(stop_cities)

            trip_id = db.create_or_get_trip(
                exec_id,
                dest_summary,
                overall_start,
                overall_end,
                trip_purpose,
                trip_display_currency,
                trip_base_currency,
            )
            db.update_trip_budget(trip_id, budget)
            db.update_trip_departure_details(
                trip_id, departure_city, departure_region, departure_country
            )

            db.delete_all_trip_stops(trip_id)
            for idx, stop in enumerate(st.session_state["trip_stops"]):
                db.add_trip_stop(
                    trip_id,
                    idx + 1,
                    stop["city"],
                    stop.get("country", ""),
                    stop.get("region", ""),
                    stop["start_date"],
                    stop["end_date"],
                    stop.get("notes", ""),
                )

            st.session_state["current_trip_id"] = trip_id
            st.session_state["trip_destination_summary"] = dest_summary
            st.success(
                f"Trip '{trip_purpose}' created with {len(st.session_state['trip_stops'])} stops!"
            )
            st.rerun()
        else:
            st.warning("Enter a Trip Name and add at least one stop.")

# =========================================================
# EDIT EXECUTIVE
# =========================================================
if st.session_state.get("editing_exec", False):
    with st.expander("✏️ Edit Executive Profile", expanded=True):
        st.info(f"Editing: {profile['name']}")
        companies = db.get_all_companies()
        company_options = {name: id for id, name in companies}
        current_company_id = profile.get("company_id")
        tz_display_names, tz_map = get_timezone_dropdown_options()
        current_tz = profile.get("timezone", "America/New_York")
        current_tz_display = next(
            (n for n in tz_display_names if current_tz in n), tz_display_names[0]
        )

        with st.form("edit_exec_form"):
            curr_comp_name = next(
                (
                    name
                    for name, cid in company_options.items()
                    if cid == current_company_id
                ),
                list(company_options.keys())[0] if company_options else "",
            )
            new_company_label = st.selectbox(
                "Company*",
                list(company_options.keys()),
                index=(
                    list(company_options.keys()).index(curr_comp_name)
                    if curr_comp_name in company_options
                    else 0
                ),
                key="edit_company",
            )
            new_company_id = company_options[new_company_label]

            new_name = st.text_input(
                "Full Name*", value=profile.get("name", ""), key="edit_name"
            )
            new_email = st.text_input(
                "Email", value=profile.get("email", ""), key="edit_email"
            )
            new_tz_display = st.selectbox(
                "Timezone",
                tz_display_names,
                index=tz_display_names.index(current_tz_display),
                key="edit_tz",
            )
            new_tz = tz_map[new_tz_display]

            seat_options = ["No Preference", "Aisle", "Window", "Middle"]
            new_seat = st.selectbox(
                "Seat Preference",
                seat_options,
                index=safe_index(
                    seat_options, profile.get("seat_preference", "No Preference")
                ),
                key="edit_seat",
            )
            new_hotel = st.text_input(
                "Hotel Loyalty",
                value=profile.get("hotel_loyalty", ""),
                key="edit_hotel",
            )
            new_ff = st.text_input(
                "Frequent Flyer Number",
                value=profile.get("frequent_flyer_number", ""),
                key="edit_ff",
            )
            new_diet = st.text_input(
                "Dietary Restrictions",
                value=profile.get("dietary_restrictions", ""),
                key="edit_diet",
            )
            new_passport = st.text_input(
                "Passport Number",
                value=profile.get("passport_number", ""),
                key="edit_passport",
            )
            new_airline = st.text_input(
                "Preferred Airline",
                value=profile.get("preferred_airline", ""),
                key="edit_airline",
            )
            new_tsa = st.text_input(
                "TSA PreCheck", value=profile.get("tsa_precheck", ""), key="edit_tsa"
            )
            meal_options = [
                "No Preference",
                "Vegetarian",
                "Vegan",
                "Kosher",
                "Halal",
                "Gluten-Free",
            ]
            new_meal = st.selectbox(
                "Meal Preference",
                meal_options,
                index=safe_index(
                    meal_options, profile.get("meal_preference", "No Preference")
                ),
                key="edit_meal",
            )

            col_save, col_cancel = st.columns(2)
            with col_save:
                submitted = st.form_submit_button("💾 Save Changes")
            with col_cancel:
                cancel = st.form_submit_button("❌ Cancel")

            if submitted:
                db.update_executive(
                    exec_id,
                    new_company_id,
                    new_name,
                    new_email,
                    new_tz,
                    new_seat if new_seat != "No Preference" else "",
                    new_hotel,
                    new_ff,
                    new_diet,
                    new_passport,
                    new_airline,
                    new_tsa,
                    new_meal if new_meal != "No Preference" else "",
                )
                st.success(f"✅ Executive '{new_name}' updated!")
                st.session_state["editing_exec"] = False
                st.rerun()
            if cancel:
                st.session_state["editing_exec"] = False
                st.rerun()

        # --- Membership Management ---
        st.divider()
        st.subheader("✈️ Manage Memberships")
        existing_mems = db.get_memberships(exec_id)
        if existing_mems:
            for m in existing_mems:
                col1, col2 = st.columns([4, 1])
                with col1:
                    emoji = (
                        "✈️"
                        if m["category"] == "airline"
                        else "🏨" if m["category"] == "hotel" else "🚗"
                    )
                    st.write(f"{emoji} {m['program_name']}: {m['membership_number']}")
                with col2:
                    if st.button("❌", key=f"del_mem_{m['id']}"):
                        db.delete_membership(m["id"])
                        st.rerun()
        else:
            st.info("No memberships added yet.")

        st.write("**Add New Membership:**")
        col_cat, col_name, col_num = st.columns(3)
        with col_cat:
            new_cat = st.selectbox(
                "Category", ["Airline", "Hotel", "Car Rental"], key="edit_mem_cat"
            )
        with col_name:
            new_name = st.text_input("Program Name", key="edit_mem_name")
        with col_num:
            new_num = st.text_input("Membership Number", key="edit_mem_num")
        if st.button("➕ Add Membership", key="edit_add_mem"):
            if new_name and new_num:
                db.add_membership(exec_id, new_cat.lower(), new_name, new_num)
                st.success(f"Added {new_name}")
                st.rerun()
            else:
                st.warning("Fill in both fields.")

# =========================================================
# DELETE EXECUTIVE CONFIRMATION DIALOG
# =========================================================
if st.session_state.get("show_delete_exec_confirm", False):
    st.warning("⚠️ You are about to delete this executive.")

    # Check how many trips they have
    trip_count = db.get_executive_trip_count(exec_id)
    exec_name = profile.get("name", "Unknown")

    if trip_count > 0:
        st.error(
            f"⚠️ **{exec_name}** has **{trip_count}** trip(s). They will be **permanently deleted** along with all associated itinerary items, stops, and receipts."
        )
    else:
        st.info(f"**{exec_name}** has no trips. They can be safely deleted.")

    st.markdown("**This action cannot be undone.**")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Yes, Permanently Delete", key="confirm_delete_exec"):
            success, msg = db.delete_executive(exec_id, force=True)
            if success:
                st.success(msg)
                # Reset session state
                st.session_state["show_delete_exec_confirm"] = False
                if "current_trip_id" in st.session_state:
                    del st.session_state["current_trip_id"]
                if "editing_exec" in st.session_state:
                    del st.session_state["editing_exec"]
                if "trip_stops" in st.session_state:
                    del st.session_state["trip_stops"]
                # Remove the executive from dropdown by rerunning
                st.rerun()
            else:
                st.error(msg)
    with col2:
        if st.button("❌ Cancel", key="cancel_delete_exec"):
            st.session_state["show_delete_exec_confirm"] = False
            st.rerun()

# =========================================================
# ITINERARY & ITEMS (The main trip view)
# =========================================================
if "current_trip_id" in st.session_state:
    trip_id = st.session_state["current_trip_id"]
    trip_data = db.get_trip(trip_id)
    if not trip_data:
        st.warning("Trip not found. Create a new one.")
        st.stop()

    trip_budget = trip_data.get("budget", 0)
    items = db.get_items_for_trip(trip_id)
    stops = db.get_trip_stops(trip_id)

    # --- Retrieve per-trip currencies ---
    trip_display_currency = trip_data.get("display_currency", "USD")
    display_symbol = get_currency_symbol(trip_display_currency)

    trip_base_currency = trip_data.get("base_currency", "USD")
    base_symbol = get_currency_symbol(trip_base_currency)

    # --- TRIP MANAGEMENT (Delete Trip + Status + Duplicate) ---
    st.divider()
    col_title, col_status, col_delete, col_duplicate = st.columns([3, 1, 1, 1])
    with col_title:
        st.subheader(f"📋 Current Itinerary: {trip_data.get('purpose', '')}")
    with col_status:
        current_status = trip_data.get("status", "draft")
        st.caption(f"**Status:** {current_status.title()}")

        # --- Status management buttons ---
        if current_status == "draft":
            if st.button("✅ Mark as Approved", key="approve_trip"):
                db.update_trip_status(trip_id, "approved")
                st.rerun()
        elif current_status == "approved":
            if st.button("📄 Mark as Final", key="finalize_trip"):
                db.update_trip_status(trip_id, "final")
                st.rerun()
            if st.button("↩️ Revert to Draft", key="revert_to_draft_approved"):
                db.update_trip_status(trip_id, "draft")
                st.rerun()
        elif current_status == "final":
            if st.button("↩️ Revert to Draft", key="revert_to_draft_final"):
                db.update_trip_status(trip_id, "draft")
                st.rerun()
    with col_delete:
        if st.button("🗑️ Delete Trip", key="delete_trip_btn"):
            st.session_state["show_delete_trip_confirm"] = True
    with col_duplicate:
        if st.button("🔄 Duplicate Trip", key="duplicate_trip_btn"):
            new_trip_id = db.duplicate_trip(trip_id, exec_id)
            if new_trip_id:
                st.session_state["current_trip_id"] = new_trip_id
                st.success("Trip duplicated successfully! New trip is in Draft status.")
                st.rerun()
            else:
                st.error("Failed to duplicate trip.")

    # --- Delete Trip Confirmation ---
    if st.session_state.get("show_delete_trip_confirm", False):
        with st.container():
            st.warning("⚠️ Permanently delete this trip?")
            col_yes, col_no = st.columns(2)
            with col_yes:
                if st.button("✅ Yes, Delete", key="confirm_del_trip_yes"):
                    db.delete_trip(trip_id)
                    st.session_state.pop("current_trip_id", None)
                    st.session_state.pop("trip_destination_summary", None)
                    st.session_state["show_delete_trip_confirm"] = False
                    st.success("Trip deleted.")
                    st.rerun()
            with col_no:
                if st.button("❌ Cancel", key="confirm_del_trip_no"):
                    st.session_state["show_delete_trip_confirm"] = False
                    st.rerun()

    # --- Trip Route with EDIT STOPS ---
    dep_city_db = trip_data.get("departure_city", "")
    dep_region_db = trip_data.get("departure_region", "")
    dep_country_db = trip_data.get("departure_country", "")
    dep_parts = [p for p in [dep_city_db, dep_region_db, dep_country_db] if p]
    departure_display = ", ".join(dep_parts) if dep_parts else ""

    if stops:
        st.subheader("📍 Trip Route")
        stop_dates = []
        for stop in stops:
            loc = stop["city"]
            loc_parts = []
            if stop.get("region"):
                loc_parts.append(stop["region"])
            if stop.get("country"):
                loc_parts.append(stop["country"])
            if loc_parts:
                loc += f" ({', '.join(loc_parts)})"
            stop_dates.append(
                f"{loc} ({format_date_display(stop['start_date'])} - {format_date_display(stop['end_date'])})"
            )
        route_display = " → ".join(stop_dates)
        if departure_display:
            route_display = f"📍 {departure_display} → " + route_display
        st.write(route_display)

        # --- EDIT STOPS ---
        with st.expander("✏️ Edit Stops"):
            for stop in stops:
                st.markdown(f"**Stop {stop['stop_order']}:** {stop['city']}")
                with st.form(key=f"edit_stop_{stop['id']}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        e_city = st.text_input(
                            "City", value=stop["city"], key=f"e_city_{stop['id']}"
                        )
                        e_country = st.selectbox(
                            "Country",
                            [""] + country_list,
                            index=(
                                ([""] + country_list).index(stop.get("country", ""))
                                if stop.get("country") in [""] + country_list
                                else 0
                            ),
                            key=f"e_country_{stop['id']}",
                        )
                    with col2:
                        e_region = st.text_input(
                            "Region",
                            value=stop.get("region", ""),
                            key=f"e_region_{stop['id']}",
                        )
                    col_d1, col_d2 = st.columns(2)
                    with col_d1:
                        e_start = st.date_input(
                            "Start Date",
                            value=datetime.fromisoformat(stop["start_date"]),
                            key=f"e_start_{stop['id']}",
                        )
                    with col_d2:
                        e_end = st.date_input(
                            "End Date",
                            value=datetime.fromisoformat(stop["end_date"]),
                            key=f"e_end_{stop['id']}",
                        )
                    e_notes = st.text_input(
                        "Notes",
                        value=stop.get("notes", ""),
                        key=f"e_notes_{stop['id']}",
                    )

                    col_b1, col_b2 = st.columns(2)
                    with col_b1:
                        if st.form_submit_button("💾 Update Stop"):
                            db.update_trip_stop(
                                stop["id"],
                                e_city,
                                e_country,
                                e_region,
                                e_start.isoformat(),
                                e_end.isoformat(),
                                e_notes,
                            )
                            st.success("Stop updated!")
                            st.rerun()
                    with col_b2:
                        if st.form_submit_button("🗑️ Remove Stop"):
                            db.delete_trip_stop(stop["id"])
                            st.rerun()

    # --- DISPLAY ITINERARY ITEMS ---
    if items:
        # --- Spending Summary (converted to Base Currency) ---
        spending = db.get_trip_spending(trip_id)

        # Convert spending totals to base currency using snapshot rates
        total_estimated_converted = 0.0
        total_confirmed_converted = 0.0
        total_all_converted = 0.0
        for item in items:
            cost = item.get("cost", 0)
            snapshot_rate = item.get("exchange_rate_snapshot", 1.0)
            converted = cost * snapshot_rate
            total_all_converted += converted
            if item.get("is_confirmed"):
                total_confirmed_converted += converted
            else:
                total_estimated_converted += converted

        st.subheader("💰 Spending Summary")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric(
                "Total Estimated (Quoted)",
                f"{base_symbol}{total_estimated_converted:,.2f}",
                help="Converted using snapshot rate at time of each expense.",
            )
        with col2:
            st.metric(
                "✅ Confirmed (Booked)",
                f"{base_symbol}{total_confirmed_converted:,.2f}",
            )
        with col3:
            st.metric(
                "📊 Total Spend",
                f"{base_symbol}{total_all_converted:,.2f}",
            )
        with col4:
            remaining = trip_budget - total_all_converted
            st.metric(
                "💰 Budget",
                f"{base_symbol}{trip_budget:,.2f}",
                delta=f"{base_symbol}{remaining:,.2f} remaining",
                delta_color="inverse" if remaining < 0 else "normal",
            )

        if trip_budget > 0:
            percent_used = min((total_all_converted / trip_budget) * 100, 100)
            st.progress(percent_used / 100, text="{:.0f}% used".format(percent_used))
        st.divider()

        # --- Conflicts ---
        conflicts = utils.detect_conflicts(items)
        if conflicts:
            st.warning("⚠️ Conflicts Detected:")
            for c in conflicts:
                st.write(f"- {c}")
        else:
            st.success("✅ No scheduling conflicts detected.")

        # --- Display Mode selector ---
        display_mode = st.radio(
            "Show costs in:",
            ["Original Currency", "Snapshot (at time of expense)", "Live Conversion"],
            index=0,
            key="display_mode",
            horizontal=True,
        )

        # --- Fetch live rates only if needed ---
        live_rates = None
        if display_mode == "Live Conversion":
            try:
                live_rates = get_exchange_rates(trip_base_currency)
            except Exception as e:
                st.warning(f"Could not fetch live rates: {e}. Using snapshot rates.")
                display_mode = "Snapshot (at time of expense)"

        # =========================================================
        # 6-COLUMN LAYOUT with resettable uploader key
        # =========================================================
        st.subheader("📋 Itinerary Items")

        for item in items:
            # ---- Row: 6 columns ----
            (
                col_desc,
                col_receipt_status,
                col_upload,
                col_del_receipt,
                col_del_item,
                col_edit,
            ) = st.columns([4, 2, 2, 1, 1, 1])

            # --- Calculate display cost based on mode ---
            orig_currency = item.get("cost_currency", "USD")
            orig_cost = item.get("cost", 0)
            snapshot_rate = item.get("exchange_rate_snapshot", 1.0)

            if display_mode == "Original Currency":
                display_cost = orig_cost
                display_symbol_local = display_symbol
                display_currency_code = trip_display_currency
            elif display_mode == "Snapshot (at time of expense)":
                display_cost = orig_cost * snapshot_rate
                display_symbol_local = base_symbol
                display_currency_code = trip_base_currency
            else:  # Live Conversion
                if live_rates is not None:
                    display_cost = convert(
                        orig_cost, orig_currency, trip_base_currency, live_rates
                    )
                else:
                    display_cost = orig_cost * snapshot_rate
                display_symbol_local = base_symbol
                display_currency_code = trip_base_currency

            # Format display
            display_str = f"{display_symbol_local}{display_cost:,.2f} {display_currency_code}"

            start_display = format_datetime_display(item["datetime_start"])
            end_display = (
                datetime.fromisoformat(item["datetime_end"]).strftime("%H:%M")
                if item["datetime_end"]
                else "TBD"
            )
            status_icon = "✅" if item.get("is_confirmed") else "📌"

            # Column 1: Description
            with col_desc:
                st.write(
                    f"{status_icon} **{start_display} – {end_display}** | {item['item_type']}: {item['description']} | Cost: {display_str}"
                )

            # Column 2: Receipt status + Download button
            with col_receipt_status:
                receipt_path = item.get("receipt_path")
                if receipt_path and os.path.exists(receipt_path):
                    st.success("📎 Attached")
                    with open(receipt_path, "rb") as f:
                        file_bytes = f.read()
                    st.download_button(
                        label="⬇️ Download",
                        data=file_bytes,
                        file_name=os.path.basename(receipt_path),
                        mime="application/octet-stream",
                        key=f"download_{item['id']}",
                    )
                else:
                    st.info("No receipt")

            # Column 3: Upload receipt – key includes counter to reset
            with col_upload:
                upload_key = f"receipt_{item['id']}_{st.session_state.upload_counter}"
                uploaded_file = st.file_uploader(
                    "Attach",
                    type=["png", "jpg", "jpeg", "pdf"],
                    key=upload_key,
                    label_visibility="collapsed",
                )
                if uploaded_file is not None:
                    # Only process if no receipt exists yet
                    if not receipt_path or not os.path.exists(receipt_path):
                        os.makedirs("receipts", exist_ok=True)
                        trip_folder = f"receipts/trip_{trip_id}"
                        os.makedirs(trip_folder, exist_ok=True)
                        original_name = uploaded_file.name
                        safe_name = (
                            f"item_{item['id']}_{original_name.replace(' ', '_')}"
                        )
                        file_path = os.path.join(trip_folder, safe_name)
                        with open(file_path, "wb") as f:
                            f.write(uploaded_file.getbuffer())
                        db.update_receipt_path(item["id"], file_path)
                        # Increment counter to reset uploader key
                        st.session_state.upload_counter += 1
                        st.success("✅ Receipt attached!")
                        st.rerun()
                    else:
                        st.info("A receipt is already attached. Remove it first.")

            # Column 4: Delete Receipt
            with col_del_receipt:
                if receipt_path and os.path.exists(receipt_path):
                    if st.button("🗑️ Receipt", key=f"del_receipt_{item['id']}"):
                        try:
                            os.remove(receipt_path)
                            st.success(
                                f"✅ Receipt deleted: {os.path.basename(receipt_path)}"
                            )
                        except Exception as e:
                            st.error(f"Could not delete file: {e}")
                        db.update_receipt_path(item["id"], None)
                        # Increment counter to reset uploader key
                        st.session_state.upload_counter += 1
                        st.rerun()

            # Column 5: Delete Entire Item
            with col_del_item:
                if st.button("❌ Item", key=f"del_item_{item['id']}"):
                    db.delete_itinerary_item(item["id"])
                    st.rerun()

            # Column 6: ✏️ Edit button (toggles the edit form)
            with col_edit:
                if st.button("✏️", key=f"edit_btn_{item['id']}"):
                    st.session_state[f"editing_item_{item['id']}"] = (
                        not st.session_state.get(f"editing_item_{item['id']}", False)
                    )
                    st.rerun()

            # ---- EDIT FORM (if toggled) ----
            if st.session_state.get(f"editing_item_{item['id']}", False):
                with st.expander(f"✏️ Editing: {item['description']}", expanded=True):
                    with st.form(key=f"edit_item_form_{item['id']}"):
                        # Get categories from DB
                        categories = db.get_all_categories()
                        cat_names = (
                            [cat[1] for cat in categories]
                            if categories
                            else ["Flight", "Hotel", "Meeting", "Transport"]
                        )
                        idx_cat = (
                            cat_names.index(item["item_type"])
                            if item["item_type"] in cat_names
                            else 0
                        )

                        e_type = st.selectbox(
                            "Type", cat_names, index=idx_cat, key=f"e_type_{item['id']}"
                        )
                        e_desc = st.text_input(
                            "Description",
                            value=item["description"],
                            key=f"e_desc_{item['id']}",
                        )

                        col_dt1, col_dt2 = st.columns(2)
                        with col_dt1:
                            e_start = st.datetime_input(
                                "Start Time",
                                value=datetime.fromisoformat(item["datetime_start"]),
                                key=f"e_start_{item['id']}",
                            )
                        with col_dt2:
                            e_end = st.datetime_input(
                                "End Time",
                                value=(
                                    datetime.fromisoformat(item["datetime_end"])
                                    if item["datetime_end"]
                                    else datetime.now()
                                ),
                                key=f"e_end_{item['id']}",
                            )

                        e_loc = st.text_input(
                            "Location",
                            value=item.get("location", ""),
                            key=f"e_loc_{item['id']}",
                        )
                        col_cost1, col_conf1 = st.columns(2)
                        with col_cost1:
                            e_cost = st.number_input(
                                "Cost (original)",
                                min_value=0.0,
                                step=10.0,
                                value=float(item.get("cost", 0)),
                                key=f"e_cost_{item['id']}",
                            )
                            # Add currency dropdown for editing
                            e_cost_currency = st.selectbox(
                                "Currency",
                                options=["USD", "EUR", "GBP", "NGN", "JPY", "BRL"],
                                index=["USD", "EUR", "GBP", "NGN", "JPY", "BRL"].index(
                                    item.get("cost_currency", "USD")
                                ),
                                key=f"e_cost_currency_{item['id']}",
                            )
                        with col_conf1:
                            e_conf = st.text_input(
                                "Confirmation Code",
                                value=item.get("confirmation_code", ""),
                                key=f"e_conf_{item['id']}",
                            )

                        e_notes = st.text_area(
                            "Notes",
                            value=item.get("notes", ""),
                            key=f"e_notes_{item['id']}",
                        )
                        e_confirmed = st.checkbox(
                            "Confirmed",
                            value=bool(item.get("is_confirmed", False)),
                            key=f"e_confirmed_{item['id']}",
                        )

                        # --- VISIBLE HINT FOR SAVE/CANCEL BUTTONS ---
                        st.markdown("---")
                        st.markdown(
                            "**⬇️ Scroll down to find the Save and Cancel buttons below.**"
                        )
                        st.markdown("---")

                        col_s, col_c = st.columns(2)
                        with col_s:
                            if st.form_submit_button("💾 Save Changes"):
                                # Recompute snapshot rate if currency changed
                                new_snapshot_rate = get_snapshot_rate(
                                    trip_base_currency, e_cost_currency
                                )
                                db.update_itinerary_item(
                                    item["id"],
                                    e_type,
                                    e_desc,
                                    e_start.isoformat(),
                                    e_end.isoformat() if e_end else None,
                                    e_loc,
                                    e_cost,
                                    e_conf,
                                    e_notes,
                                    1 if e_confirmed else 0,
                                    e_cost_currency,
                                    new_snapshot_rate,
                                )
                                st.session_state[f"editing_item_{item['id']}"] = False
                                st.success("Item updated!")
                                st.rerun()
                        with col_c:
                            if st.form_submit_button("❌ Cancel"):
                                st.session_state[f"editing_item_{item['id']}"] = False
                                st.rerun()

        # --- ADD NEW ITEM ---
        st.divider()
        st.subheader("➕ Add New Itinerary Item")
        with st.form("add_item_form"):
            categories = db.get_all_categories()
            cat_names = (
                [cat[1] for cat in categories]
                if categories
                else ["Flight", "Hotel", "Meeting", "Transport"]
            )

            cols = st.columns(4)
            with cols[0]:
                item_type = st.selectbox("Type", cat_names, key="item_type")
            with cols[1]:
                desc = st.text_input("Description", key="item_desc")
            with cols[2]:
                dt_start = st.datetime_input(
                    "Start Time", value=datetime.now(), key="item_start"
                )
            with cols[3]:
                dt_end = st.datetime_input(
                    "End Time", value=datetime.now(), key="item_end"
                )

            col_loc, col_cost, col_conf = st.columns(3)
            with col_loc:
                location = st.text_input("Location", key="item_location")
            with col_cost:
                cost = st.number_input(
                    f"Cost (original currency)",
                    min_value=0.0,
                    step=10.0,
                    key="item_cost",
                )
            with col_conf:
                conf_code = st.text_input("Confirmation Code", key="item_conf")
            # Add currency dropdown for the new item
            cost_currency = st.selectbox(
                "Currency",
                options=["USD", "EUR", "GBP", "NGN", "JPY", "BRL"],
                key="item_currency",
                index=0,
            )

            notes = st.text_area("Notes", key="item_notes")
            confirmed = st.checkbox("✅ Confirmed / Booked", key="item_confirmed")

            if st.form_submit_button("Add to Itinerary"):
                if desc and dt_start:
                    # Compute snapshot rate using trip's base currency
                    snapshot_rate = get_snapshot_rate(trip_base_currency, cost_currency)
                    db.add_itinerary_item(
                        trip_id,
                        item_type,
                        desc,
                        dt_start.isoformat(),
                        dt_end.isoformat() if dt_end else None,
                        location,
                        cost,
                        conf_code,
                        notes,
                        1 if confirmed else 0,
                        cost_currency,
                        snapshot_rate,
                    )
                    st.success("Added!")
                    st.rerun()
                else:
                    st.warning("Description and Start Time required.")

        # --- EXPORT BUTTONS ---
        st.divider()
        col_gen, col_cal, col_expense_word, col_expense_excel = st.columns(4)

        with col_gen:
            if st.button("📄 Generate Word Itinerary"):
                exec_data = db.get_executive_profile(exec_id)
                stops_data = db.get_trip_stops(trip_id)
                doc_stream, filename = doc_generator.generate_itinerary_doc(
                    exec_data,
                    items,
                    stops_data,
                    dep_city_db,
                    dep_region_db,
                    dep_country_db,
                    trip_id,
                    trip_budget,
                    display_symbol,  # display symbol
                    trip_display_currency,  # display code
                    base_currency=trip_base_currency,  # not used for conversion unless convert_to_base=True
                    convert_to_base=False,
                )
                st.download_button(
                    "⬇️ Download Word Doc",
                    data=doc_stream,
                    file_name=f"{exec_data['name']}_{trip_purpose}_itinerary.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml",
                    key="itinerary_download",
                )

        with col_cal:
            if st.button("📅 Export to Calendar (.ics)"):
                ics_data = utils.generate_ics(
                    items, profile.get("timezone", "America/New_York"), trip_purpose
                )
                st.download_button(
                    "⬇️ Download .ics",
                    data=ics_data,
                    file_name=f"{profile['name']}_{trip_purpose}.ics",
                    mime="text/calendar",
                    key="ics_download",
                )

        with col_expense_word:
            if st.button("🧾 Export Expense Report (Word)"):
                if items:
                    stops_data = db.get_trip_stops(trip_id)
                    exec_data = db.get_executive_profile(exec_id)
                    doc_stream, filename = doc_generator.generate_expense_report_doc(
                        exec_data,
                        items,
                        stops_data,
                        dep_city_db,
                        dep_region_db,
                        dep_country_db,
                        trip_id,
                        trip_budget,
                        trip_purpose,
                        display_symbol,  # not used inside; kept for compatibility
                        base_currency=trip_base_currency,  # conversion target
                    )
                    st.download_button(
                        "⬇️ Download Word Report",
                        data=doc_stream,
                        file_name=f"{exec_data['name']}_{trip_purpose}_ExpenseReport.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml",
                        key="expense_download",
                    )
                else:
                    st.warning("No items to export.")

        with col_expense_excel:
            if st.button("📊 Expense to Excel", key="expense_excel"):
                if items:
                    trip_data_full = db.get_trip(trip_id)
                    excel_stream = export_expense_to_excel(
                        items,
                        trip_data_full,
                        display_symbol,  # display symbol
                        base_currency=trip_base_currency,
                    )
                    if excel_stream:
                        st.download_button(
                            label="⬇️ Download .xlsx",
                            data=excel_stream,
                            file_name=f"{trip_purpose}_ExpenseReport.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key="expense_excel_download",
                        )
                else:
                    st.warning("No items to export.")
    else:
        st.info("No itinerary items yet. Add one below.")
        # Show Add Item form even if no items
        st.divider()
        st.subheader("➕ Add Itinerary Item")
        with st.form("add_item_form_empty"):
            categories = db.get_all_categories()
            cat_names = (
                [cat[1] for cat in categories]
                if categories
                else ["Flight", "Hotel", "Meeting", "Transport"]
            )
            cols = st.columns(4)
            with cols[0]:
                item_type = st.selectbox("Type", cat_names, key="item_type_empty")
            with cols[1]:
                desc = st.text_input("Description", key="item_desc_empty")
            with cols[2]:
                dt_start = st.datetime_input(
                    "Start Time", value=datetime.now(), key="item_start_empty"
                )
            with cols[3]:
                dt_end = st.datetime_input(
                    "End Time", value=datetime.now(), key="item_end_empty"
                )
            col_loc, col_cost, col_conf = st.columns(3)
            with col_loc:
                location = st.text_input("Location", key="item_location_empty")
            with col_cost:
                cost = st.number_input(
                    f"Cost (original currency)",
                    min_value=0.0,
                    step=10.0,
                    key="item_cost_empty",
                )
            with col_conf:
                conf_code = st.text_input("Confirmation Code", key="item_conf_empty")
            cost_currency = st.selectbox(
                "Currency",
                options=["USD", "EUR", "GBP", "NGN", "JPY", "BRL"],
                key="item_currency_empty",
                index=0,
            )
            notes = st.text_area("Notes", key="item_notes_empty")
            confirmed = st.checkbox("✅ Confirmed / Booked", key="item_confirmed_empty")
            if st.form_submit_button("Add to Itinerary"):
                if desc and dt_start:
                    snapshot_rate = get_snapshot_rate(trip_base_currency, cost_currency)
                    db.add_itinerary_item(
                        trip_id,
                        item_type,
                        desc,
                        dt_start.isoformat(),
                        dt_end.isoformat() if dt_end else None,
                        location,
                        cost,
                        conf_code,
                        notes,
                        1 if confirmed else 0,
                        cost_currency,
                        snapshot_rate,
                    )
                    st.success("Added!")
                    st.rerun()
                else:
                    st.warning("Description and Start Time required.")

else:
    st.info("Create a trip first to start managing itinerary items.")

# =========================================================
# SPENDING DASHBOARD (All Trips) - WITH EDIT/DELETE
# =========================================================
st.divider()
with st.expander("📊 Spending Dashboard (All Trips)"):
    st.subheader("Filter & View Aggregate Spending")
    col_dash1, col_dash2 = st.columns(2)
    with col_dash1:
        exec_filter_options = ["All"] + [
            f"{name} (ID: {id})" for id, name, _ in executives
        ]
        exec_filter = st.selectbox(
            "Filter by Executive", exec_filter_options, key="dash_filter"
        )
        exec_id_filter = (
            None
            if exec_filter == "All"
            else int(exec_filter.split("(ID: ")[1].rstrip(")"))
        )
    with col_dash2:
        date_range = st.date_input("Date Range (optional)", value=[], key="dash_date")
    start_filter = date_range[0].isoformat() if len(date_range) > 0 else None
    end_filter = date_range[1].isoformat() if len(date_range) > 1 else None

    summary_data = db.get_spending_summary(
        exec_id=exec_id_filter, start_date=start_filter, end_date=end_filter
    )

    if summary_data:
        # Aggregate metrics – we need a consistent currency for dashboard totals.
        # We'll use the base_currency of each trip for its own totals, but for a global sum,
        # we need to convert everything to a single currency. For simplicity, we'll use USD.
        # However, we don't have per-item rates here, so we'll just display raw sums in USD.
        # For a better dashboard, you could add a target currency selector.
        # We'll keep it simple: just show the raw sums with a note.
        total_budget = sum(t["budget"] for t in summary_data)
        total_spent = sum(t["total_spent"] for t in summary_data)
        total_confirmed = sum(t["confirmed_spent"] for t in summary_data)
        total_estimated = sum(t["estimated_spent"] for t in summary_data)

        # Use USD for display as a fallback
        dashboard_symbol = get_currency_symbol("USD")

        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        col_m1.metric("Total Trips", len(summary_data))
        col_m2.metric(
            "Total Budget", f"{dashboard_symbol}{total_budget:,.2f}"
        )
        col_m3.metric(
            "Total Spent", f"{dashboard_symbol}{total_spent:,.2f}"
        )
        col_m4.metric(
            "Total Confirmed",
            f"{dashboard_symbol}{total_confirmed:,.2f}",
        )

        st.subheader("Trip-Level Breakdown")

        # --- Display each trip as an interactive row ---
        for trip in summary_data:
            # Show each trip's own base currency symbol for its amounts
            trip_base_currency = trip.get("base_currency", "USD")
            trip_symbol = get_currency_symbol(trip_base_currency)
            with st.container():
                col1, col2, col3, col4, col5, col6, col7, col8, col9, col10 = (
                    st.columns([1.5, 1.5, 1.2, 1, 1, 1, 1, 1, 0.8, 0.8])
                )
                with col1:
                    st.write(trip["executive_name"])
                with col2:
                    st.write(trip["company_name"])
                with col3:
                    st.write(trip["destination"])
                with col4:
                    st.write(
                        f"{trip_symbol}{trip['budget']:.2f}"
                    )
                with col5:
                    st.write(
                        f"{trip_symbol}{trip['total_spent']:.2f}"
                    )
                with col6:
                    st.write(
                        f"{trip_symbol}{trip['confirmed_spent']:.2f}"
                    )
                with col7:
                    st.write(
                        f"{trip_symbol}{trip['estimated_spent']:.2f}"
                    )
                with col8:
                    status = trip["status"]
                    if status == "draft":
                        st.write("📝 Draft")
                    elif status == "approved":
                        st.write("✅ Approved")
                    elif status == "final":
                        st.write("📄 Final")
                    else:
                        st.write(status)
                with col9:
                    # --- OPEN / EDIT BUTTON ---
                    if st.button("📂", key=f"open_trip_{trip['trip_id']}"):
                        st.session_state["current_trip_id"] = trip["trip_id"]
                        st.success(f"Loaded trip: {trip['destination']}")
                        st.rerun()
                with col10:
                    # --- DELETE BUTTON (with confirmation) ---
                    if st.button("🗑️", key=f"del_trip_dash_{trip['trip_id']}"):
                        st.session_state[f"confirm_del_trip_{trip['trip_id']}"] = True
                        st.rerun()

                # --- Delete confirmation (appears below the row) ---
                if st.session_state.get(f"confirm_del_trip_{trip['trip_id']}", False):
                    st.warning(f"⚠️ Permanently delete trip to {trip['destination']}?")
                    col_yes, col_no = st.columns(2)
                    with col_yes:
                        if st.button(
                            "✅ Yes, Delete", key=f"confirm_yes_{trip['trip_id']}"
                        ):
                            db.delete_trip(trip["trip_id"])
                            if (
                                st.session_state.get("current_trip_id")
                                == trip["trip_id"]
                            ):
                                st.session_state.pop("current_trip_id", None)
                            st.session_state.pop(
                                f"confirm_del_trip_{trip['trip_id']}", None
                            )
                            st.success("Trip deleted.")
                            st.rerun()
                    with col_no:
                        if st.button("❌ Cancel", key=f"confirm_no_{trip['trip_id']}"):
                            st.session_state.pop(
                                f"confirm_del_trip_{trip['trip_id']}", None
                            )
                            st.rerun()
                st.divider()

        # --- Export Buttons: CSV, Word, Excel ---
        st.subheader("📊 Export Data")
        col_exp1, col_exp2, col_exp3 = st.columns(3)

        with col_exp1:
            headers = [
                "Executive",
                "Company",
                "Destination",
                "Budget",
                "Total Spent",
                "Confirmed",
                "Estimated",
                "Status",
            ]
            rows = []
            for trip in summary_data:
                trip_base = trip.get("base_currency", "USD")
                sym = get_currency_symbol(trip_base)
                rows.append([
                    trip["executive_name"],
                    trip["company_name"],
                    trip["destination"],
                    f"{sym}{trip['budget']:.2f}",
                    f"{sym}{trip['total_spent']:.2f}",
                    f"{sym}{trip['confirmed_spent']:.2f}",
                    f"{sym}{trip['estimated_spent']:.2f}",
                    trip["status"],
                ])

            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(headers + ["Base Currency"])
            for row in rows:
                # We don't have per-row base currency easily, so we just add the trip's base from data
                # but we need to match. Since we lost the base currency in the row, we can loop again.
                # We'll use the summary_data directly.
                # Let's rebuild rows with base currency.
            # Quick fix: rebuild rows with base currency
                rows_with_currency = []
            for trip in summary_data:
                trip_base = trip.get("base_currency", "USD")
                sym = get_currency_symbol(trip_base)
                rows_with_currency.append([
                    trip["executive_name"],
                    trip["company_name"],
                    trip["destination"],
                    f"{sym}{trip['budget']:.2f}",
                    f"{sym}{trip['total_spent']:.2f}",
                    f"{sym}{trip['confirmed_spent']:.2f}",
                    f"{sym}{trip['estimated_spent']:.2f}",
                    trip["status"],
                    trip_base,
                ])
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(headers + ["Base Currency"])
            for row in rows_with_currency:
                writer.writerow(row)
            st.download_button(
                "📊 Export Dashboard CSV",
                data=output.getvalue().encode("utf-8"),
                file_name=f"spending_summary_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                key="dash_csv",
            )

        with col_exp2:
            if st.button("📄 Export Spending Report (Word)", key="dash_report"):
                doc_stream = doc_generator.generate_spending_report_doc(
                    exec_filter if exec_filter != "All" else "All Executives",
                    summary_data,
                    start_filter,
                    end_filter,
                    get_currency_symbol("USD"),  # default symbol
                    base_currency="USD",  # we use USD for aggregate
                )
                st.download_button(
                    "⬇️ Download Word Report",
                    data=doc_stream,
                    file_name=f"spending_report_{datetime.now().strftime('%Y%m%d')}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml",
                    key="dash_report_download",
                )

        with col_exp3:
            if st.button("📊 Export to Excel", key="dash_excel"):
                excel_stream = export_spending_to_excel(
                    summary_data,
                    get_currency_symbol("USD"),
                    "USD",
                    base_currency="USD",
                )
                if excel_stream:
                    st.download_button(
                        label="⬇️ Download .xlsx",
                        data=excel_stream,
                        file_name=f"spending_summary_{datetime.now().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="dash_excel_download",
                    )
    else:
        st.info("No trips found matching the filters.")