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
    button[data-baseweb="tab"] {
        background-color: #f0f2f6;
        border-radius: 20px 20px 0 0;
        padding: 8px 20px;
        font-weight: 500;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        background-color: #87CEEB;
        color: white;
    }
</style>
""",
    unsafe_allow_html=True,
)

# --- Session State ---
if "upload_counter" not in st.session_state:
    st.session_state.upload_counter = 0
if "reset_form" not in st.session_state:
    st.session_state.reset_form = False
if "tab_control" not in st.session_state:
    st.session_state.tab_control = 0
if "show_exec_dialog" not in st.session_state:
    st.session_state.show_exec_dialog = False
if "show_edit_trip_dashboard" not in st.session_state:
    st.session_state.show_edit_trip_dashboard = False
if "current_trip_id" not in st.session_state:
    st.session_state.current_trip_id = None
if "editing_trip_id" not in st.session_state:
    st.session_state.editing_trip_id = None

# Separate stops for inline and modal
if "trip_stops_inline" not in st.session_state:
    st.session_state.trip_stops_inline = []
if "trip_stops_modal" not in st.session_state:
    st.session_state.trip_stops_modal = []

st.title("Executive Travel Planner")
db.init_db()

# --- Reset flag processing (runs before widgets) ---
if st.session_state.get("reset_form", False):
    # Reset inline form keys
    inline_defaults = {
        "trip_purpose_input_inline": "",
        "departure_city_input_inline": "",
        "departure_region_input_inline": "",
        "departure_country_input_inline": "",
        "trip_display_currency_inline": "USD",
        "trip_base_currency_inline": "USD",
        "display_exchange_rate_inline": 1.0,
        "budget_currency_label_inline": "Base Currency (USD)",
        "trip_budget_input_inline": 0.0,
    }
    for key, default in inline_defaults.items():
        st.session_state[key] = default
    # Reset modal keys (if any)
    modal_defaults = {
        "trip_purpose_input_modal": "",
        "departure_city_input_modal": "",
        "departure_region_input_modal": "",
        "departure_country_input_modal": "",
        "trip_display_currency_modal": "USD",
        "trip_base_currency_modal": "USD",
        "display_exchange_rate_modal": 1.0,
        "budget_currency_label_modal": "Base Currency (USD)",
        "trip_budget_input_modal": 0.0,
    }
    for key, default in modal_defaults.items():
        st.session_state[key] = default

    st.session_state.pop("current_trip_id", None)
    st.session_state.pop("trip_destination_summary", None)
    st.session_state["trip_stops_inline"] = []
    st.session_state["trip_stops_modal"] = []
    st.session_state["reset_form"] = False
    st.rerun()

# =========================================================
# SIDEBAR
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
            st.session_state.tab_control = 1
            st.session_state.show_exec_dialog = True
            st.rerun()

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
                            "⬇️ Download",
                            data=excel_stream,
                            file_name=f"{profile_data['Name']}_Profile.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key="excel_download_side",
                        )

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
# FUNCTIONS TO RENDER FORMS
# =========================================================


def render_trip_setup_form(
    is_editing,
    trip_data,
    trip_id,
    trip_exec_label,
    trip_exec_id,
    is_draft,
    exec_id,
    executives,
    country_list,
    key_suffix="inline",
):
    """
    Render the trip setup form (used both inline and in modal).
    key_suffix: "inline" or "modal" to avoid duplicate keys.
    """
    # Use different session state keys for stops based on suffix
    stops_key = f"trip_stops_{key_suffix}"
    stops = st.session_state.get(stops_key, [])

    # Trip Name
    trip_purpose = st.text_input(
        "Trip Name / Purpose (e.g., 'Q3 Sales Tour')",
        value=trip_data.get("purpose", "") if is_editing and trip_data else "",
        disabled=not is_draft,
        key=f"trip_purpose_input_{key_suffix}",
    )

    # Departure
    st.subheader("📍 Departure City / Home Base")
    col_dep_city, col_dep_region = st.columns(2)
    with col_dep_city:
        departure_city = st.text_input(
            "City*",
            value=(
                trip_data.get("departure_city", "") if is_editing and trip_data else ""
            ),
            disabled=not is_draft,
            key=f"departure_city_input_{key_suffix}",
        )
    with col_dep_region:
        departure_region = st.text_input(
            "Region / State (optional)",
            value=(
                trip_data.get("departure_region", "")
                if is_editing and trip_data
                else ""
            ),
            disabled=not is_draft,
            key=f"departure_region_input_{key_suffix}",
        )
    departure_country = st.selectbox(
        "Country (optional)",
        options=[""] + country_list,
        index=(
            (([""] + country_list).index(trip_data.get("departure_country", "")))
            if is_editing and trip_data and trip_data.get("departure_country")
            else 0
        ),
        disabled=not is_draft,
        key=f"departure_country_input_{key_suffix}",
    )

    # Stops
    st.subheader("📍 Trip Stops (Destinations)")
    if stops:
        st.write("**Stops in this trip:**")
        for idx, stop in enumerate(stops):
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
                if st.button("🗑️", key=f"del_stop_{key_suffix}_{idx}"):
                    st.session_state[stops_key].pop(idx)
                    st.rerun()

    with st.expander("➕ Add Destination Stop"):
        col_city, col_country = st.columns(2)
        with col_city:
            new_city = st.text_input(
                "City*", key=f"new_stop_city_{key_suffix}", disabled=not is_draft
            )
        with col_country:
            new_country = st.selectbox(
                "Country (optional)",
                options=[""] + country_list,
                index=0,
                key=f"new_stop_country_{key_suffix}",
                disabled=not is_draft,
            )
        col_region, col_notes = st.columns(2)
        with col_region:
            new_region = st.text_input(
                "Region / State (optional)",
                key=f"new_stop_region_{key_suffix}",
                disabled=not is_draft,
            )
        with col_notes:
            new_stop_notes = st.text_input(
                "Notes (optional)",
                key=f"new_stop_notes_{key_suffix}",
                disabled=not is_draft,
            )
        col_start, col_end = st.columns(2)
        with col_start:
            new_start = st.date_input(
                "Start Date*",
                value=datetime.now(),
                key=f"new_stop_start_{key_suffix}",
                disabled=not is_draft,
            )
        with col_end:
            new_end = st.date_input(
                "End Date*",
                value=datetime.now(),
                key=f"new_stop_end_{key_suffix}",
                disabled=not is_draft,
            )

        if st.button(
            "➕ Add Stop", key=f"add_stop_button_{key_suffix}", disabled=not is_draft
        ):
            if new_city and new_start and new_end:
                st.session_state[stops_key].append(
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

    # Currencies
    st.subheader("💱 Trip Currencies")
    col_currency1, col_currency2 = st.columns(2)
    display_currency_options = ["USD", "EUR", "GBP", "NGN", "JPY", "BRL"]
    current_display = (
        trip_data.get("display_currency", "USD") if is_editing and trip_data else "USD"
    )
    with col_currency1:
        trip_display_currency = st.selectbox(
            "Display Currency (for this trip)",
            options=display_currency_options,
            index=(
                display_currency_options.index(current_display)
                if current_display in display_currency_options
                else 0
            ),
            disabled=not is_draft,
            key=f"trip_display_currency_{key_suffix}",
            help="The currency used for all item costs in this trip.",
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
    current_base = (
        trip_data.get("base_currency", "USD") if is_editing and trip_data else "USD"
    )
    with col_currency2:
        trip_base_currency = st.selectbox(
            "Base Currency (for reporting & conversion)",
            options=base_currency_options,
            index=(
                base_currency_options.index(current_base)
                if current_base in base_currency_options
                else 0
            ),
            disabled=not is_draft,
            key=f"trip_base_currency_{key_suffix}",
            help="All expenses are converted to this currency using the trip‑wide exchange rate.",
        )

    # Exchange rate
    default_display_rate = (
        trip_data.get("display_exchange_rate", 1.0) if is_editing and trip_data else 1.0
    )
    display_exchange_rate = st.number_input(
        f"Exchange Rate (1 {trip_base_currency} = ? {trip_display_currency})",
        min_value=0.000001,
        step=0.0001,
        value=default_display_rate,
        disabled=not is_draft,
        key=f"display_exchange_rate_{key_suffix}",
        help=f"Enter the exchange rate from {trip_base_currency} to {trip_display_currency}.",
    )

    # Budget
    st.subheader("💰 Trip Budget")
    budget_currency_options = {
        f"Base Currency ({trip_base_currency})": "base",
        f"Display Currency ({trip_display_currency})": "display",
    }
    budget_currency_label = st.selectbox(
        "Budget Currency",
        options=list(budget_currency_options.keys()),
        index=0,
        key=f"budget_currency_label_{key_suffix}",
        disabled=not is_draft,
    )
    budget_currency_code = budget_currency_options[budget_currency_label]

    stored_budget = (
        float(trip_data.get("budget", 0)) if is_editing and trip_data else 0.0
    )
    if budget_currency_code == "base":
        budget_label = f"Budget (in {trip_base_currency})"
        budget_value = stored_budget
    else:
        budget_label = f"Budget (in {trip_display_currency})"
        budget_value = stored_budget * display_exchange_rate

    budget = st.number_input(
        budget_label,
        min_value=0.0,
        step=100.0,
        value=budget_value,
        disabled=not is_draft,
        key=f"trip_budget_input_{key_suffix}",
        help=f"Enter the total budget for this trip in {budget_currency_code.upper()}.",
    )

    def budget_to_base(budget_val, currency_code, exchange_rate):
        if currency_code == "display":
            return budget_val / exchange_rate if exchange_rate != 0 else 0
        return budget_val

    # Create/Update buttons
    col_buttons = st.columns([1, 1, 2])
    with col_buttons[0]:
        if is_editing:
            if is_draft:
                if st.button("🚀 Update Draft", key=f"update_trip_form_{key_suffix}"):
                    if trip_purpose and stops:
                        first_stop = stops[0]
                        last_stop = stops[-1]
                        overall_start = first_stop["start_date"]
                        overall_end = last_stop["end_date"]
                        stop_cities = [stop["city"] for stop in stops]
                        dest_summary = " → ".join(stop_cities)

                        # Duplicate check
                        existing_trips = duplicate_detection.find_duplicate_trips(
                            trip_exec_id,
                            trip_purpose,
                            overall_start,
                            overall_end,
                            exclude_trip_id=trip_id,
                        )
                        if existing_trips:
                            st.warning(
                                "⚠️ You already have a trip with the same purpose and overlapping dates:"
                            )
                            for dup in existing_trips:
                                st.write(
                                    f"- {dup['destination']} ({dup['start_date'][:10]} to {dup['end_date'][:10]})"
                                )
                            if not st.checkbox(
                                "Proceed anyway?", key=f"force_trip_update_{key_suffix}"
                            ):
                                st.stop()

                        budget_base = budget_to_base(
                            budget, budget_currency_code, display_exchange_rate
                        )

                        db.update_trip_purpose(trip_id, trip_purpose)
                        db.update_trip_dates(
                            trip_id, overall_start, overall_end, dest_summary
                        )
                        db.update_trip_budget(trip_id, budget_base)
                        db.update_trip_departure_details(
                            trip_id, departure_city, departure_region, departure_country
                        )
                        db.update_trip_currencies(
                            trip_id, trip_base_currency, trip_display_currency
                        )
                        db.update_trip_display_exchange_rate(
                            trip_id, display_exchange_rate
                        )

                        db.delete_all_trip_stops(trip_id)
                        for idx, stop in enumerate(stops):
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

                        st.success(f"Trip '{trip_purpose}' updated successfully!")
                        # Clear appropriate session state
                        if key_suffix == "inline":
                            st.session_state["reset_form"] = True
                        else:  # modal
                            st.session_state["show_edit_trip_dashboard"] = False
                            st.session_state[f"trip_stops_{key_suffix}"] = []
                        st.rerun()
                    else:
                        st.warning("Enter a Trip Name and add at least one stop.")
            else:
                st.warning(
                    f"⚠️ This trip is **{trip_data.get('status', 'draft').title()}** and cannot be edited."
                )
        else:
            if st.button("🚀 Create Trip", key=f"create_trip_form_{key_suffix}"):
                if trip_purpose and stops:
                    first_stop = stops[0]
                    last_stop = stops[-1]
                    overall_start = first_stop["start_date"]
                    overall_end = last_stop["end_date"]
                    stop_cities = [stop["city"] for stop in stops]
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
                        if not st.checkbox(
                            "Proceed anyway?", key=f"force_trip_create_{key_suffix}"
                        ):
                            st.stop()

                    budget_base = budget_to_base(
                        budget, budget_currency_code, display_exchange_rate
                    )

                    new_trip_id = db.create_or_get_trip(
                        trip_exec_id,
                        dest_summary,
                        overall_start,
                        overall_end,
                        trip_purpose,
                        trip_display_currency,
                        trip_base_currency,
                    )
                    db.update_trip_budget(new_trip_id, budget_base)
                    db.update_trip_departure_details(
                        new_trip_id, departure_city, departure_region, departure_country
                    )
                    db.update_trip_display_exchange_rate(
                        new_trip_id, display_exchange_rate
                    )

                    db.delete_all_trip_stops(new_trip_id)
                    for idx, stop in enumerate(stops):
                        db.add_trip_stop(
                            new_trip_id,
                            idx + 1,
                            stop["city"],
                            stop.get("country", ""),
                            stop.get("region", ""),
                            stop["start_date"],
                            stop["end_date"],
                            stop.get("notes", ""),
                        )

                    st.success(
                        f"Trip '{trip_purpose}' created for {trip_exec_label} with {len(stops)} stops!"
                    )
                    st.session_state["current_trip_id"] = new_trip_id
                    # Clear inline stops
                    st.session_state[f"trip_stops_{key_suffix}"] = []
                    st.session_state["reset_form"] = True
                    st.rerun()
                else:
                    st.warning("Enter a Trip Name and add at least one stop.")
    with col_buttons[1]:
        if st.button("🗑️ Clear Form", key=f"clear_form_{key_suffix}"):
            st.session_state[f"trip_stops_{key_suffix}"] = []
            if key_suffix == "inline":
                st.session_state["reset_form"] = True
            else:
                st.session_state["show_edit_trip_dashboard"] = False
            st.rerun()

    return False


def render_executive_edit_form(exec_id, profile):
    """Render the executive edit form inside a modal."""
    companies = db.get_all_companies()
    company_options = {name: id for id, name in companies}
    current_company_id = profile.get("company_id")
    curr_comp_name = next(
        (name for name, cid in company_options.items() if cid == current_company_id),
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
        key="edit_company_modal",
    )
    new_company_id = company_options[new_company_label]

    new_name = st.text_input(
        "Full Name*", value=profile.get("name", ""), key="edit_name_modal"
    )
    new_email = st.text_input(
        "Email", value=profile.get("email", ""), key="edit_email_modal"
    )
    tz_display_names, tz_map = get_timezone_dropdown_options()
    current_tz = profile.get("timezone", "America/New_York")
    current_tz_display = next(
        (n for n in tz_display_names if current_tz in n), tz_display_names[0]
    )
    new_tz_display = st.selectbox(
        "Timezone",
        tz_display_names,
        index=tz_display_names.index(current_tz_display),
        key="edit_tz_modal",
    )
    new_tz = tz_map[new_tz_display]

    seat_options = ["No Preference", "Aisle", "Window", "Middle"]
    new_seat = st.selectbox(
        "Seat Preference",
        seat_options,
        index=safe_index(seat_options, profile.get("seat_preference", "No Preference")),
        key="edit_seat_modal",
    )
    new_hotel = st.text_input(
        "Hotel Loyalty", value=profile.get("hotel_loyalty", ""), key="edit_hotel_modal"
    )
    new_ff = st.text_input(
        "Frequent Flyer Number",
        value=profile.get("frequent_flyer_number", ""),
        key="edit_ff_modal",
    )
    new_diet = st.text_input(
        "Dietary Restrictions",
        value=profile.get("dietary_restrictions", ""),
        key="edit_diet_modal",
    )
    new_passport = st.text_input(
        "Passport Number",
        value=profile.get("passport_number", ""),
        key="edit_passport_modal",
    )
    new_airline = st.text_input(
        "Preferred Airline",
        value=profile.get("preferred_airline", ""),
        key="edit_airline_modal",
    )
    new_tsa = st.text_input(
        "TSA PreCheck", value=profile.get("tsa_precheck", ""), key="edit_tsa_modal"
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
        index=safe_index(meal_options, profile.get("meal_preference", "No Preference")),
        key="edit_meal_modal",
    )

    col_save, col_cancel = st.columns(2)
    with col_save:
        if st.button("💾 Save Changes", key="save_exec_modal"):
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
            st.session_state.show_exec_dialog = False
            st.rerun()
    with col_cancel:
        if st.button("❌ Cancel", key="cancel_exec_modal"):
            st.session_state.show_exec_dialog = False
            st.rerun()


# =========================================================
# DIALOG FUNCTIONS (only for editing trips from dashboard)
# =========================================================


@st.dialog("Edit Trip")
def edit_trip_dashboard_dialog():
    """Dialog for editing a trip from the Spending Dashboard."""
    trip_id = st.session_state.get("editing_trip_id")
    if not trip_id:
        st.error("No trip selected.")
        return
    trip_data = db.get_trip(trip_id)
    if not trip_data:
        st.error("Trip not found.")
        return
    is_draft = trip_data.get("status", "draft") == "draft"
    if not is_draft:
        st.warning("This trip is not in Draft status and cannot be edited.")
        return
    # Prepare exec dropdown
    exec_dropdown_options = {f"{name} (ID: {id})": id for id, name, _ in executives}
    default_exec_id = trip_data.get("exec_id")
    default_label = next(
        (
            label
            for label, eid in exec_dropdown_options.items()
            if eid == default_exec_id
        ),
        list(exec_dropdown_options.keys())[0],
    )
    trip_exec_label = default_label
    trip_exec_id = default_exec_id
    country_list = sorted([c.name for c in pycountry.countries])
    # Load stops into modal-specific session state
    st.session_state["trip_stops_modal"] = db.get_trip_stops(trip_id)
    render_trip_setup_form(
        True,
        trip_data,
        trip_id,
        trip_exec_label,
        trip_exec_id,
        is_draft,
        exec_id,
        executives,
        country_list,
        key_suffix="modal",
    )


@st.dialog("Edit Executive")
def edit_executive_dialog():
    """Dialog for editing an executive."""
    if not profile:
        st.error("No executive selected.")
        return
    render_executive_edit_form(exec_id, profile)


# =========================================================
# HELPER FUNCTIONS FOR ITINERARY (add item form)
# =========================================================


def render_add_item_form(
    trip_id, trip_base_currency, trip_display_currency, display_rate, key_suffix=""
):
    with st.form(key=f"add_item_form_{key_suffix}"):
        categories = db.get_all_categories()
        cat_names = (
            [cat[1] for cat in categories]
            if categories
            else ["Flight", "Hotel", "Meeting", "Transport"]
        )
        cols = st.columns(4)
        with cols[0]:
            item_type = st.selectbox("Type", cat_names, key=f"item_type_{key_suffix}")
        with cols[1]:
            desc = st.text_input("Description", key=f"item_desc_{key_suffix}")
        with cols[2]:
            dt_start = st.datetime_input(
                "Start Time", value=datetime.now(), key=f"item_start_{key_suffix}"
            )
        with cols[3]:
            dt_end = st.datetime_input(
                "End Time", value=datetime.now(), key=f"item_end_{key_suffix}"
            )

        col_loc, col_cost, col_curr, col_conf, col_rate = st.columns(5)
        with col_loc:
            location = st.text_input("Location", key=f"item_location_{key_suffix}")
        with col_cost:
            cost = st.number_input(
                "Cost", min_value=0.0, step=10.0, key=f"item_cost_{key_suffix}"
            )
        with col_curr:
            currency_choice = st.selectbox(
                "Currency",
                options=[
                    f"Display ({trip_display_currency})",
                    f"Base ({trip_base_currency})",
                ],
                key=f"item_currency_{key_suffix}",
            )
            chosen_currency = (
                trip_display_currency
                if "Display" in currency_choice
                else trip_base_currency
            )
        with col_conf:
            conf_code = st.text_input(
                "Confirmation Code", key=f"item_conf_{key_suffix}"
            )
        with col_rate:
            # Exchange rate field (only for Display currency)
            if chosen_currency == trip_display_currency:
                # Default to trip-wide display_rate
                default_rate = display_rate if display_rate > 0 else 1.0
                rate = st.number_input(
                    f"Exchange Rate (1 {trip_base_currency} = ? {trip_display_currency})",
                    min_value=0.000001,
                    step=0.01,
                    value=default_rate,
                    key=f"item_rate_{key_suffix}",
                    help="Override the trip-wide exchange rate for this item.",
                )
                snapshot_rate = 1.0 / rate if rate != 0 else 1.0
            else:
                # For base currency, no rate needed
                st.text("Rate: N/A (Base currency)")
                snapshot_rate = 1.0

        notes = st.text_area("Notes", key=f"item_notes_{key_suffix}")
        confirmed = st.checkbox(
            "✅ Confirmed / Booked", key=f"item_confirmed_{key_suffix}"
        )

        if st.form_submit_button("Add to Itinerary"):
            if desc and dt_start:
                existing_dupes = duplicate_detection.find_duplicate_item(
                    trip_id,
                    desc,
                    dt_start.isoformat(),
                    dt_end.isoformat() if dt_end else None,
                    cost,
                    item_type,
                )
                if existing_dupes:
                    st.warning(
                        "⚠️ This item looks like a duplicate of an existing one:"
                    )
                    for d in existing_dupes:
                        st.write(f"- {d['description']} ({d['datetime_start'][:16]})")
                    if not st.checkbox(
                        "Add anyway?", key=f"force_add_item_{key_suffix}"
                    ):
                        st.stop()
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
                    chosen_currency,
                    snapshot_rate,
                )
                st.success("Added!")
                st.rerun()
                return True
            else:
                st.warning("Description and Start Time required.")
        return False


# =========================================================
# TABS
# =========================================================
tabs = st.tabs(
    [
        "✈️ Trip Planner",
        "👤 Executive Management",
        "📋 Trip Templates",
        "📊 Spending Dashboard",
    ],
    key="tab_control",
)

# Define country list globally
country_list = sorted([c.name for c in pycountry.countries])

for i, tab in enumerate(tabs):
    with tab:
        if i == 0:
            # --- TRIP PLANNER (inline form, no buttons) ---
            if not profile:
                st.warning(
                    "Please add an executive in the 'Executive Management' tab first."
                )
                st.stop()

            st.header("📅 Trip Planner")

            # Check current trip
            is_editing = (
                "current_trip_id" in st.session_state
                and st.session_state.current_trip_id is not None
            )
            trip_id = st.session_state.get("current_trip_id")
            trip_data = db.get_trip(trip_id) if trip_id else None
            items = db.get_items_for_trip(trip_id) if trip_id else []
            stops = db.get_trip_stops(trip_id) if trip_id else []

            # Get trip purpose (for export buttons)
            trip_purpose = trip_data.get("purpose", "") if trip_data else ""

            # --- Display trip status (if any) ---
            if is_editing and trip_data:
                status = trip_data.get("status", "draft")
                st.caption(f"**Status:** {status.title()}")
                if status == "draft":
                    if st.button("✅ Mark as Approved"):
                        db.update_trip_status(trip_id, "approved")
                        st.rerun()
                elif status == "approved":
                    if st.button("📄 Mark as Final"):
                        db.update_trip_status(trip_id, "final")
                        st.rerun()
                elif status == "final":
                    st.info("Final – no further changes allowed.")

            # --- Render the trip setup form inline ---
            st.divider()
            if is_editing and trip_data:
                is_draft = trip_data.get("status", "draft") == "draft"
                if not is_draft:
                    st.warning(
                        "This trip is not in Draft status and cannot be edited. Duplicate it or revert to draft."
                    )
                exec_dropdown_options = {
                    f"{name} (ID: {id})": id for id, name, _ in executives
                }
                default_exec_id = trip_data.get("exec_id")
                default_label = next(
                    (
                        label
                        for label, eid in exec_dropdown_options.items()
                        if eid == default_exec_id
                    ),
                    list(exec_dropdown_options.keys())[0],
                )
                trip_exec_label = default_label
                trip_exec_id = default_exec_id
                # Load stops into inline session state if not already
                if not st.session_state["trip_stops_inline"]:
                    st.session_state["trip_stops_inline"] = db.get_trip_stops(trip_id)
                render_trip_setup_form(
                    True,
                    trip_data,
                    trip_id,
                    trip_exec_label,
                    trip_exec_id,
                    is_draft,
                    exec_id,
                    executives,
                    country_list,
                    key_suffix="inline",
                )
            else:
                # New trip form
                exec_dropdown_options = {
                    f"{name} (ID: {id})": id for id, name, _ in executives
                }
                default_label = next(
                    (
                        label
                        for label, eid in exec_dropdown_options.items()
                        if eid == exec_id
                    ),
                    list(exec_dropdown_options.keys())[0],
                )
                trip_exec_label = default_label
                trip_exec_id = exec_id
                render_trip_setup_form(
                    False,
                    None,
                    None,
                    trip_exec_label,
                    trip_exec_id,
                    True,
                    exec_id,
                    executives,
                    country_list,
                    key_suffix="inline",
                )

            # --- Itinerary and Spending (if trip loaded) ---
            if is_editing and trip_data:
                trip_budget = trip_data.get("budget", 0)
                trip_display_currency = trip_data.get("display_currency", "USD")
                display_symbol = get_currency_symbol(trip_display_currency)
                trip_base_currency = trip_data.get("base_currency", "USD")
                base_symbol = get_currency_symbol(trip_base_currency)
                display_rate = trip_data.get("display_exchange_rate", 1.0)

                # Spending Summary
                total_estimated_base = 0.0
                total_confirmed_base = 0.0
                total_all_base = 0.0
                for item in items:
                    cost = item.get("cost", 0)
                    snapshot_rate = item.get("exchange_rate_snapshot", 1.0)
                    converted = cost * snapshot_rate
                    total_all_base += converted
                    if item.get("is_confirmed"):
                        total_confirmed_base += converted
                    else:
                        total_estimated_base += converted

                st.subheader("💰 Spending Summary")
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric(
                        "Total Estimated (Base)",
                        f"{base_symbol}{total_estimated_base:,.2f}",
                    )
                with col2:
                    st.metric(
                        "✅ Confirmed (Base)",
                        f"{base_symbol}{total_confirmed_base:,.2f}",
                    )
                with col3:
                    st.metric(
                        "📊 Total Spend (Base)", f"{base_symbol}{total_all_base:,.2f}"
                    )
                with col4:
                    remaining_base = trip_budget - total_all_base
                    st.metric(
                        "💰 Budget (Base)",
                        f"{base_symbol}{trip_budget:,.2f}",
                        delta=f"{base_symbol}{remaining_base:,.2f} remaining",
                        delta_color="inverse" if remaining_base < 0 else "normal",
                    )

                st.divider()
                col5, col6, col7, col8 = st.columns(4)
                total_estimated_display = total_estimated_base * display_rate
                total_confirmed_display = total_confirmed_base * display_rate
                total_all_display = total_all_base * display_rate
                budget_display = trip_budget * display_rate
                remaining_display = budget_display - total_all_display
                with col5:
                    st.metric(
                        "Total Estimated (Display)",
                        f"{display_symbol}{total_estimated_display:,.2f}",
                    )
                with col6:
                    st.metric(
                        "✅ Confirmed (Display)",
                        f"{display_symbol}{total_confirmed_display:,.2f}",
                    )
                with col7:
                    st.metric(
                        "📊 Total Spend (Display)",
                        f"{display_symbol}{total_all_display:,.2f}",
                    )
                with col8:
                    st.metric(
                        "💰 Budget (Display)",
                        f"{display_symbol}{budget_display:,.2f}",
                        delta=f"{display_symbol}{remaining_display:,.2f} remaining",
                        delta_color="inverse" if remaining_display < 0 else "normal",
                    )

                if trip_budget > 0:
                    percent_used = min((total_all_base / trip_budget) * 100, 100)
                    st.progress(
                        percent_used / 100, text="{:.0f}% used".format(percent_used)
                    )
                st.divider()

                # Trip Route
                dep_city_db = trip_data.get("departure_city", "")
                dep_region_db = trip_data.get("departure_region", "")
                dep_country_db = trip_data.get("departure_country", "")
                dep_parts = [
                    p for p in [dep_city_db, dep_region_db, dep_country_db] if p
                ]
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

                    with st.expander("✏️ Edit Stops"):
                        for stop in stops:
                            st.markdown(
                                f"**Stop {stop['stop_order']}:** {stop['city']}"
                            )
                            with st.form(key=f"edit_stop_{stop['id']}"):
                                col1, col2 = st.columns(2)
                                with col1:
                                    e_city = st.text_input(
                                        "City",
                                        value=stop["city"],
                                        key=f"e_city_{stop['id']}",
                                    )
                                    e_country = st.selectbox(
                                        "Country",
                                        [""] + country_list,
                                        index=(
                                            ([""] + country_list).index(
                                                stop.get("country", "")
                                            )
                                            if stop.get("country")
                                            in [""] + country_list
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
                                        value=datetime.fromisoformat(
                                            stop["start_date"]
                                        ),
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

                # Conflict detection
                conflicts = utils.detect_conflicts(items)
                if conflicts:
                    st.warning("⚠️ Conflicts Detected:")
                    for c in conflicts:
                        st.write(f"- {c}")
                else:
                    st.success("✅ No scheduling conflicts detected.")

                # --- Itinerary Items display and edit ---
                if items:
                    display_mode = st.radio(
                        "Show costs in:",
                        ["Original Currency", "Snapshot (at time of expense)"],
                        index=0,
                        key="display_mode",
                        horizontal=True,
                    )

                    st.subheader("📋 Itinerary Items")
                    for item in items:
                        (
                            col_desc,
                            col_receipt_status,
                            col_upload,
                            col_del_receipt,
                            col_del_item,
                            col_edit,
                        ) = st.columns([4, 2, 2, 1, 1, 1])

                        orig_currency = item.get("cost_currency", trip_display_currency)
                        orig_cost = item.get("cost", 0)
                        snapshot_rate = item.get("exchange_rate_snapshot", 1.0)

                        if display_mode == "Original Currency":
                            display_cost = orig_cost
                            display_symbol_local = get_currency_symbol(orig_currency)
                            display_currency_code = orig_currency
                        else:  # Snapshot
                            display_cost = orig_cost * snapshot_rate
                            display_symbol_local = base_symbol
                            display_currency_code = trip_base_currency

                        display_str = f"{display_symbol_local}{display_cost:,.2f} {display_currency_code}"
                        start_display = format_datetime_display(item["datetime_start"])
                        end_display = (
                            datetime.fromisoformat(item["datetime_end"]).strftime(
                                "%H:%M"
                            )
                            if item["datetime_end"]
                            else "TBD"
                        )
                        status_icon = "✅" if item.get("is_confirmed") else "📌"

                        with col_desc:
                            st.write(
                                f"{status_icon} **{start_display} – {end_display}** | {item['item_type']}: {item['description']} | Cost: {display_str}"
                            )

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

                        with col_upload:
                            upload_key = f"receipt_{item['id']}_{st.session_state.upload_counter}"
                            uploaded_file = st.file_uploader(
                                "Attach",
                                type=["png", "jpg", "jpeg", "pdf"],
                                key=upload_key,
                                label_visibility="collapsed",
                            )
                            if uploaded_file is not None:
                                if not receipt_path or not os.path.exists(receipt_path):
                                    existing_receipts = (
                                        duplicate_detection.find_duplicate_receipts(
                                            trip_id
                                        )
                                    )
                                    if uploaded_file.name in existing_receipts:
                                        st.error(
                                            f"⚠️ A receipt with the name '{uploaded_file.name}' already exists in this trip."
                                        )
                                        base, ext = os.path.splitext(uploaded_file.name)
                                        new_name = f"{base}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
                                        st.info(f"Renamed to: {new_name}")
                                        uploaded_file.name = new_name

                                    os.makedirs("receipts", exist_ok=True)
                                    trip_folder = f"receipts/trip_{trip_id}"
                                    os.makedirs(trip_folder, exist_ok=True)
                                    safe_name = f"item_{item['id']}_{uploaded_file.name.replace(' ', '_')}"
                                    file_path = os.path.join(trip_folder, safe_name)
                                    with open(file_path, "wb") as f:
                                        f.write(uploaded_file.getbuffer())
                                    db.update_receipt_path(item["id"], file_path)
                                    st.session_state.upload_counter += 1
                                    st.success("✅ Receipt attached!")
                                    st.rerun()
                                else:
                                    st.info(
                                        "A receipt is already attached. Remove it first."
                                    )

                        with col_del_receipt:
                            if receipt_path and os.path.exists(receipt_path):
                                if st.button(
                                    "🗑️ Receipt", key=f"del_receipt_{item['id']}"
                                ):
                                    try:
                                        os.remove(receipt_path)
                                        st.success(
                                            f"✅ Receipt deleted: {os.path.basename(receipt_path)}"
                                        )
                                    except Exception as e:
                                        st.error(f"Could not delete file: {e}")
                                    db.update_receipt_path(item["id"], None)
                                    st.session_state.upload_counter += 1
                                    st.rerun()

                        with col_del_item:
                            if st.button("❌ Item", key=f"del_item_{item['id']}"):
                                db.delete_itinerary_item(item["id"])
                                st.rerun()

                        with col_edit:
                            if st.button("✏️", key=f"edit_btn_{item['id']}"):
                                st.session_state[f"editing_item_{item['id']}"] = (
                                    not st.session_state.get(
                                        f"editing_item_{item['id']}", False
                                    )
                                )
                                st.rerun()

                        if st.session_state.get(f"editing_item_{item['id']}", False):
                            with st.expander(
                                f"✏️ Editing: {item['description']}", expanded=True
                            ):
                                with st.form(key=f"edit_item_form_{item['id']}"):
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
                                        "Type",
                                        cat_names,
                                        index=idx_cat,
                                        key=f"e_type_{item['id']}",
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
                                            value=datetime.fromisoformat(
                                                item["datetime_start"]
                                            ),
                                            key=f"e_start_{item['id']}",
                                        )
                                    with col_dt2:
                                        e_end = st.datetime_input(
                                            "End Time",
                                            value=(
                                                datetime.fromisoformat(
                                                    item["datetime_end"]
                                                )
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
                                    col_cost1, col_curr1, col_conf1, col_rate1 = (
                                        st.columns(4)
                                    )
                                    with col_cost1:
                                        e_cost = st.number_input(
                                            "Cost",
                                            min_value=0.0,
                                            step=10.0,
                                            value=float(item.get("cost", 0)),
                                            key=f"e_cost_{item['id']}",
                                        )
                                    with col_curr1:
                                        current_currency = item.get(
                                            "cost_currency", trip_display_currency
                                        )
                                        currency_options = [
                                            f"Display ({trip_display_currency})",
                                            f"Base ({trip_base_currency})",
                                        ]
                                        default_idx = (
                                            0
                                            if current_currency == trip_display_currency
                                            else 1
                                        )
                                        e_currency_choice = st.selectbox(
                                            "Currency",
                                            options=currency_options,
                                            index=default_idx,
                                            key=f"e_currency_{item['id']}",
                                        )
                                        e_chosen_currency = (
                                            trip_display_currency
                                            if "Display" in e_currency_choice
                                            else trip_base_currency
                                        )
                                    with col_rate1:
                                        # Exchange rate field (only if currency is Display)
                                        if e_chosen_currency == trip_display_currency:
                                            # Compute current rate from snapshot
                                            snapshot = item.get(
                                                "exchange_rate_snapshot", 1.0
                                            )
                                            current_rate = (
                                                1.0 / snapshot if snapshot != 0 else 1.0
                                            )
                                            e_rate = st.number_input(
                                                f"Exchange Rate (1 {trip_base_currency} = ? {trip_display_currency})",
                                                min_value=0.000001,
                                                step=0.01,
                                                value=current_rate,
                                                key=f"e_rate_{item['id']}",
                                                help="Override the trip-wide exchange rate for this item.",
                                            )
                                            e_snapshot_rate = (
                                                1.0 / e_rate if e_rate != 0 else 1.0
                                            )
                                        else:
                                            st.text("Rate: N/A (Base currency)")
                                            e_snapshot_rate = 1.0
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
                                    st.markdown("---")
                                    col_save_btn, col_cancel_btn = st.columns(2)
                                    with col_save_btn:
                                        if st.form_submit_button("💾 Save Changes"):
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
                                                e_chosen_currency,
                                                e_snapshot_rate,
                                            )
                                            st.session_state[
                                                f"editing_item_{item['id']}"
                                            ] = False
                                            st.success("Item updated!")
                                            st.rerun()
                                    with col_cancel_btn:
                                        if st.form_submit_button("❌ Cancel"):
                                            st.session_state[
                                                f"editing_item_{item['id']}"
                                            ] = False
                                            st.rerun()

                else:
                    st.info("No itinerary items yet. Add one below.")

                # Add New Item
                st.divider()
                st.subheader("➕ Add New Itinerary Item")
                render_add_item_form(
                    trip_id,
                    trip_base_currency,
                    trip_display_currency,
                    display_rate,
                    key_suffix="",
                )

                # Export buttons
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
                            display_symbol,
                            trip_display_currency,
                            base_currency=trip_base_currency,
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
                            items,
                            profile.get("timezone", "America/New_York"),
                            trip_purpose,
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
                            doc_stream, filename = (
                                doc_generator.generate_expense_report_doc(
                                    exec_data,
                                    items,
                                    stops_data,
                                    dep_city_db,
                                    dep_region_db,
                                    dep_country_db,
                                    trip_id,
                                    trip_budget,
                                    trip_purpose,
                                    display_symbol,
                                    base_currency=trip_base_currency,
                                )
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
                                display_symbol,
                                base_currency=trip_base_currency,
                            )
                            if excel_stream:
                                st.download_button(
                                    "⬇️ Download .xlsx",
                                    data=excel_stream,
                                    file_name=f"{trip_purpose}_ExpenseReport.xlsx",
                                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                    key="expense_excel_download",
                                )
                        else:
                            st.warning("No items to export.")

                # Duplicate scan
                st.divider()
                if st.button("🔍 Scan for Duplicates & Conflicts"):
                    st.session_state["show_duplicate_scan"] = True
                if st.session_state.get("show_duplicate_scan", False):
                    with st.expander("🔍 Duplicate & Conflict Report", expanded=True):
                        report = duplicate_detection.scan_trip_for_duplicates(trip_id)
                        if not report:
                            st.info("No issues found.")
                        else:
                            if report["conflicts"]:
                                st.error("⏰ Scheduling Conflicts")
                                for c in report["conflicts"]:
                                    st.write(f"- {c}")
                            if report["duplicate_items"]:
                                st.warning("📋 Exact Duplicate Items")
                                for group in report["duplicate_items"]:
                                    orig = group["original"]
                                    st.write(
                                        f"**Original:** {orig['description']} ({orig['datetime_start'][:16]})"
                                    )
                                    for dup in group["duplicates"]:
                                        st.write(
                                            f"  - Duplicate: {dup['description']} ({dup['datetime_start'][:16]})"
                                        )
                                        if st.button(
                                            f"🗑️ Delete duplicate #{dup['id']}",
                                            key=f"del_dup_{dup['id']}",
                                        ):
                                            db.delete_itinerary_item(dup["id"])
                                            st.success("Deleted duplicate item.")
                                            st.rerun()
                            if report["similar_expenses"]:
                                st.info(
                                    "💰 Similar Expenses (check for double‑booking)"
                                )
                                for a, b in report["similar_expenses"]:
                                    st.write(
                                        f"  - {a['description']} ({a['cost']}) vs {b['description']} ({b['cost']})"
                                    )
                            if report["duplicate_receipts"]:
                                st.info("📎 Duplicate Receipt Filenames")
                                for fname, ids in report["duplicate_receipts"].items():
                                    st.write(f"  - {fname}: attached to items {ids}")
                            if st.button("Close Scan"):
                                st.session_state["show_duplicate_scan"] = False
                                st.rerun()

            else:
                st.info(
                    "No trip loaded. Fill in the form above and click 'Create Trip'."
                )

        # ------------------------------------------------------------
        # Executive Management, Trip Templates, Spending Dashboard remain unchanged
        # ------------------------------------------------------------
        elif i == 1:
            # --- EXECUTIVE MANAGEMENT ---
            st.header("👤 Executive Management")

            # Add Company
            st.subheader("🏢 Add Company")
            with st.form("add_company_form_tab", clear_on_submit=True):
                comp_name = st.text_input("Company Name", key="comp_name_tab")
                comp_cc = st.text_input(
                    "Default Cost Center (optional)", key="comp_cc_tab"
                )
                comp_policy = st.text_area(
                    "Policy Notes (optional)", key="comp_policy_tab"
                )
                if st.form_submit_button("Add Company"):
                    if comp_name:
                        db.add_company(comp_name, comp_cc, comp_policy)
                        st.success(f"Company '{comp_name}' added!")
                        st.rerun()
                    else:
                        st.warning("Company Name is required.")
            st.divider()

            if profile:
                # Profile summary
                st.subheader(f"📋 Profile: {profile['name']}")
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Company:** {profile.get('company_name', 'N/A')}")
                    st.write(f"**Email:** {profile.get('email', 'N/A')}")
                    st.write(f"**Timezone:** {profile.get('timezone', 'N/A')}")
                    st.write(
                        f"**Seat Preference:** {profile.get('seat_preference', 'N/A')}"
                    )
                with col2:
                    st.write(
                        f"**Hotel Loyalty:** {profile.get('hotel_loyalty', 'N/A')}"
                    )
                    st.write(
                        f"**Frequent Flyer:** {profile.get('frequent_flyer_number', 'N/A')}"
                    )
                    st.write(
                        f"**Dietary Restrictions:** {profile.get('dietary_restrictions', 'N/A')}"
                    )
                    st.write(
                        f"**Meal Preference:** {profile.get('meal_preference', 'N/A')}"
                    )

                mems = db.get_memberships(exec_id)
                if mems:
                    st.write("**Memberships:**")
                    for m in mems:
                        emoji = (
                            "✈️"
                            if m["category"] == "airline"
                            else "🏨" if m["category"] == "hotel" else "🚗"
                        )
                        st.write(
                            f"  {emoji} {m['program_name']}: {m['membership_number']}"
                        )
                else:
                    st.write("**Memberships:** None")

                # Edit button (opens modal)
                if st.button("✏️ Edit Executive"):
                    st.session_state.show_exec_dialog = True
                    st.rerun()

                # Show Executive Edit Dialog
                if st.session_state.get("show_exec_dialog", False):
                    edit_executive_dialog()

                # Manage Memberships
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
                            st.write(
                                f"{emoji} {m['program_name']}: {m['membership_number']}"
                            )
                        with col2:
                            if st.button("❌", key=f"del_mem_tab_{m['id']}"):
                                db.delete_membership(m["id"])
                                st.rerun()
                else:
                    st.info("No memberships added yet.")

                st.write("**Add New Membership:**")
                col_cat, col_name, col_num = st.columns(3)
                with col_cat:
                    new_cat = st.selectbox(
                        "Category",
                        ["Airline", "Hotel", "Car Rental"],
                        key="edit_mem_cat_tab",
                    )
                with col_name:
                    new_name = st.text_input("Program Name", key="edit_mem_name_tab")
                with col_num:
                    new_num = st.text_input("Membership Number", key="edit_mem_num_tab")
                if st.button("➕ Add Membership", key="edit_add_mem_tab"):
                    if new_name and new_num:
                        db.add_membership(exec_id, new_cat.lower(), new_name, new_num)
                        st.success(f"Added {new_name}")
                        st.rerun()
                    else:
                        st.warning("Fill in both fields.")

                # Delete Executive
                st.divider()
                if st.button("🗑️ Delete Executive", type="primary"):
                    st.session_state["show_delete_exec_confirm_tab"] = True

                if st.session_state.get("show_delete_exec_confirm_tab", False):
                    st.warning("⚠️ You are about to delete this executive.")
                    trip_count = db.get_executive_trip_count(exec_id)
                    exec_name = profile.get("name", "Unknown")
                    if trip_count > 0:
                        st.error(
                            f"⚠️ **{exec_name}** has **{trip_count}** trip(s). They will be permanently deleted."
                        )
                    else:
                        st.info(
                            f"**{exec_name}** has no trips. They can be safely deleted."
                        )
                    st.markdown("**This action cannot be undone.**")
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button(
                            "✅ Yes, Permanently Delete", key="confirm_delete_exec_tab"
                        ):
                            success, msg = db.delete_executive(exec_id, force=True)
                            if success:
                                st.success(msg)
                                st.session_state["show_delete_exec_confirm_tab"] = False
                                if "current_trip_id" in st.session_state:
                                    del st.session_state["current_trip_id"]
                                if "trip_stops_inline" in st.session_state:
                                    st.session_state["trip_stops_inline"] = []
                                st.rerun()
                            else:
                                st.error(msg)
                    with col2:
                        if st.button("❌ Cancel", key="cancel_delete_exec_tab"):
                            st.session_state["show_delete_exec_confirm_tab"] = False
                            st.rerun()

            else:
                # No profile – show Add Executive in a collapsed expander
                with st.expander("➕ Add New Executive", expanded=False):
                    st.subheader("👤 Add Executive")
                    companies = db.get_all_companies()
                    company_options = {name: id for id, name in companies}
                    tz_display_names, tz_map = get_timezone_dropdown_options()
                    default_display = next(
                        (n for n in tz_display_names if "America/New_York" in n),
                        tz_display_names[0],
                    )

                    with st.form("add_exec_form_tab", clear_on_submit=True):
                        exec_name = st.text_input("Full Name*", key="exec_name_tab")
                        exec_email = st.text_input("Email", key="exec_email_tab")
                        if companies:
                            sel_company = st.selectbox(
                                "Company*",
                                list(company_options.keys()),
                                key="exec_company_tab",
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
                        exec_hotel = st.text_input(
                            "Hotel Loyalty Program", key="exec_hotel_tab"
                        )
                        exec_ff = st.text_input(
                            "Frequent Flyer Number", key="exec_ff_tab"
                        )
                        exec_diet = st.text_input(
                            "Dietary Restrictions", key="exec_diet_tab"
                        )
                        exec_passport = st.text_input(
                            "Passport Number", key="exec_passport_tab"
                        )
                        exec_airline = st.text_input(
                            "Preferred Airline", key="exec_airline_tab"
                        )
                        exec_tsa = st.text_input("TSA PreCheck", key="exec_tsa_tab")
                        exec_meal = st.selectbox(
                            "Meal Preference",
                            [
                                "No Preference",
                                "Vegetarian",
                                "Vegan",
                                "Kosher",
                                "Halal",
                                "Gluten-Free",
                            ],
                            key="exec_meal_tab",
                        )

                        if st.form_submit_button("Add Executive"):
                            if exec_name and sel_company_id:
                                if exec_email:
                                    existing = (
                                        duplicate_detection.find_duplicate_executive(
                                            exec_email, exec_name, sel_company_id
                                        )
                                    )
                                    if existing:
                                        st.warning(
                                            "⚠️ An executive with the same email or name+company already exists:"
                                        )
                                        for dup in existing:
                                            st.write(
                                                f"- {dup['name']} (ID: {dup['id']})"
                                            )
                                        if not st.checkbox(
                                            "Add anyway?", key="force_add_exec_tab"
                                        ):
                                            st.stop()
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
                                st.session_state.show_edit_form = True
                                st.rerun()
                            else:
                                st.warning("Name and Company are required.")

            # Global duplicate scan
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

        elif i == 2:
            # --- TRIP TEMPLATES ---
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
                                st.write(
                                    f"City: {template_data.get('departure_city', 'N/A')}"
                                )
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
                                if st.button(
                                    "Close Preview", key=f"close_preview_{t['id']}"
                                ):
                                    st.session_state[f"preview_template_{t['id']}"] = (
                                        False
                                    )
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
                                    "Start Date*",
                                    value=datetime.now() + timedelta(days=7),
                                )
                            with col2:
                                new_budget = st.number_input(
                                    "Budget", min_value=0.0, step=100.0, value=1000.0
                                )
                                new_end = st.date_input(
                                    "End Date*",
                                    value=datetime.now() + timedelta(days=10),
                                )
                            submitted = st.form_submit_button(
                                "🚀 Create Trip from Template"
                            )
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
                                        st.session_state["current_trip_id"] = (
                                            new_trip_id
                                        )
                                        st.session_state["trip_stops_inline"] = (
                                            db.get_trip_stops(new_trip_id)
                                        )
                                        st.success(
                                            f"✅ Trip '{new_trip_name}' created from template!"
                                        )
                                        st.rerun()
                                    else:
                                        st.error("Failed to create trip from template.")
                                else:
                                    st.warning("Please fill in all required fields.")

        else:  # i == 3
            # --- SPENDING DASHBOARD ---
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
            if summary_data:
                st.subheader("Trip-Level Breakdown")
                for trip in summary_data:
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
                            st.write(f"{trip_symbol}{trip['budget']:.2f}")
                        with col5:
                            st.write(f"{trip_symbol}{trip['total_spent']:.2f}")
                        with col6:
                            st.write(f"{trip_symbol}{trip['confirmed_spent']:.2f}")
                        with col7:
                            st.write(f"{trip_symbol}{trip['estimated_spent']:.2f}")
                        with col8:
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
                        with col9:
                            if st.button("📂", key=f"open_trip_dash_{trip['trip_id']}"):
                                # Open modal for editing this trip
                                st.session_state["editing_trip_id"] = trip["trip_id"]
                                st.session_state["show_edit_trip_dashboard"] = True
                                st.rerun()
                        with col10:
                            if st.button("🗑️", key=f"del_trip_dash_{trip['trip_id']}"):
                                st.session_state[
                                    f"confirm_del_trip_{trip['trip_id']}"
                                ] = True
                                st.rerun()

                        if st.session_state.get(
                            f"confirm_del_trip_{trip['trip_id']}", False
                        ):
                            st.warning(
                                f"⚠️ Permanently delete trip to {trip['destination']}?"
                            )
                            col_yes, col_no = st.columns(2)
                            with col_yes:
                                if st.button(
                                    "✅ Yes, Delete",
                                    key=f"confirm_yes_dash_{trip['trip_id']}",
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
                                if st.button(
                                    "❌ Cancel",
                                    key=f"confirm_no_dash_{trip['trip_id']}",
                                ):
                                    st.session_state.pop(
                                        f"confirm_del_trip_{trip['trip_id']}", None
                                    )
                                    st.rerun()
                        st.divider()

                # Show the edit trip modal if flag is set
                if st.session_state.get("show_edit_trip_dashboard", False):
                    edit_trip_dashboard_dialog()
                    # After modal closes, reset flag (happens automatically when dialog returns)

                # Export
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
                    if st.button(
                        "📄 Export Spending Report (Word)", key="dash_report_tab"
                    ):
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
                            summary_data,
                            get_currency_symbol("USD"),
                            "USD",
                            base_currency="USD",
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
