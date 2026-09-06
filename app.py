import streamlit as st
import database as db
import doc_generator
import utils
from datetime import datetime, timedelta
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
from currency import get_currency_symbol
import duplicate_detection
import sqlite3


# --- Helpers ---
def safe_index(options, value, default="No Preference"):
    if value is None:
        value = default
    try:
        return options.index(value)
    except ValueError:
        return options.index(default)


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

# --- Custom CSS ---
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

# --- Session State ---
if "upload_counter" not in st.session_state:
    st.session_state.upload_counter = 0

st.title("Executive Travel Planner")

# --- Init DB ---
db.init_db()

# =========================================================
# SIDEBAR: Executive Selection & Quick Actions
# =========================================================
st.sidebar.header("👤 Select Executive")

executives = db.get_all_executives()
if not executives:
    st.sidebar.warning(
        "No executives found. Add one in the 'Executive Management' tab."
    )
    exec_id = None
    profile = None
else:
    exec_options = {f"{name} (ID: {id})": id for id, name, _ in executives}
    selected_label = st.sidebar.selectbox("Choose Executive", list(exec_options.keys()))
    exec_id = exec_options[selected_label]
    profile = db.get_executive_profile(exec_id)

# Quick profile card (collapsible)
if profile:
    with st.sidebar.expander("📋 Quick Profile", expanded=False):
        st.write(f"**{profile['name']}**")
        st.write(f"🏢 {profile.get('company_name', 'N/A')}")
        st.write(f"🕐 {profile.get('timezone', 'N/A')}")
        st.write(f"💺 {profile.get('seat_preference', 'N/A')}")
        mems = db.get_memberships(exec_id)
        if mems:
            st.caption(f"✈️ {len(mems)} memberships")

        if st.button("👤 View Full Profile"):
            st.session_state["show_full_profile"] = True
            st.session_state["profile_edit_mode"] = False

    if st.session_state.get("show_full_profile", False):
        with st.popover("👤 Full Profile", use_container_width=True):
            if st.session_state.get("profile_edit_mode", False):
                st.subheader(f"✏️ Editing: {profile['name']}")
                with st.form("edit_exec_popover"):
                    companies = db.get_all_companies()
                    company_options = {name: id for id, name in companies}
                    current_company_id = profile.get("company_id")
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
                        key="edit_company_popover",
                    )
                    new_company_id = company_options[new_company_label]

                    new_name = st.text_input(
                        "Full Name*",
                        value=profile.get("name", ""),
                        key="edit_name_popover",
                    )
                    new_email = st.text_input(
                        "Email",
                        value=profile.get("email", ""),
                        key="edit_email_popover",
                    )

                    tz_display_names, tz_map = get_timezone_dropdown_options()
                    current_tz = profile.get("timezone", "America/New_York")
                    current_tz_display = next(
                        (n for n in tz_display_names if current_tz in n),
                        tz_display_names[0],
                    )
                    new_tz_display = st.selectbox(
                        "Timezone",
                        tz_display_names,
                        index=tz_display_names.index(current_tz_display),
                        key="edit_tz_popover",
                    )
                    new_tz = tz_map[new_tz_display]

                    seat_options = ["No Preference", "Aisle", "Window", "Middle"]
                    new_seat = st.selectbox(
                        "Seat Preference",
                        seat_options,
                        index=safe_index(
                            seat_options,
                            profile.get("seat_preference", "No Preference"),
                        ),
                        key="edit_seat_popover",
                    )
                    new_diet = st.text_input(
                        "Dietary Restrictions",
                        value=profile.get("dietary_restrictions", ""),
                        key="edit_diet_popover",
                    )
                    new_passport = st.text_input(
                        "Passport Number",
                        value=profile.get("passport_number", ""),
                        key="edit_passport_popover",
                    )
                    new_airline = st.text_input(
                        "Preferred Airline",
                        value=profile.get("preferred_airline", ""),
                        key="edit_airline_popover",
                    )
                    new_tsa = st.text_input(
                        "TSA PreCheck",
                        value=profile.get("tsa_precheck", ""),
                        key="edit_tsa_popover",
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
                            meal_options,
                            profile.get("meal_preference", "No Preference"),
                        ),
                        key="edit_meal_popover",
                    )

                    # -------- Passports Management (inside edit form) --------
                    st.subheader("🛂 Passports")
                    passports = db.get_passports(exec_id)
                    if passports:
                        for p in passports:
                            col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
                            with col1:
                                st.write(f"{p['country']}: {p['passport_number']}")
                            with col2:
                                st.write(f"Exp: {p.get('expiry_date') or ''}")
                            with col3:
                                st.write((p.get("notes") or "")[:30])
                            with col4:
                                if st.button("🗑️", key=f"del_pass_{p['id']}"):
                                    db.delete_passport(p["id"])
                                    st.rerun()
                    else:
                        st.caption("No passports added.")

                    with st.expander("➕ Add Passport"):
                        col_c, col_n = st.columns(2)
                        with col_c:
                            new_country = st.text_input(
                                "Country", key="add_pass_country"
                            )
                        with col_n:
                            new_pass_num = st.text_input(
                                "Passport Number", key="add_pass_num"
                            )
                        col_e, col_i = st.columns(2)
                        with col_e:
                            new_expiry = st.date_input(
                                "Expiry Date", value=None, key="add_pass_expiry"
                            )
                        with col_i:
                            new_issued = st.date_input(
                                "Issued Date", value=None, key="add_pass_issued"
                            )
                        new_notes_pass = st.text_area("Notes", key="add_pass_notes")
                        if st.button("➕ Add Passport", key="add_pass_btn"):
                            if new_country and new_pass_num:
                                db.add_passport(
                                    exec_id,
                                    new_country,
                                    new_pass_num,
                                    expiry_date=(
                                        new_expiry.isoformat() if new_expiry else None
                                    ),
                                    issued_date=(
                                        new_issued.isoformat() if new_issued else None
                                    ),
                                    notes=new_notes_pass,
                                )
                                st.rerun()
                            else:
                                st.warning("Country and Passport Number required.")

                    # -------- Memberships Management (inside edit form) --------
                    st.subheader("✈️ Memberships")
                    mems = db.get_memberships(exec_id)
                    if mems:
                        for m in mems:
                            col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
                            with col1:
                                emoji = (
                                    "✈️"
                                    if m["category"] == "airline"
                                    else "🏨" if m["category"] == "hotel" else "🚗"
                                )
                                st.write(
                                    f"{emoji} {m['program_name']}: {m['membership_number']}"
                                )
                            with col2:
                                tier = m.get("tier") or ""
                                alliance = m.get("alliance") or ""
                                airport = m.get("airport_code") or ""
                                details = []
                                if tier:
                                    details.append(tier)
                                if alliance:
                                    details.append(alliance)
                                if airport:
                                    details.append(airport)
                                st.write(", ".join(details) if details else "")
                            with col3:
                                st.write((m.get("notes") or "")[:30])
                            with col4:
                                if st.button("🗑️", key=f"del_mem_pop_{m['id']}"):
                                    db.delete_membership(m["id"])
                                    st.rerun()
                    else:
                        st.caption("No memberships added.")

                    with st.expander("➕ Add Membership"):
                        col_cat, col_name, col_num = st.columns(3)
                        with col_cat:
                            new_cat_pop = st.selectbox(
                                "Category",
                                ["Airline", "Hotel", "Car Rental"],
                                key="mem_pop_cat",
                            )
                        with col_name:
                            new_name_pop = st.text_input(
                                "Program Name", key="mem_pop_name"
                            )
                        with col_num:
                            new_num_pop = st.text_input(
                                "Membership Number", key="mem_pop_num"
                            )
                        col_extra1, col_extra2 = st.columns(2)
                        if new_cat_pop == "Airline":
                            with col_extra1:
                                new_tier_pop = st.text_input("Tier", key="mem_pop_tier")
                                new_alliance_pop = st.text_input(
                                    "Alliance", key="mem_pop_alliance"
                                )
                            with col_extra2:
                                new_airport_pop = st.text_input(
                                    "Airport Code", key="mem_pop_airport"
                                )
                                new_notes_mem_pop = st.text_area(
                                    "Notes", key="mem_pop_notes"
                                )
                            new_alliance_pop = new_alliance_pop or None
                            new_airport_pop = new_airport_pop or None
                        elif new_cat_pop == "Hotel":
                            with col_extra1:
                                new_tier_pop = st.text_input(
                                    "Status/Tier", key="mem_pop_tier"
                                )
                            with col_extra2:
                                new_notes_mem_pop = st.text_area(
                                    "Notes", key="mem_pop_notes"
                                )
                            new_alliance_pop = None
                            new_airport_pop = None
                        else:  # Car
                            with col_extra1:
                                new_notes_mem_pop = st.text_area(
                                    "Notes", key="mem_pop_notes"
                                )
                            new_tier_pop = None
                            new_alliance_pop = None
                            new_airport_pop = None

                        if st.button(
                            "➕ Add Membership (Popover)", key="add_mem_pop_btn"
                        ):
                            if new_name_pop and new_num_pop:
                                db.add_membership(
                                    exec_id,
                                    new_cat_pop.lower(),
                                    new_name_pop,
                                    new_num_pop,
                                    tier=new_tier_pop,
                                    alliance=new_alliance_pop,
                                    airport_code=new_airport_pop,
                                    notes=new_notes_mem_pop,
                                )
                                st.rerun()
                            else:
                                st.warning(
                                    "Program Name and Membership Number required."
                                )

                    # -------- End of extra sections --------

                    col_save, col_cancel, col_delete = st.columns(3)
                    with col_save:
                        submitted = st.form_submit_button("💾 Save Changes")
                    with col_cancel:
                        cancel = st.form_submit_button("❌ Cancel")
                    with col_delete:
                        if st.form_submit_button("🗑️ Delete Executive", type="primary"):
                            st.session_state["show_delete_confirmation"] = True

                    if submitted:
                        db.update_executive(
                            exec_id,
                            new_company_id,
                            new_name,
                            new_email,
                            new_tz,
                            new_seat if new_seat != "No Preference" else "",
                            "",  # hotel_loyalty removed
                            "",  # frequent_flyer_number removed
                            new_diet,
                            new_passport,
                            new_airline,
                            new_tsa,
                            new_meal if new_meal != "No Preference" else "",
                        )
                        st.success(f"✅ Executive '{new_name}' updated!")
                        st.session_state["profile_edit_mode"] = False
                        st.session_state["show_full_profile"] = False
                        st.rerun()
                    if cancel:
                        st.session_state["profile_edit_mode"] = False
                        st.rerun()

                    if st.session_state.get("show_delete_confirmation", False):
                        st.warning(
                            f"⚠️ Permanently delete executive '{profile['name']}'?"
                        )
                        trip_count = db.get_executive_trip_count(exec_id)
                        if trip_count > 0:
                            st.error(
                                f"⚠️ This executive has {trip_count} trip(s). They will also be deleted."
                            )
                        col_yes, col_no = st.columns(2)
                        with col_yes:
                            if st.button("✅ Yes, Delete", key="confirm_delete_modal"):
                                success, msg = db.delete_executive(exec_id, force=True)
                                if success:
                                    st.success(msg)
                                    st.session_state["show_full_profile"] = False
                                    st.session_state["profile_edit_mode"] = False
                                    st.session_state["show_delete_confirmation"] = False
                                    if "current_trip_id" in st.session_state:
                                        del st.session_state["current_trip_id"]
                                    if "trip_stops" in st.session_state:
                                        del st.session_state["trip_stops"]
                                    st.rerun()
                                else:
                                    st.error(msg)
                        with col_no:
                            if st.button("❌ Cancel", key="cancel_delete_modal"):
                                st.session_state["show_delete_confirmation"] = False
                                st.rerun()

            else:
                profile_data = db.get_full_executive_profile(exec_id)
                if profile_data:
                    for key, value in profile_data.items():
                        st.write(f"**{key}:** {value}")

                st.divider()
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✏️ Edit Executive", use_container_width=True):
                        st.session_state["profile_edit_mode"] = True
                        st.rerun()
                with col2:
                    if st.button("❌ Close Profile", use_container_width=True):
                        st.session_state["show_full_profile"] = False
                        st.session_state["profile_edit_mode"] = False
                        st.rerun()

    # Export buttons (collapsible)
    with st.sidebar.expander("📤 Export Profile", expanded=False):
        col_csv, col_doc, col_excel = st.columns(3)
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
                        key="csv_download_side",
                    )
        with col_doc:
            if st.button("📄 Word"):
                profile_data = db.get_full_executive_profile(exec_id)
                if profile_data:
                    doc_stream = doc_generator.generate_executive_profile_doc(
                        profile_data, exec_id, get_currency_symbol("USD")
                    )
                    st.download_button(
                        "⬇️ Download",
                        data=doc_stream,
                        file_name=f"{profile_data['Name']}_Profile.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml",
                        key="docx_download_side",
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
                            key="excel_download_side",
                        )

# --- Import / Restore ---
with st.sidebar.expander("💾 Import / Restore Database"):
    st.caption("Upload a file to restore or merge data.")

    import_mode = st.radio(
        "Import Mode",
        options=["Merge (Add to existing)", "Replace (Full restore)"],
        key="import_mode",
        help="Merge adds new data; Replace overwrites everything.",
    )

    uploaded_file = st.file_uploader(
        "Choose a file",
        type=["db", "json", "csv"],
        key="import_file",
        help="Supported: .db (replace), .json (merge), .csv (merge executives).",
    )

    if uploaded_file is not None:
        st.info(f"📄 {uploaded_file.name} ({uploaded_file.size / 1024:.1f} KB)")

        if st.button("🚀 Start Import", type="primary"):
            try:
                if import_mode == "Replace (Full restore)":
                    if uploaded_file.name.endswith(".db"):
                        with open("travel_planner.db", "wb") as f:
                            f.write(uploaded_file.getbuffer())
                        st.success("✅ Database replaced successfully! Refreshing...")
                        st.rerun()
                    else:
                        st.error("Replace mode only accepts .db files.")
                else:
                    if uploaded_file.name.endswith(".json"):
                        import json

                        data = json.load(uploaded_file)
                        result = db.merge_database_data(data)
                        st.success(result)
                    elif uploaded_file.name.endswith(".csv"):
                        content = uploaded_file.getvalue().decode("utf-8").splitlines()
                        reader = csv.DictReader(content)
                        result = db.import_executives_from_csv(reader)
                        st.success(result)
                    else:
                        st.error("Merge mode accepts .json or .csv files.")
            except Exception as e:
                st.error(f"Import failed: {e}")

# =========================================================
# MAIN AREA: TABS
# =========================================================
tab_names = [
    "✈️ Trip Planner",
    "👤 Executive Management",
    "📋 Trip Templates",
    "📊 Spending Dashboard",
]
default_tab = st.session_state.get("active_tab", "✈️ Trip Planner")
default_index = tab_names.index(default_tab) if default_tab in tab_names else 0
if "active_tab" in st.session_state:
    del st.session_state["active_tab"]

tab1, tab2, tab3, tab4 = st.tabs(tab_names)

# ------------------------------------------------------------------
# TAB 1: TRIP PLANNER (CREATE ONLY)
# ------------------------------------------------------------------
with tab1:
    if not profile:
        st.warning("Please add an executive in the 'Executive Management' tab first.")
        st.stop()

    # Executive dropdown
    exec_dropdown_options = {f"{name} (ID: {id})": id for id, name, _ in executives}
    trip_exec_label = st.selectbox(
        "👤 Executive for this Trip",
        options=list(exec_dropdown_options.keys()),
        key="create_trip_exec",
    )
    trip_exec_id = exec_dropdown_options[trip_exec_label]

    # Trip Name
    trip_purpose = st.text_input(
        "Trip Name / Purpose (e.g., 'Q3 Sales Tour')", key="create_trip_purpose"
    )

    # --- Overall Trip Dates ---
    col_start, col_end = st.columns(2)
    with col_start:
        overall_start = st.date_input(
            "Start Date*", value=datetime.now(), key="create_overall_start"
        )
    with col_end:
        overall_end = st.date_input(
            "End Date*",
            value=datetime.now() + timedelta(days=1),
            key="create_overall_end",
        )
    if overall_start and overall_end and overall_end >= overall_start:
        duration = (overall_end - overall_start).days
        st.caption(f"⏱️ Duration: {duration} day(s)")
    elif overall_start and overall_end:
        st.warning("End date must be after start date.")

    # Departure
    col_dep_city, col_dep_region = st.columns(2)
    with col_dep_city:
        departure_city = st.text_input("Departure City*", key="create_departure_city")
    with col_dep_region:
        departure_region = st.text_input(
            "Region / State (optional)", key="create_departure_region"
        )

    country_list = sorted([c.name for c in pycountry.countries])
    departure_country = st.selectbox(
        "Country (optional)",
        options=[""] + country_list,
        key="create_departure_country",
    )

    # --- Budget ---
    col_budget1, col_budget2 = st.columns(2)
    with col_budget1:
        budget = st.number_input(
            "Budget Amount",
            min_value=0.0,
            step=100.0,
            value=0.0,
            key="create_trip_budget",
        )
    with col_budget2:
        budget_currency_type = st.radio(
            "Budget is in:",
            options=["Display Currency", "Base Currency"],
            index=0,
            key="create_budget_currency_type",
        )

    # --- Currencies ---
    col_currency1, col_currency2 = st.columns(2)
    display_currency_options = ["USD", "EUR", "GBP", "NGN", "JPY", "BRL"]
    with col_currency1:
        trip_display_currency = st.selectbox(
            "Display Currency",
            options=display_currency_options,
            index=0,
            key="create_display_currency",
        )
    base_currency_options = [
        "USD",
        "EUR",
        "GBP",
        "NGN",
        "JPY",
        "BRL",
        "CAD",
        "AUD",
        "CHF",
        "CNY",
        "INR",
    ]
    with col_currency2:
        trip_base_currency = st.selectbox(
            "Base Currency (for reporting & conversion)",
            options=base_currency_options,
            index=0,
            key="create_base_currency",
        )

    # --- Status ---
    status_options = ["draft", "approved", "final"]
    trip_status = st.selectbox(
        "Trip Status",
        options=status_options,
        index=0,
        key="create_trip_status",
        help="Set the initial status of the trip. Draft = editable, Approved = locked, Final = locked.",
    )

    # Stops
    if "create_trip_stops" not in st.session_state:
        st.session_state["create_trip_stops"] = []

    if st.session_state["create_trip_stops"]:
        for idx, stop in enumerate(st.session_state["create_trip_stops"]):
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
                if st.button("🗑️", key=f"create_del_stop_{idx}"):
                    st.session_state["create_trip_stops"].pop(idx)
                    st.rerun()

    with st.expander("➕ Add Destination Stop"):
        col_city, col_country = st.columns(2)
        with col_city:
            new_city = st.text_input("City*", key="create_new_stop_city")
        with col_country:
            new_country = st.selectbox(
                "Country (optional)",
                options=[""] + country_list,
                key="create_new_stop_country",
            )
        col_region, col_notes = st.columns(2)
        with col_region:
            new_region = st.text_input(
                "Region / State (optional)", key="create_new_stop_region"
            )
        with col_notes:
            new_stop_notes = st.text_input(
                "Notes (optional)", key="create_new_stop_notes"
            )
        col_start, col_end = st.columns(2)
        with col_start:
            new_start = st.date_input(
                "Start Date*", value=datetime.now(), key="create_new_stop_start"
            )
        with col_end:
            new_end = st.date_input(
                "End Date*", value=datetime.now(), key="create_new_stop_end"
            )

        if st.button("➕ Add Stop", key="create_add_stop_button"):
            if new_city and new_start and new_end:
                st.session_state["create_trip_stops"].append(
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

    # --- Itinerary Items (optional) ---
    if "create_trip_items" not in st.session_state:
        st.session_state["create_trip_items"] = []

    if st.session_state["create_trip_items"]:
        for idx, item in enumerate(st.session_state["create_trip_items"]):
            col_i1, col_i2, col_i3, col_i4 = st.columns([3, 2, 1, 1])
            with col_i1:
                st.write(f"{item['description']} ({item['item_type']})")
            with col_i2:
                st.write(f"{item.get('cost',0):.2f} {item.get('cost_currency','USD')}")
            with col_i3:
                if st.button("✏️", key=f"create_edit_item_{idx}"):
                    st.session_state[f"create_editing_item_{idx}"] = True
            with col_i4:
                if st.button("🗑️", key=f"create_del_item_{idx}"):
                    st.session_state["create_trip_items"].pop(idx)
                    st.rerun()

            if st.session_state.get(f"create_editing_item_{idx}", False):
                with st.expander(f"Edit Item: {item['description']}", expanded=True):
                    with st.form(key=f"create_edit_item_form_{idx}"):
                        e_type = st.selectbox(
                            "Type",
                            options=(
                                [cat[1] for cat in db.get_all_categories()]
                                if db.get_all_categories()
                                else ["Flight", "Hotel", "Meeting", "Transport"]
                            ),
                            index=0,
                            key=f"create_e_type_{idx}",
                        )
                        e_desc = st.text_input(
                            "Description",
                            value=item["description"],
                            key=f"create_e_desc_{idx}",
                        )
                        e_start = st.datetime_input(
                            "Start",
                            value=datetime.fromisoformat(item["datetime_start"]),
                            key=f"create_e_start_{idx}",
                        )
                        e_end = st.datetime_input(
                            "End",
                            value=(
                                datetime.fromisoformat(item["datetime_end"])
                                if item["datetime_end"]
                                else datetime.now()
                            ),
                            key=f"create_e_end_{idx}",
                        )
                        e_loc = st.text_input(
                            "Location",
                            value=item.get("location", ""),
                            key=f"create_e_loc_{idx}",
                        )
                        e_cost = st.number_input(
                            "Cost",
                            value=float(item.get("cost", 0)),
                            key=f"create_e_cost_{idx}",
                        )
                        e_currency = st.selectbox(
                            "Currency",
                            options=["USD", "EUR", "GBP", "NGN", "JPY", "BRL"],
                            index=["USD", "EUR", "GBP", "NGN", "JPY", "BRL"].index(
                                item.get("cost_currency", "USD")
                            ),
                            key=f"create_e_currency_{idx}",
                        )
                        e_rate = st.number_input(
                            "Exchange Rate (1 base currency = X this currency)",
                            min_value=0.0,
                            step=0.01,
                            value=float(item.get("exchange_rate_snapshot", 1.0)),
                            key=f"create_e_rate_{idx}",
                        )
                        st.caption(
                            "💡 [Check current rates on XE.com](https://www.xe.com)"
                        )
                        e_confirmed = st.checkbox(
                            "Confirmed",
                            value=bool(item.get("is_confirmed", 0)),
                            key=f"create_e_confirmed_{idx}",
                        )
                        e_notes = st.text_area(
                            "Notes",
                            value=item.get("notes", ""),
                            key=f"create_e_notes_{idx}",
                        )
                        if st.form_submit_button("💾 Update Item"):
                            st.session_state["create_trip_items"][idx] = {
                                "item_type": e_type,
                                "description": e_desc,
                                "datetime_start": e_start.isoformat(),
                                "datetime_end": e_end.isoformat() if e_end else None,
                                "location": e_loc,
                                "cost": e_cost,
                                "cost_currency": e_currency,
                                "exchange_rate_snapshot": e_rate,
                                "is_confirmed": 1 if e_confirmed else 0,
                                "confirmation_code": item.get("confirmation_code", ""),
                                "notes": e_notes,
                            }
                            st.session_state[f"create_editing_item_{idx}"] = False
                            st.rerun()
                        if st.form_submit_button("❌ Cancel"):
                            st.session_state[f"create_editing_item_{idx}"] = False
                            st.rerun()

    with st.expander("➕ Add Itinerary Item"):
        with st.form(key="create_add_item_form"):
            n_type = st.selectbox(
                "Type",
                options=(
                    [cat[1] for cat in db.get_all_categories()]
                    if db.get_all_categories()
                    else ["Flight", "Hotel", "Meeting", "Transport"]
                ),
                key="create_n_type",
            )
            n_desc = st.text_input("Description", key="create_n_desc")
            n_start = st.datetime_input(
                "Start", value=datetime.now(), key="create_n_start"
            )
            n_end = st.datetime_input("End", value=datetime.now(), key="create_n_end")
            n_loc = st.text_input("Location", key="create_n_loc")
            n_cost = st.number_input(
                "Cost", min_value=0.0, value=0.0, key="create_n_cost"
            )
            n_currency = st.selectbox(
                "Currency",
                options=["USD", "EUR", "GBP", "NGN", "JPY", "BRL"],
                key="create_n_currency",
            )
            n_rate = st.number_input(
                "Exchange Rate (1 base currency = X this currency)",
                min_value=0.0,
                step=0.01,
                value=1.0,
                key="create_n_rate",
            )
            st.caption("💡 [Check current rates on XE.com](https://www.xe.com)")
            n_confirmed = st.checkbox("Confirmed", key="create_n_confirmed")
            n_notes = st.text_area("Notes", key="create_n_notes")
            if st.form_submit_button("➕ Add Item"):
                if n_desc and n_start:
                    st.session_state["create_trip_items"].append(
                        {
                            "item_type": n_type,
                            "description": n_desc,
                            "datetime_start": n_start.isoformat(),
                            "datetime_end": n_end.isoformat() if n_end else None,
                            "location": n_loc,
                            "cost": n_cost,
                            "cost_currency": n_currency,
                            "exchange_rate_snapshot": n_rate,
                            "is_confirmed": 1 if n_confirmed else 0,
                            "confirmation_code": "",
                            "notes": n_notes,
                        }
                    )
                    st.rerun()
                else:
                    st.warning("Description and Start Time are required.")

    # Create and Clear buttons
    col_clear, col_create = st.columns(2)
    with col_clear:
        if st.button("🗑️ Clear Form", key="clear_create_form"):
            st.session_state["create_trip_stops"] = []
            st.session_state["create_trip_items"] = []
            st.rerun()
    with col_create:
        if st.button("🚀 Create Trip", key="create_trip_button"):
            if trip_purpose and st.session_state["create_trip_stops"]:
                # Use the user-provided overall dates
                overall_start = overall_start.isoformat()
                overall_end = overall_end.isoformat()
                stop_cities = [
                    stop["city"] for stop in st.session_state["create_trip_stops"]
                ]
                dest_summary = " → ".join(stop_cities)

                existing_trips = duplicate_detection.find_duplicate_trips(
                    trip_exec_id, trip_purpose, overall_start, overall_end
                )
                if existing_trips:
                    st.warning(
                        "⚠️ You already have a trip with the same purpose and overlapping dates:"
                    )
                    for dup in existing_trips:
                        st.write(
                            f"- {dup['destination']} ({dup['start_date'][:10]} to {dup['end_date'][:10]})"
                        )
                    if not st.checkbox("Proceed anyway?", key="force_trip_create"):
                        st.stop()

                # Convert budget to base currency before storing
                if budget_currency_type == "Display Currency":
                    try:
                        from currency import get_exchange_rates

                        rates = get_exchange_rates(trip_base_currency)
                        rate = rates.get(trip_display_currency, 1.0)
                        budget_base = budget / rate
                    except:
                        budget_base = budget
                else:
                    budget_base = budget

                trip_id = db.create_or_get_trip(
                    trip_exec_id,
                    dest_summary,
                    overall_start,
                    overall_end,
                    trip_purpose,
                    trip_display_currency,
                    trip_base_currency,
                )
                db.update_trip_budget(trip_id, budget_base)
                db.update_trip_departure_details(
                    trip_id, departure_city, departure_region, departure_country
                )
                db.update_trip_status(trip_id, trip_status)

                db.delete_all_trip_stops(trip_id)
                for idx, stop in enumerate(st.session_state["create_trip_stops"]):
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

                # Add items
                valid_currencies = [trip_display_currency, trip_base_currency]
                for item in st.session_state["create_trip_items"]:
                    if item["cost_currency"] not in valid_currencies:
                        item["cost_currency"] = trip_display_currency
                    db.add_itinerary_item(
                        trip_id,
                        item["item_type"],
                        item["description"],
                        item["datetime_start"],
                        item["datetime_end"],
                        item.get("location", ""),
                        item.get("cost", 0),
                        item.get("confirmation_code", ""),
                        item.get("notes", ""),
                        item.get("is_confirmed", 0),
                        item["cost_currency"],
                        item.get("exchange_rate_snapshot", 1.0),
                    )

                # Clear the form
                st.session_state["create_trip_stops"] = []
                st.session_state["create_trip_items"] = []

                # Reset all form fields by removing their session state keys
                keys_to_clear = [
                    "create_trip_purpose",
                    "create_departure_city",
                    "create_departure_region",
                    "create_departure_country",
                    "create_trip_budget",
                    "create_display_currency",
                    "create_base_currency",
                    "create_trip_status",
                    "create_overall_start",
                    "create_overall_end",
                ]
                for key in keys_to_clear:
                    st.session_state.pop(key, None)

                st.success(
                    f"✅ Trip '{trip_purpose}' created successfully with status '{trip_status}'!"
                )
                st.rerun()
            else:
                st.warning("Enter a Trip Name and add at least one stop.")

# ------------------------------------------------------------------
# TAB 2: EXECUTIVE MANAGEMENT (ADD ONLY + ADD MEMBERSHIP OUTSIDE FORM)
# ------------------------------------------------------------------
with tab2:

    # Add Company
    st.subheader("Add Company")
    with st.form("add_company_form_tab", clear_on_submit=True):
        comp_name = st.text_input("Company Name", key="comp_name_tab")
        comp_cc = st.text_input("Default Cost Center (optional)", key="comp_cc_tab")
        comp_policy = st.text_area("Policy Notes (optional)", key="comp_policy_tab")
        if st.form_submit_button("Add Company"):
            if comp_name:
                db.add_company(comp_name, comp_cc, comp_policy)
                st.success(f"Company '{comp_name}' added!")
                st.rerun()
            else:
                st.warning("Company Name is required.")
    st.divider()

    # Add Executive
    st.subheader("Add Executive")
    companies = db.get_all_companies()
    company_options = {name: id for id, name in companies}
    tz_display_names, tz_map = get_timezone_dropdown_options()
    default_display = next(
        (n for n in tz_display_names if "America/New_York" in n), tz_display_names[0]
    )

    with st.form("add_exec_form_tab", clear_on_submit=True):
        exec_name = st.text_input("Full Name*", key="exec_name_tab")
        exec_email = st.text_input("Email", key="exec_email_tab")
        if companies:
            sel_company = st.selectbox(
                "Company*", list(company_options.keys()), key="exec_company_tab"
            )
            sel_company_id = company_options[sel_company]
        else:
            st.warning("Add a company first.")
            sel_company_id = None
        sel_tz = st.selectbox(
            "Timezone",
            tz_display_names,
            index=tz_display_names.index(default_display),
            key="exec_tz_tab",
        )
        exec_tz = tz_map[sel_tz]
        exec_seat = st.selectbox(
            "Seat Preference",
            ["No Preference", "Aisle", "Window", "Middle"],
            key="exec_seat_tab",
        )
        exec_diet = st.text_input("Dietary Restrictions", key="exec_diet_tab")
        exec_passport = st.text_input("Passport Number", key="exec_passport_tab")
        exec_airline = st.text_input("Preferred Airline", key="exec_airline_tab")
        exec_tsa = st.text_input("TSA PreCheck", key="exec_tsa_tab")
        exec_meal = st.selectbox(
            "Meal Preference",
            ["No Preference", "Vegetarian", "Vegan", "Kosher", "Halal", "Gluten-Free"],
            key="exec_meal_tab",
        )

        if st.form_submit_button("Add Executive"):
            if exec_name and sel_company_id:
                if exec_email:
                    existing = duplicate_detection.find_duplicate_executive(
                        exec_email, exec_name, sel_company_id
                    )
                    if existing:
                        st.warning(
                            "⚠️ An executive with the same email or name+company already exists:"
                        )
                        for dup in existing:
                            st.write(f"- {dup['name']} (ID: {dup['id']})")
                        if not st.checkbox("Add anyway?", key="force_add_exec_tab"):
                            st.stop()
                db.add_executive(
                    sel_company_id,
                    exec_name,
                    exec_email,
                    exec_tz,
                    exec_seat if exec_seat != "No Preference" else "",
                    "",  # hotel_loyalty removed
                    "",  # frequent_flyer_number removed
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

    # ---- Add New Membership (outside the Add Executive form) ----
    st.write("**Add New Membership:**")
    col_cat, col_name, col_num = st.columns(3)
    with col_cat:
        new_cat = st.selectbox(
            "Category", ["Airline", "Hotel", "Car Rental"], key="edit_mem_cat_tab"
        )
    with col_name:
        new_name = st.text_input("Program Name", key="edit_mem_name_tab")
    with col_num:
        new_num = st.text_input("Membership Number", key="edit_mem_num_tab")

    col_extra1, col_extra2 = st.columns(2)
    if new_cat == "Airline":
        with col_extra1:
            new_tier = st.text_input("Tier", key="edit_mem_tier_tab")
            new_alliance = st.text_input("Alliance", key="edit_mem_alliance_tab")
        with col_extra2:
            new_airport = st.text_input("Airport Code", key="edit_mem_airport_tab")
            new_notes_mem = st.text_area("Notes", key="edit_mem_notes_tab")
        new_alliance = new_alliance or None
        new_airport = new_airport or None
    elif new_cat == "Hotel":
        with col_extra1:
            new_tier = st.text_input("Status/Tier", key="edit_mem_tier_tab")
        with col_extra2:
            new_notes_mem = st.text_area("Notes", key="edit_mem_notes_tab")
        new_alliance = None
        new_airport = None
    else:  # Car
        with col_extra1:
            new_notes_mem = st.text_area("Notes", key="edit_mem_notes_tab")
        new_tier = None
        new_alliance = None
        new_airport = None

    if st.button("➕ Add Membership", key="edit_add_mem_tab"):
        if new_name and new_num:
            db.add_membership(
                exec_id,
                new_cat.lower(),
                new_name,
                new_num,
                tier=new_tier,
                alliance=new_alliance,
                airport_code=new_airport,
                notes=new_notes_mem,
            )
            st.success(f"Added {new_name}")
            st.rerun()
        else:
            st.warning("Fill in Program Name and Membership Number.")

    # Global duplicate executive scan (keep as a helper)
    st.divider()
    if st.button("🔍 Find Duplicate Executives (All)"):
        all_execs = db.get_all_executives()
        email_map = {}
        for e_id, name, company in all_execs:
            p = db.get_executive_profile(e_id)
            email = p.get("email", "")
            if email:
                email_map.setdefault(email, []).append((e_id, name, company))
        duplicates_found = False
        for email, entries in email_map.items():
            if len(entries) > 1:
                duplicates_found = True
                st.warning(f"Email {email} has {len(entries)} executives:")
                for e_id, name, company in entries:
                    st.write(f"  - {name} (ID: {e_id})")
        if not duplicates_found:
            st.success("No duplicate emails found.")

# ------------------------------------------------------------------
# TAB 3: TRIP TEMPLATES (unchanged)
# ------------------------------------------------------------------
with tab3:
    st.header("📋 Trip Templates")
    templates = db.get_trip_templates()
    if templates:
        st.write("**Saved Templates:**")
        for t in templates:
            col1, col2 = st.columns([4, 1])
            with col1:
                st.write(f"**{t['name']}**")
                st.caption(f"Created: {t['created_at'][:10]}")
                if st.button(f"👁️ Preview", key=f"preview_{t['id']}"):
                    st.session_state[f"preview_template_{t['id']}"] = True
                if st.session_state.get(f"preview_template_{t['id']}", False):
                    template_data = db.get_trip_template(t["id"])
                    if template_data:
                        st.write("**Departure:**")
                        st.write(f"City: {template_data.get('departure_city', 'N/A')}")
                        st.write(
                            f"Region: {template_data.get('departure_region', 'N/A')}"
                        )
                        st.write(
                            f"Country: {template_data.get('departure_country', 'N/A')}"
                        )
                        st.write("**Stops:**")
                        for stop in template_data.get("stops", []):
                            st.write(f"- {stop.get('city', '')}")
                        st.write("**Items:**")
                        for item in template_data.get("items", []):
                            st.write(
                                f"- {item.get('item_type', '')}: {item.get('description', '')}"
                            )
                        if st.button("Close Preview", key=f"close_preview_{t['id']}"):
                            st.session_state[f"preview_template_{t['id']}"] = False
                            st.rerun()
            with col2:
                if st.button("🗑️", key=f"del_template_tab_{t['id']}"):
                    db.delete_trip_template(t["id"])
                    st.rerun()
    else:
        st.caption("No templates saved yet.")

    if templates:
        st.divider()
        st.subheader("🚀 Create Trip from Template")
        template_options = {t["name"]: t["id"] for t in templates}
        selected_template_name = st.selectbox(
            "Select Template",
            list(template_options.keys()),
            key="template_selector_tab",
        )
        selected_template_id = template_options[selected_template_name]
        if selected_template_id:
            template_data = db.get_trip_template(selected_template_id)
            if template_data:
                with st.form("apply_template_form_tab"):
                    col1, col2 = st.columns(2)
                    with col1:
                        new_trip_name = st.text_input(
                            "Trip Name*",
                            value=f"{selected_template_name} - {datetime.now().strftime('%Y-%m-%d')}",
                        )
                        new_start = st.date_input(
                            "Start Date*", value=datetime.now() + timedelta(days=7)
                        )
                    with col2:
                        new_budget = st.number_input(
                            "Budget", min_value=0.0, step=100.0, value=1000.0
                        )
                        new_end = st.date_input(
                            "End Date*", value=datetime.now() + timedelta(days=10)
                        )
                    submitted = st.form_submit_button("🚀 Create Trip from Template")
                    if submitted:
                        if new_trip_name and new_start and new_end:
                            new_trip_id = db.apply_trip_template(
                                selected_template_id,
                                exec_id,
                                new_trip_name,
                                new_start,
                                new_end,
                                new_budget,
                            )
                            if new_trip_id:
                                db.update_trip_status(new_trip_id, "draft")
                                st.session_state["current_trip_id"] = new_trip_id
                                st.success(
                                    f"✅ Trip '{new_trip_name}' created from template!"
                                )
                                st.rerun()
                            else:
                                st.error("Failed to create trip from template.")
                        else:
                            st.warning("Please fill in all required fields.")

# ------------------------------------------------------------------
# TAB 4: SPENDING DASHBOARD (with mass delete)
# ------------------------------------------------------------------
with tab4:
    st.header("📊 Spending Dashboard (All Trips)")
    st.subheader("Filter & View Aggregate Spending")
    col_dash1, col_dash2 = st.columns(2)
    with col_dash1:
        exec_filter_options = ["All"] + [
            f"{name} (ID: {id})" for id, name, _ in executives
        ]
        exec_filter = st.selectbox(
            "Filter by Executive", exec_filter_options, key="dash_filter_tab"
        )
        exec_id_filter = (
            None
            if exec_filter == "All"
            else int(exec_filter.split("(ID: ")[1].rstrip(")"))
        )
    with col_dash2:
        date_range = st.date_input(
            "Date Range (optional)", value=[], key="dash_date_tab"
        )
    start_filter = date_range[0].isoformat() if len(date_range) > 0 else None
    end_filter = date_range[1].isoformat() if len(date_range) > 1 else None

    summary_data = db.get_spending_summary(
        exec_id=exec_id_filter, start_date=start_filter, end_date=end_filter
    )

    if "selected_trip_ids" not in st.session_state:
        st.session_state.selected_trip_ids = set()

    if summary_data:
        total_budget = sum(t["budget"] for t in summary_data)
        total_spent = sum(t["total_spent"] for t in summary_data)
        total_confirmed = sum(t["confirmed_spent"] for t in summary_data)
        total_estimated = sum(t["estimated_spent"] for t in summary_data)
        dashboard_symbol = get_currency_symbol("USD")

        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        col_m1.metric("Total Trips", len(summary_data))
        col_m2.metric("Total Budget", f"{dashboard_symbol}{total_budget:,.2f}")
        col_m3.metric("Total Spent", f"{dashboard_symbol}{total_spent:,.2f}")
        col_m4.metric("Total Confirmed", f"{dashboard_symbol}{total_confirmed:,.2f}")

        st.subheader("Trip-Level Breakdown")

        # --- Mass delete controls ---
        col_select_all, col_delete_selected = st.columns([1, 3])
        with col_select_all:
            all_ids = [trip["trip_id"] for trip in summary_data]
            all_selected = all(
                id in st.session_state.selected_trip_ids for id in all_ids
            )
            if st.checkbox("Select All", value=all_selected, key="select_all_checkbox"):
                if not all_selected:
                    st.session_state.selected_trip_ids = set(all_ids)
                    st.rerun()
            else:
                if all_selected:
                    st.session_state.selected_trip_ids = set()
                    st.rerun()

        with col_delete_selected:
            if st.session_state.selected_trip_ids:
                st.write(
                    f"**{len(st.session_state.selected_trip_ids)}** trip(s) selected."
                )
                if st.button("🗑️ Delete Selected", type="primary"):
                    st.session_state["confirm_mass_delete"] = True
            else:
                st.write("No trips selected.")

        if st.session_state.get("confirm_mass_delete", False):
            st.warning(
                f"⚠️ Permanently delete {len(st.session_state.selected_trip_ids)} selected trip(s)?"
            )
            col_yes, col_no = st.columns(2)
            with col_yes:
                if st.button("✅ Yes, Delete All", key="confirm_mass_delete_yes"):
                    trip_ids_to_delete = list(st.session_state.selected_trip_ids)
                    db.delete_trips(trip_ids_to_delete)
                    st.session_state.selected_trip_ids = set()
                    st.session_state["confirm_mass_delete"] = False
                    st.success(f"Deleted {len(trip_ids_to_delete)} trip(s).")
                    st.rerun()
            with col_no:
                if st.button("❌ Cancel", key="confirm_mass_delete_no"):
                    st.session_state["confirm_mass_delete"] = False
                    st.rerun()

        # --- Table header ---
        header_cols = st.columns([0.5, 1.5, 1.5, 1.5, 1, 1, 1, 1, 1, 0.8, 0.8])
        with header_cols[0]:
            st.write("")
        with header_cols[1]:
            st.write("**Executive**")
        with header_cols[2]:
            st.write("**Company**")
        with header_cols[3]:
            st.write("**Destination**")
        with header_cols[4]:
            st.write("**Budget**")
        with header_cols[5]:
            st.write("**Total Spent**")
        with header_cols[6]:
            st.write("**Confirmed**")
        with header_cols[7]:
            st.write("**Estimated**")
        with header_cols[8]:
            st.write("**Status**")
        with header_cols[9]:
            st.write("**Open**")
        with header_cols[10]:
            st.write("**Delete**")

        # --- Loop through trips ---
        for trip in summary_data:
            trip_base_currency = trip.get("base_currency", "USD")
            trip_symbol = get_currency_symbol(trip_base_currency)
            trip_id = trip["trip_id"]

            with st.container():
                cols = st.columns([0.5, 1.5, 1.5, 1.5, 1, 1, 1, 1, 1, 0.8, 0.8])

                with cols[0]:
                    is_checked = trip_id in st.session_state.selected_trip_ids
                    if st.checkbox("", value=is_checked, key=f"sel_{trip_id}"):
                        st.session_state.selected_trip_ids.add(trip_id)
                    else:
                        st.session_state.selected_trip_ids.discard(trip_id)

                with cols[1]:
                    st.write(trip["executive_name"])
                with cols[2]:
                    st.write(trip["company_name"])
                with cols[3]:
                    st.write(trip["destination"])
                with cols[4]:
                    st.write(f"{trip_symbol}{trip['budget']:.2f}")
                with cols[5]:
                    st.write(f"{trip_symbol}{trip['total_spent']:.2f}")
                with cols[6]:
                    st.write(f"{trip_symbol}{trip['confirmed_spent']:.2f}")
                with cols[7]:
                    st.write(f"{trip_symbol}{trip['estimated_spent']:.2f}")
                with cols[8]:
                    status = trip["status"]
                    st.write(
                        "📝 Draft"
                        if status == "draft"
                        else (
                            "✅ Approved"
                            if status == "approved"
                            else "📄 Final" if status == "final" else status
                        )
                    )
                with cols[9]:
                    # Full edit modal
                    with st.popover("📂", use_container_width=True):
                        trip_id_modal = trip["trip_id"]
                        trip_modal_data = db.get_trip(trip_id_modal)
                        if trip_modal_data:
                            st.subheader(
                                f"✈️ Edit Trip: {trip_modal_data.get('purpose', 'Untitled')}"
                            )

                            if f"modal_stops_{trip_id_modal}" not in st.session_state:
                                st.session_state[f"modal_stops_{trip_id_modal}"] = (
                                    db.get_trip_stops(trip_id_modal)
                                )
                            if f"modal_items_{trip_id_modal}" not in st.session_state:
                                st.session_state[f"modal_items_{trip_id_modal}"] = (
                                    db.get_items_for_trip(trip_id_modal)
                                )

                            with st.form(key=f"edit_trip_form_{trip_id_modal}"):
                                new_purpose = st.text_input(
                                    "Trip Name",
                                    value=trip_modal_data.get("purpose", ""),
                                    key=f"modal_purpose_{trip_id_modal}",
                                )

                                col_dep1, col_dep2 = st.columns(2)
                                with col_dep1:
                                    new_dep_city = st.text_input(
                                        "Departure City",
                                        value=trip_modal_data.get("departure_city", ""),
                                        key=f"modal_dep_city_{trip_id_modal}",
                                    )
                                with col_dep2:
                                    new_dep_region = st.text_input(
                                        "Departure Region",
                                        value=trip_modal_data.get(
                                            "departure_region", ""
                                        ),
                                        key=f"modal_dep_region_{trip_id_modal}",
                                    )
                                new_dep_country = st.selectbox(
                                    "Departure Country",
                                    options=[""] + country_list,
                                    index=(
                                        ([""] + country_list).index(
                                            trip_modal_data.get("departure_country", "")
                                        )
                                        if trip_modal_data.get("departure_country")
                                        in ([""] + country_list)
                                        else 0
                                    ),
                                    key=f"modal_dep_country_{trip_id_modal}",
                                )

                                st.write("**Budget**")
                                col_bud1, col_bud2 = st.columns(2)
                                with col_bud1:
                                    display_cur = trip_modal_data.get(
                                        "display_currency", "USD"
                                    )
                                    base_cur = trip_modal_data.get(
                                        "base_currency", "USD"
                                    )
                                    budget_base = trip_modal_data.get("budget", 0.0)
                                    try:
                                        from currency import get_exchange_rates

                                        rates = get_exchange_rates(base_cur)
                                        rate = rates.get(display_cur, 1.0)
                                        budget_display = budget_base * rate
                                    except:
                                        budget_display = budget_base
                                    edit_currency_type = st.radio(
                                        "Edit budget in:",
                                        options=["Display Currency", "Base Currency"],
                                        index=0,
                                        key=f"modal_budget_currency_type_{trip_id_modal}",
                                    )
                                    if edit_currency_type == "Display Currency":
                                        budget_value = budget_display
                                    else:
                                        budget_value = budget_base
                                    new_budget = st.number_input(
                                        "Budget Amount",
                                        min_value=0.0,
                                        step=100.0,
                                        value=float(budget_value),
                                        key=f"modal_budget_{trip_id_modal}",
                                    )
                                with col_bud2:
                                    st.write(
                                        f"Display: {display_cur} | Base: {base_cur}"
                                    )

                                col_cur1, col_cur2 = st.columns(2)
                                with col_cur1:
                                    new_display_currency = st.selectbox(
                                        "Display Currency",
                                        options=display_currency_options,
                                        index=(
                                            display_currency_options.index(
                                                trip_modal_data.get(
                                                    "display_currency", "USD"
                                                )
                                            )
                                            if trip_modal_data.get("display_currency")
                                            in display_currency_options
                                            else 0
                                        ),
                                        key=f"modal_display_currency_{trip_id_modal}",
                                    )
                                with col_cur2:
                                    new_base_currency = st.selectbox(
                                        "Base Currency",
                                        options=base_currency_options,
                                        index=(
                                            base_currency_options.index(
                                                trip_modal_data.get(
                                                    "base_currency", "USD"
                                                )
                                            )
                                            if trip_modal_data.get("base_currency")
                                            in base_currency_options
                                            else 0
                                        ),
                                        key=f"modal_base_currency_{trip_id_modal}",
                                    )

                                current_status = trip_modal_data.get("status", "draft")
                                new_status = st.selectbox(
                                    "Status",
                                    options=["draft", "approved", "final"],
                                    index=(
                                        ["draft", "approved", "final"].index(
                                            current_status
                                        )
                                        if current_status
                                        in ["draft", "approved", "final"]
                                        else 0
                                    ),
                                    key=f"modal_status_{trip_id_modal}",
                                )

                                submitted = st.form_submit_button("💾 Save Changes")
                                if submitted:
                                    if edit_currency_type == "Display Currency":
                                        try:
                                            from currency import get_exchange_rates

                                            rates = get_exchange_rates(
                                                new_base_currency
                                            )
                                            rate = rates.get(new_display_currency, 1.0)
                                            budget_base = new_budget / rate
                                        except:
                                            budget_base = new_budget
                                    else:
                                        budget_base = new_budget

                                    db.update_trip_purpose(trip_id_modal, new_purpose)
                                    db.update_trip_budget(trip_id_modal, budget_base)
                                    db.update_trip_departure_details(
                                        trip_id_modal,
                                        new_dep_city,
                                        new_dep_region,
                                        new_dep_country,
                                    )
                                    db.update_trip_currencies(
                                        trip_id_modal,
                                        new_base_currency,
                                        new_display_currency,
                                    )
                                    db.update_trip_status(trip_id_modal, new_status)

                                    db.delete_all_trip_stops(trip_id_modal)
                                    for idx, stop in enumerate(
                                        st.session_state[f"modal_stops_{trip_id_modal}"]
                                    ):
                                        db.add_trip_stop(
                                            trip_id_modal,
                                            idx + 1,
                                            stop["city"],
                                            stop.get("country", ""),
                                            stop.get("region", ""),
                                            stop["start_date"],
                                            stop["end_date"],
                                            stop.get("notes", ""),
                                        )

                                    valid_currencies = [
                                        new_display_currency,
                                        new_base_currency,
                                    ]
                                    conn = sqlite3.connect(db.DB_PATH)
                                    c = conn.cursor()
                                    c.execute(
                                        "DELETE FROM itinerary_items WHERE trip_id = ?",
                                        (trip_id_modal,),
                                    )
                                    conn.commit()
                                    conn.close()

                                    for item in st.session_state[
                                        f"modal_items_{trip_id_modal}"
                                    ]:
                                        if (
                                            item["cost_currency"]
                                            not in valid_currencies
                                        ):
                                            item["cost_currency"] = new_display_currency
                                        db.add_itinerary_item(
                                            trip_id_modal,
                                            item["item_type"],
                                            item["description"],
                                            item["datetime_start"],
                                            item["datetime_end"],
                                            item.get("location", ""),
                                            item.get("cost", 0),
                                            item.get("confirmation_code", ""),
                                            item.get("notes", ""),
                                            item.get("is_confirmed", 0),
                                            item["cost_currency"],
                                            item.get("exchange_rate_snapshot", 1.0),
                                        )

                                    st.success("✅ Trip updated successfully!")
                                    st.session_state.pop(
                                        f"modal_stops_{trip_id_modal}", None
                                    )
                                    st.session_state.pop(
                                        f"modal_items_{trip_id_modal}", None
                                    )
                                    st.rerun()

                            # Stops management
                            st.write("**📍 Stops**")
                            stops = st.session_state[f"modal_stops_{trip_id_modal}"]
                            for idx, stop in enumerate(stops):
                                col_s1, col_s2, col_s3, col_s4, col_s5 = st.columns(
                                    [2, 2, 2, 2, 1]
                                )
                                with col_s1:
                                    st.write(f"**{idx+1}.** {stop['city']}")
                                with col_s2:
                                    loc_parts = []
                                    if stop.get("region"):
                                        loc_parts.append(stop["region"])
                                    if stop.get("country"):
                                        loc_parts.append(stop["country"])
                                    st.write(", ".join(loc_parts) if loc_parts else "")
                                with col_s3:
                                    st.write(
                                        f"{format_date_display(stop['start_date'])} → {format_date_display(stop['end_date'])}"
                                    )
                                with col_s4:
                                    st.write(stop.get("notes", "")[:30])
                                with col_s5:
                                    if st.button(
                                        "🗑️",
                                        key=f"modal_del_stop_{trip_id_modal}_{idx}",
                                    ):
                                        st.session_state[
                                            f"modal_stops_{trip_id_modal}"
                                        ].pop(idx)
                                        st.rerun()

                            with st.expander("➕ Add Stop"):
                                col_sc1, col_sc2 = st.columns(2)
                                with col_sc1:
                                    new_stop_city = st.text_input(
                                        "City*",
                                        key=f"modal_new_stop_city_{trip_id_modal}",
                                    )
                                with col_sc2:
                                    new_stop_country = st.selectbox(
                                        "Country",
                                        options=[""] + country_list,
                                        key=f"modal_new_stop_country_{trip_id_modal}",
                                    )
                                col_sr, col_sn = st.columns(2)
                                with col_sr:
                                    new_stop_region = st.text_input(
                                        "Region",
                                        key=f"modal_new_stop_region_{trip_id_modal}",
                                    )
                                with col_sn:
                                    new_stop_notes = st.text_input(
                                        "Notes",
                                        key=f"modal_new_stop_notes_{trip_id_modal}",
                                    )
                                col_ss, col_se = st.columns(2)
                                with col_ss:
                                    new_stop_start = st.date_input(
                                        "Start Date*",
                                        value=datetime.now(),
                                        key=f"modal_new_stop_start_{trip_id_modal}",
                                    )
                                with col_se:
                                    new_stop_end = st.date_input(
                                        "End Date*",
                                        value=datetime.now(),
                                        key=f"modal_new_stop_end_{trip_id_modal}",
                                    )
                                if st.button(
                                    "➕ Add Stop", key=f"modal_add_stop_{trip_id_modal}"
                                ):
                                    if (
                                        new_stop_city
                                        and new_stop_start
                                        and new_stop_end
                                    ):
                                        st.session_state[
                                            f"modal_stops_{trip_id_modal}"
                                        ].append(
                                            {
                                                "city": new_stop_city,
                                                "country": new_stop_country,
                                                "region": new_stop_region,
                                                "start_date": new_stop_start.isoformat(),
                                                "end_date": new_stop_end.isoformat(),
                                                "notes": new_stop_notes,
                                            }
                                        )
                                        st.rerun()
                                    else:
                                        st.warning(
                                            "City, Start Date, and End Date are required."
                                        )

                            # Items management
                            st.write("**📋 Itinerary Items**")
                            display_cur_modal = trip_modal_data.get(
                                "display_currency", "USD"
                            )
                            base_cur_modal = trip_modal_data.get("base_currency", "USD")
                            valid_currency_options = [display_cur_modal, base_cur_modal]

                            items = st.session_state[f"modal_items_{trip_id_modal}"]
                            for idx, item in enumerate(items):
                                col_i1, col_i2, col_i3, col_i4 = st.columns(
                                    [3, 2, 1, 1]
                                )
                                with col_i1:
                                    st.write(
                                        f"{item['description']} ({item['item_type']})"
                                    )
                                with col_i2:
                                    st.write(
                                        f"{item.get('cost',0):.2f} {item.get('cost_currency','USD')}"
                                    )
                                with col_i3:
                                    if st.button(
                                        "✏️",
                                        key=f"modal_edit_item_{trip_id_modal}_{idx}",
                                    ):
                                        st.session_state[
                                            f"modal_editing_item_{trip_id_modal}_{idx}"
                                        ] = True
                                with col_i4:
                                    if st.button(
                                        "🗑️",
                                        key=f"modal_del_item_{trip_id_modal}_{idx}",
                                    ):
                                        st.session_state[
                                            f"modal_items_{trip_id_modal}"
                                        ].pop(idx)
                                        st.rerun()

                                if st.session_state.get(
                                    f"modal_editing_item_{trip_id_modal}_{idx}", False
                                ):
                                    with st.expander(
                                        f"Edit Item: {item['description']}",
                                        expanded=True,
                                    ):
                                        with st.form(
                                            key=f"edit_item_form_{trip_id_modal}_{idx}"
                                        ):
                                            e_type = st.selectbox(
                                                "Type",
                                                options=(
                                                    [
                                                        cat[1]
                                                        for cat in db.get_all_categories()
                                                    ]
                                                    if db.get_all_categories()
                                                    else [
                                                        "Flight",
                                                        "Hotel",
                                                        "Meeting",
                                                        "Transport",
                                                    ]
                                                ),
                                                index=0,
                                                key=f"modal_e_type_{trip_id_modal}_{idx}",
                                            )
                                            e_desc = st.text_input(
                                                "Description",
                                                value=item["description"],
                                                key=f"modal_e_desc_{trip_id_modal}_{idx}",
                                            )
                                            e_start = st.datetime_input(
                                                "Start",
                                                value=datetime.fromisoformat(
                                                    item["datetime_start"]
                                                ),
                                                key=f"modal_e_start_{trip_id_modal}_{idx}",
                                            )
                                            e_end = st.datetime_input(
                                                "End",
                                                value=(
                                                    datetime.fromisoformat(
                                                        item["datetime_end"]
                                                    )
                                                    if item["datetime_end"]
                                                    else datetime.now()
                                                ),
                                                key=f"modal_e_end_{trip_id_modal}_{idx}",
                                            )
                                            e_loc = st.text_input(
                                                "Location",
                                                value=item.get("location", ""),
                                                key=f"modal_e_loc_{trip_id_modal}_{idx}",
                                            )
                                            e_cost = st.number_input(
                                                "Cost",
                                                value=float(item.get("cost", 0)),
                                                key=f"modal_e_cost_{trip_id_modal}_{idx}",
                                            )
                                            e_currency = st.selectbox(
                                                "Currency",
                                                options=valid_currency_options,
                                                index=(
                                                    valid_currency_options.index(
                                                        item.get("cost_currency", "USD")
                                                    )
                                                    if item.get("cost_currency", "USD")
                                                    in valid_currency_options
                                                    else 0
                                                ),
                                                key=f"modal_e_currency_{trip_id_modal}_{idx}",
                                            )
                                            e_rate = st.number_input(
                                                "Exchange Rate (1 base currency = X this currency)",
                                                min_value=0.0,
                                                step=0.01,
                                                value=float(
                                                    item.get(
                                                        "exchange_rate_snapshot", 1.0
                                                    )
                                                ),
                                                key=f"modal_e_rate_{trip_id_modal}_{idx}",
                                            )
                                            st.caption(
                                                "💡 [Check current rates on XE.com](https://www.xe.com)"
                                            )
                                            e_confirmed = st.checkbox(
                                                "Confirmed",
                                                value=bool(item.get("is_confirmed", 0)),
                                                key=f"modal_e_confirmed_{trip_id_modal}_{idx}",
                                            )
                                            e_notes = st.text_area(
                                                "Notes",
                                                value=item.get("notes", ""),
                                                key=f"modal_e_notes_{trip_id_modal}_{idx}",
                                            )
                                            if st.form_submit_button("💾 Update Item"):
                                                st.session_state[
                                                    f"modal_items_{trip_id_modal}"
                                                ][idx] = {
                                                    "item_type": e_type,
                                                    "description": e_desc,
                                                    "datetime_start": e_start.isoformat(),
                                                    "datetime_end": (
                                                        e_end.isoformat()
                                                        if e_end
                                                        else None
                                                    ),
                                                    "location": e_loc,
                                                    "cost": e_cost,
                                                    "cost_currency": e_currency,
                                                    "exchange_rate_snapshot": e_rate,
                                                    "is_confirmed": (
                                                        1 if e_confirmed else 0
                                                    ),
                                                    "confirmation_code": item.get(
                                                        "confirmation_code", ""
                                                    ),
                                                    "notes": e_notes,
                                                }
                                                st.session_state[
                                                    f"modal_editing_item_{trip_id_modal}_{idx}"
                                                ] = False
                                                st.rerun()
                                            if st.form_submit_button("❌ Cancel"):
                                                st.session_state[
                                                    f"modal_editing_item_{trip_id_modal}_{idx}"
                                                ] = False
                                                st.rerun()

                            with st.expander("➕ Add Item"):
                                with st.form(key=f"add_item_form_{trip_id_modal}"):
                                    n_type = st.selectbox(
                                        "Type",
                                        options=(
                                            [cat[1] for cat in db.get_all_categories()]
                                            if db.get_all_categories()
                                            else [
                                                "Flight",
                                                "Hotel",
                                                "Meeting",
                                                "Transport",
                                            ]
                                        ),
                                        key=f"modal_n_type_{trip_id_modal}",
                                    )
                                    n_desc = st.text_input(
                                        "Description",
                                        key=f"modal_n_desc_{trip_id_modal}",
                                    )
                                    n_start = st.datetime_input(
                                        "Start",
                                        value=datetime.now(),
                                        key=f"modal_n_start_{trip_id_modal}",
                                    )
                                    n_end = st.datetime_input(
                                        "End",
                                        value=datetime.now(),
                                        key=f"modal_n_end_{trip_id_modal}",
                                    )
                                    n_loc = st.text_input(
                                        "Location", key=f"modal_n_loc_{trip_id_modal}"
                                    )
                                    n_cost = st.number_input(
                                        "Cost",
                                        min_value=0.0,
                                        value=0.0,
                                        key=f"modal_n_cost_{trip_id_modal}",
                                    )
                                    n_currency = st.selectbox(
                                        "Currency",
                                        options=valid_currency_options,
                                        key=f"modal_n_currency_{trip_id_modal}",
                                    )
                                    n_rate = st.number_input(
                                        "Exchange Rate (1 base currency = X this currency)",
                                        min_value=0.0,
                                        step=0.01,
                                        value=1.0,
                                        key=f"modal_n_rate_{trip_id_modal}",
                                    )
                                    st.caption(
                                        "💡 [Check current rates on XE.com](https://www.xe.com)"
                                    )
                                    n_confirmed = st.checkbox(
                                        "Confirmed",
                                        key=f"modal_n_confirmed_{trip_id_modal}",
                                    )
                                    n_notes = st.text_area(
                                        "Notes", key=f"modal_n_notes_{trip_id_modal}"
                                    )
                                    if st.form_submit_button("➕ Add Item"):
                                        if n_desc and n_start:
                                            st.session_state[
                                                f"modal_items_{trip_id_modal}"
                                            ].append(
                                                {
                                                    "item_type": n_type,
                                                    "description": n_desc,
                                                    "datetime_start": n_start.isoformat(),
                                                    "datetime_end": (
                                                        n_end.isoformat()
                                                        if n_end
                                                        else None
                                                    ),
                                                    "location": n_loc,
                                                    "cost": n_cost,
                                                    "cost_currency": n_currency,
                                                    "exchange_rate_snapshot": n_rate,
                                                    "is_confirmed": (
                                                        1 if n_confirmed else 0
                                                    ),
                                                    "confirmation_code": "",
                                                    "notes": n_notes,
                                                }
                                            )
                                            st.rerun()
                                        else:
                                            st.warning(
                                                "Description and Start Time are required."
                                            )
                        else:
                            st.warning("Trip data not found.")
                with cols[10]:
                    if st.button("🗑️", key=f"del_trip_dash_{trip_id}"):
                        st.session_state[f"confirm_del_trip_{trip_id}"] = True

                if st.session_state.get(f"confirm_del_trip_{trip_id}", False):
                    st.warning(f"⚠️ Permanently delete trip to {trip['destination']}?")
                    col_yes, col_no = st.columns(2)
                    with col_yes:
                        if st.button("✅ Yes", key=f"confirm_yes_dash_{trip_id}"):
                            db.delete_trip(trip_id)
                            st.session_state.selected_trip_ids.discard(trip_id)
                            st.session_state.pop(f"confirm_del_trip_{trip_id}", None)
                            st.success("Trip deleted.")
                            st.rerun()
                    with col_no:
                        if st.button("❌ Cancel", key=f"confirm_no_dash_{trip_id}"):
                            st.session_state.pop(f"confirm_del_trip_{trip_id}", None)
                            st.rerun()
                st.divider()

        # --- Export Data ---
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
            rows_with_currency = []
            for trip in summary_data:
                trip_base = trip.get("base_currency", "USD")
                sym = get_currency_symbol(trip_base)
                rows_with_currency.append(
                    [
                        trip["executive_name"],
                        trip["company_name"],
                        trip["destination"],
                        f"{sym}{trip['budget']:.2f}",
                        f"{sym}{trip['total_spent']:.2f}",
                        f"{sym}{trip['confirmed_spent']:.2f}",
                        f"{sym}{trip['estimated_spent']:.2f}",
                        trip["status"],
                        trip_base,
                    ]
                )
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
                key="dash_csv_tab",
            )

        with col_exp2:
            if st.button("📄 Export Spending Report (Word)", key="dash_report_tab"):
                doc_stream = doc_generator.generate_spending_report_doc(
                    exec_filter if exec_filter != "All" else "All Executives",
                    summary_data,
                    start_filter,
                    end_filter,
                    get_currency_symbol("USD"),
                    base_currency="USD",
                )
                st.download_button(
                    "⬇️ Download Word Report",
                    data=doc_stream,
                    file_name=f"spending_report_{datetime.now().strftime('%Y%m%d')}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml",
                    key="dash_report_download_tab",
                )

        with col_exp3:
            if st.button("📊 Export to Excel", key="dash_excel_tab"):
                excel_stream = export_spending_to_excel(
                    summary_data, get_currency_symbol("USD"), "USD", base_currency="USD"
                )
                if excel_stream:
                    st.download_button(
                        "⬇️ Download .xlsx",
                        data=excel_stream,
                        file_name=f"spending_summary_{datetime.now().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="dash_excel_download_tab",
                    )
    else:
        st.info("No trips found matching the filters.")
