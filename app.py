import streamlit as st
import database as db
import doc_generator
import utils
from datetime import datetime
import csv
import io
import pytz


# --- Safe Helper ---
def safe_index(options, value, default="No Preference"):
    """
    Safely find the index of a value in a list.
    If the value isn't found, return the index of the default.
    """
    if value is None:
        value = default
    try:
        return options.index(value)
    except ValueError:
        return options.index(default)


# --- Timezone Dropdown Helper ---
def get_timezone_dropdown_options():
    """
    Builds a list of display names like 'America/New_York (EDT)'
    and a mapping to the actual timezone string.
    """
    display_names = []
    tz_map = {}

    for tz in sorted(pytz.common_timezones):
        try:
            # Get the current time in this timezone to fetch the abbreviation
            now = datetime.now(pytz.timezone(tz))
            abbr = now.strftime("%Z")  # Returns 'EDT', 'GMT', 'WAT', etc.

            # Fallback to UTC offset if abbreviation is empty
            if not abbr:
                abbr = now.strftime("%z")

            display = f"{tz} ({abbr})"
        except Exception:
            # If anything fails, just show the raw timezone
            display = tz

        display_names.append(display)
        tz_map[display] = tz  # Map display string back to actual timezone

    return display_names, tz_map


# --- Page Config ---
st.set_page_config(page_title="Executive Travel Planner", layout="wide")

# --- Initialize Currency in Session State ---
if "currency_symbol" not in st.session_state:
    st.session_state["currency_symbol"] = "$"
if "currency_code" not in st.session_state:
    st.session_state["currency_code"] = "USD"

st.title("✈️ Executive Travel Planner")

# --- Initialize Database ---
db.init_db()

# --- SIDEBAR: EXECUTIVE SELECTION & MANAGEMENT ---
st.sidebar.header("👤 Select Executive")

# --- Currency Selector ---
st.sidebar.divider()
st.sidebar.subheader("💱 Currency Settings")

currency_options = {
    "$ (USD)": {"symbol": "$", "code": "USD"},
    "€ (EUR)": {"symbol": "€", "code": "EUR"},
    "£ (GBP)": {"symbol": "£", "code": "GBP"},
    "₦ (NGN)": {"symbol": "₦", "code": "NGN"},
    "¥ (JPY)": {"symbol": "¥", "code": "JPY"},
    "R$ (BRL)": {"symbol": "R$", "code": "BRL"},
}

selected_currency_label = st.sidebar.selectbox(
    "Select Currency", list(currency_options.keys()), index=0
)
selected_currency = currency_options[selected_currency_label]

if st.session_state["currency_symbol"] != selected_currency["symbol"]:
    st.session_state["currency_symbol"] = selected_currency["symbol"]
    st.session_state["currency_code"] = selected_currency["code"]
    st.rerun()

st.sidebar.divider()

# --- Management Interface ---
with st.sidebar.expander("⚙️ Manage Executives & Companies"):

    # Add Company
    st.subheader("🏢 Add Company")
    with st.form("add_company_form", clear_on_submit=True):
        comp_name = st.text_input("Company Name")
        comp_cc = st.text_input("Default Cost Center (optional)")
        comp_policy = st.text_area("Policy Notes (optional)")
        comp_submitted = st.form_submit_button("Add Company")
        if comp_submitted and comp_name:
            db.add_company(comp_name, comp_cc, comp_policy)
            st.success(f"Company '{comp_name}' added!")
            st.rerun()
        elif comp_submitted:
            st.warning("Company Name is required.")

    st.divider()

    # Add Executive
    st.subheader("👤 Add Executive")
    companies = db.get_all_companies()
    company_options = {name: id for id, name in companies}

    # --- Get Timezone Dropdown Options ---
    tz_display_names, tz_map = get_timezone_dropdown_options()

    # Set default to America/New_York
    default_display = None
    for name in tz_display_names:
        if "America/New_York" in name:
            default_display = name
            break
    if default_display is None:
        default_display = tz_display_names[0]

    with st.form("add_exec_form", clear_on_submit=True):
        exec_name = st.text_input("Full Name*")
        exec_email = st.text_input("Email")

        if companies:
            selected_company_label = st.selectbox(
                "Company*", list(company_options.keys())
            )
            selected_company_id = company_options[selected_company_label]
        else:
            st.warning("Please add a company first.")
            selected_company_id = None

        # --- Timezone Dropdown ---
        selected_tz_display = st.selectbox(
            "Timezone",
            options=tz_display_names,
            index=tz_display_names.index(default_display),
            help="Select the executive's primary timezone",
        )
        exec_tz = tz_map[
            selected_tz_display
        ]  # Store raw timezone string (e.g., 'America/New_York')

        exec_seat = st.selectbox(
            "Seat Preference", ["No Preference", "Aisle", "Window", "Middle"]
        )
        exec_hotel = st.text_input("Hotel Loyalty Program (e.g., Marriott Bonvoy Gold)")
        exec_ff = st.text_input("Frequent Flyer Number")
        exec_diet = st.text_input("Dietary Restrictions")
        exec_passport = st.text_input("Passport Number")
        exec_airline = st.text_input("Preferred Airline")
        exec_tsa = st.text_input("TSA PreCheck / Known Traveler #")
        exec_meal = st.selectbox(
            "Meal Preference",
            ["No Preference", "Vegetarian", "Vegan", "Kosher", "Halal", "Gluten-Free"],
        )

        exec_submitted = st.form_submit_button("Add Executive")
        if exec_submitted and exec_name and selected_company_id:
            db.add_executive(
                selected_company_id,
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
        elif exec_submitted:
            st.warning("Name and Company are required.")

st.sidebar.divider()

# --- Load and Select Executive ---
executives = db.get_all_executives()
if not executives:
    st.sidebar.warning("No executives found. Add one using the manager above.")
    st.stop()

exec_options = {f"{name} (ID: {id})": id for id, name, _ in executives}
selected_label = st.sidebar.selectbox("Choose Executive", list(exec_options.keys()))
exec_id = exec_options[selected_label]
profile = db.get_executive_profile(exec_id)

# --- Display Profile in Sidebar ---
if profile:
    st.sidebar.subheader("📋 Profile")
    st.sidebar.write(f"**Company:** {profile.get('company_name', 'N/A')}")
    st.sidebar.write(f"**Timezone:** {profile.get('timezone', 'N/A')}")
    st.sidebar.write(f"**Seat:** {profile.get('seat_preference', 'N/A')}")
    st.sidebar.write(f"**Airline:** {profile.get('preferred_airline', 'N/A')}")
    st.sidebar.write(f"**Passport:** {profile.get('passport_number', 'N/A')}")
    st.sidebar.write(f"**Meal:** {profile.get('meal_preference', 'N/A')}")

    # --- EDIT EXECUTIVE BUTTON ---
    if st.sidebar.button("✏️ Edit Executive"):
        st.session_state["editing_exec"] = True
        st.rerun()

# --- Sidebar: Export Profile ---
st.sidebar.divider()
st.sidebar.subheader("📤 Export Profile")
col_csv, col_doc = st.sidebar.columns(2)

with col_csv:
    if st.button("📊 CSV"):
        profile_data = db.get_full_executive_profile(exec_id)
        if profile_data:
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=profile_data.keys())
            writer.writeheader()
            writer.writerow(profile_data)
            csv_data = output.getvalue()
            st.download_button(
                label="⬇️ Download",
                data=csv_data,
                file_name=f"{profile_data['Name']}_profile.csv",
                mime="text/csv",
                key="csv_download",
            )

with col_doc:
    if st.button("📄 Word"):
        profile_data = db.get_full_executive_profile(exec_id)
        if profile_data:
            doc_stream = doc_generator.generate_executive_profile_doc(
                profile_data, st.session_state["currency_symbol"]
            )
            st.download_button(
                label="⬇️ Download",
                data=doc_stream,
                file_name=f"{profile_data['Name']}_Profile.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml",
                key="docx_download",
            )

# --- MAIN AREA: TRIP SETUP ---
st.header("📅 Trip Details")

col1, col2, col3 = st.columns(3)
with col1:
    destination = st.text_input("Destination (City)")
with col2:
    start_date = st.date_input("Start Date")
with col3:
    end_date = st.date_input("End Date")

purpose = st.text_input("Trip Purpose / Notes")

# --- Currency-aware Budget Input ---
budget = st.number_input(
    f"💰 Trip Budget ({st.session_state['currency_code']})",
    min_value=0.0,
    step=100.0,
    value=0.0,
)

if st.button("🚀 Create or Update Trip"):
    if destination and start_date and end_date:
        trip_id = db.create_or_get_trip(
            exec_id, destination, start_date.isoformat(), end_date.isoformat(), purpose
        )
        db.update_trip_budget(trip_id, budget)
        st.session_state["current_trip_id"] = trip_id
        st.success(
            f"Trip ready! Budget set to {st.session_state['currency_symbol']}{budget:,.2f}"
        )
    else:
        st.warning("Please fill in destination and dates.")

# --- EDIT EXECUTIVE (Pop-up / Expandable) ---
if st.session_state.get("editing_exec", False):
    with st.expander("✏️ Edit Executive Profile", expanded=True):
        st.info(f"Editing: {profile['name']}")

        companies = db.get_all_companies()
        company_options = {name: id for id, name in companies}
        current_company_id = profile.get("company_id")

        # --- Get Timezone Dropdown Options ---
        tz_display_names, tz_map = get_timezone_dropdown_options()

        # Find the current timezone in the display list
        current_tz = profile.get("timezone", "America/New_York")
        current_tz_display = None
        for name in tz_display_names:
            if current_tz in name:
                current_tz_display = name
                break
        if current_tz_display is None:
            current_tz_display = tz_display_names[0]

        with st.form("edit_exec_form"):
            # --- Company Dropdown ---
            current_company_name = "Select"
            for name, cid in company_options.items():
                if cid == current_company_id:
                    current_company_name = name
                    break

            new_company_label = st.selectbox(
                "Company*",
                list(company_options.keys()),
                index=(
                    list(company_options.keys()).index(current_company_name)
                    if current_company_name in company_options
                    else 0
                ),
            )
            new_company_id = company_options[new_company_label]

            # --- Text Fields (Always Visible) ---
            new_name = st.text_input("Full Name*", value=profile.get("name", ""))
            new_email = st.text_input("Email", value=profile.get("email", ""))

            # --- Timezone Dropdown (Edit) ---
            new_tz_display = st.selectbox(
                "Timezone",
                options=tz_display_names,
                index=tz_display_names.index(current_tz_display),
                help="Select the executive's primary timezone",
            )
            new_tz = tz_map[new_tz_display]  # Store raw timezone string

            # --- Seat Preference (Dropdown - Fixed) ---
            seat_options = ["No Preference", "Aisle", "Window", "Middle"]
            new_seat = st.selectbox(
                "Seat Preference",
                options=seat_options,
                index=safe_index(
                    seat_options, profile.get("seat_preference", "No Preference")
                ),
            )

            # --- Text Fields (Visible after seat dropdown) ---
            new_hotel = st.text_input(
                "Hotel Loyalty", value=profile.get("hotel_loyalty", "")
            )
            new_ff = st.text_input(
                "Frequent Flyer Number", value=profile.get("frequent_flyer_number", "")
            )
            new_diet = st.text_input(
                "Dietary Restrictions", value=profile.get("dietary_restrictions", "")
            )
            new_passport = st.text_input(
                "Passport Number", value=profile.get("passport_number", "")
            )
            new_airline = st.text_input(
                "Preferred Airline", value=profile.get("preferred_airline", "")
            )
            new_tsa = st.text_input(
                "TSA PreCheck", value=profile.get("tsa_precheck", "")
            )

            # --- Meal Preference (Dropdown - Fixed) ---
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
                options=meal_options,
                index=safe_index(
                    meal_options, profile.get("meal_preference", "No Preference")
                ),
            )

            # --- BUTTONS ---
            col_save, col_cancel = st.columns(2)
            with col_save:
                submitted = st.form_submit_button("💾 Save Changes")
            with col_cancel:
                cancel = st.form_submit_button("❌ Cancel")

            # --- Submit Logic ---
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
                st.success(f"✅ Executive '{new_name}' updated successfully!")
                st.session_state["editing_exec"] = False
                st.rerun()

            if cancel:
                st.session_state["editing_exec"] = False
                st.rerun()

# --- ADD ITINERARY ITEMS ---
if "current_trip_id" in st.session_state:
    trip_id = st.session_state["current_trip_id"]

    st.subheader("➕ Add Itinerary Item")
    with st.form("add_item_form"):
        cols = st.columns(4)
        with cols[0]:
            item_type = st.selectbox(
                "Type", ["Flight", "Hotel", "Meeting", "Transport"]
            )
        with cols[1]:
            desc = st.text_input("Description (e.g., 'Delta 1234')")
        with cols[2]:
            dt_start = st.datetime_input("Start Time", value=datetime.now())
        with cols[3]:
            dt_end = st.datetime_input("End Time", value=datetime.now())

        col_loc, col_cost, col_conf = st.columns(3)
        with col_loc:
            location = st.text_input("Location/Venue")
        with col_cost:
            cost = st.number_input(
                f"Cost ({st.session_state['currency_code']})", min_value=0.0, step=10.0
            )
        with col_conf:
            conf_code = st.text_input("Confirmation Code")

        notes = st.text_area("Notes")
        confirmed = st.checkbox(
            "✅ Confirmed / Booked (check if this is a final booking)"
        )

        submitted = st.form_submit_button("Add to Itinerary")

        if submitted and desc and dt_start:
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
            )
            st.success(f"✅ Added: {desc}")
            st.rerun()

    # --- DISPLAY CURRENT ITINERARY & SPENDING ---
    st.divider()
    st.subheader("📋 Current Itinerary")

    items = db.get_items_for_trip(trip_id)
    trip_data = db.get_trip(trip_id)
    trip_budget = trip_data.get("budget", 0) if trip_data else 0

    if items:
        # --- SPENDING SUMMARY (Currency-aware) ---
        spending = db.get_trip_spending(trip_id)

        st.subheader("💰 Spending Summary")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric(
                "Total Estimated (Quoted)",
                f"{st.session_state['currency_symbol']}{spending['total_estimated']:,.2f}",
            )
        with col2:
            st.metric(
                "✅ Confirmed (Booked)",
                f"{st.session_state['currency_symbol']}{spending['total_confirmed']:,.2f}",
            )
        with col3:
            st.metric(
                "📊 Total Spend",
                f"{st.session_state['currency_symbol']}{spending['total_all']:,.2f}",
            )
        with col4:
            budget_remaining = trip_budget - spending["total_all"]
            st.metric(
                "💰 Budget",
                f"{st.session_state['currency_symbol']}{trip_budget:,.2f}",
                delta=f"{st.session_state['currency_symbol']}{budget_remaining:,.2f} remaining",
                delta_color="inverse" if budget_remaining < 0 else "normal",
            )

        # Budget Progress Bar
        if trip_budget > 0:
            percent_used = min((spending["total_all"] / trip_budget) * 100, 100)
            color = (
                "green"
                if percent_used < 80
                else "orange" if percent_used < 100 else "red"
            )
            st.progress(percent_used / 100, text=f"{percent_used:.0f}% of budget used")

        st.divider()

        # --- CONFLICTS ---
        conflicts = utils.detect_conflicts(items)
        if conflicts:
            st.warning("⚠️ Conflicts Detected:")
            for c in conflicts:
                st.write(f"- {c}")
        else:
            st.success("✅ No scheduling conflicts detected.")

        # --- DISPLAY ITEMS (Currency-aware) ---
        st.subheader("📋 Itinerary Items")
        for item in items:
            start_display = datetime.fromisoformat(item["datetime_start"]).strftime(
                "%b %d, %H:%M"
            )
            end_display = (
                datetime.fromisoformat(item["datetime_end"]).strftime("%H:%M")
                if item["datetime_end"]
                else "TBD"
            )
            cost_display = (
                f"{st.session_state['currency_symbol']}{item['cost']:.2f}"
                if item.get("cost")
                else "-"
            )
            status_icon = "✅" if item.get("is_confirmed") else "📌"
            st.write(
                f"{status_icon} **{start_display} – {end_display}**  |  {item['item_type']}: {item['description']}  |  Cost: {cost_display}"
            )

        # --- EXPORT BUTTONS ---
        st.divider()
        col_gen, col_cal = st.columns(2)

        with col_gen:
            if st.button("📄 Generate Word Itinerary"):
                executive_data = db.get_executive_profile(exec_id)
                doc_stream, filename = doc_generator.generate_itinerary_doc(
                    executive_data,
                    items,
                    destination,
                    trip_id,
                    trip_budget,
                    st.session_state["currency_symbol"],
                    st.session_state["currency_code"],
                )
                st.download_button(
                    label="⬇️ Download Word Doc",
                    data=doc_stream,
                    file_name=f"{executive_data['name']}_{destination}_itinerary.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml",
                    key="itinerary_download",
                )
                st.success(f"Document saved locally: {filename}")

        with col_cal:
            if st.button("📅 Export to Calendar (.ics)"):
                exec_timezone = profile.get("timezone", "America/New_York")
                ics_data = utils.generate_ics(items, exec_timezone, destination)
                st.download_button(
                    label="⬇️ Download .ics",
                    data=ics_data,
                    file_name=f"{profile['name']}_itinerary.ics",
                    mime="text/calendar",
                    key="ics_download",
                )
    else:
        st.info("No itinerary items yet. Add flights, hotels, or meetings above.")

# --- SPENDING DASHBOARD (All Trips) - WITHOUT PANDAS ---
st.divider()
with st.expander("📊 Spending Dashboard (All Trips)"):
    st.subheader("Filter & View Aggregate Spending")

    col_dash1, col_dash2 = st.columns(2)
    with col_dash1:
        exec_filter_options = ["All"] + [
            f"{name} (ID: {id})" for id, name, _ in executives
        ]
        exec_filter = st.selectbox("Filter by Executive", exec_filter_options)
        exec_id_filter = None
        if exec_filter != "All":
            exec_id_filter = int(exec_filter.split("(ID: ")[1].rstrip(")"))

    with col_dash2:
        date_range = st.date_input("Date Range (optional)", value=[])

    start_filter = date_range[0].isoformat() if len(date_range) > 0 else None
    end_filter = date_range[1].isoformat() if len(date_range) > 1 else None

    summary_data = db.get_spending_summary(
        exec_id=exec_id_filter, start_date=start_filter, end_date=end_filter
    )

    if summary_data:
        # Aggregate metrics
        total_budget = sum(t["budget"] for t in summary_data)
        total_spent = sum(t["total_spent"] for t in summary_data)
        total_confirmed = sum(t["confirmed_spent"] for t in summary_data)
        total_estimated = sum(t["estimated_spent"] for t in summary_data)

        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        col_m1.metric("Total Trips", len(summary_data))
        col_m2.metric(
            "Total Budget", f"{st.session_state['currency_symbol']}{total_budget:,.2f}"
        )
        col_m3.metric(
            "Total Spent", f"{st.session_state['currency_symbol']}{total_spent:,.2f}"
        )
        col_m4.metric(
            "Total Confirmed",
            f"{st.session_state['currency_symbol']}{total_confirmed:,.2f}",
        )

        # --- Display Table without pandas ---
        st.subheader("Trip-Level Breakdown")

        # Build table headers and rows
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
            rows.append(
                [
                    trip["executive_name"],
                    trip["company_name"],
                    trip["destination"],
                    f"{st.session_state['currency_symbol']}{trip['budget']:.2f}",
                    f"{st.session_state['currency_symbol']}{trip['total_spent']:.2f}",
                    f"{st.session_state['currency_symbol']}{trip['confirmed_spent']:.2f}",
                    f"{st.session_state['currency_symbol']}{trip['estimated_spent']:.2f}",
                    trip["status"],
                ]
            )

        # Render as a Markdown table (works nicely in Streamlit)
        markdown_table = "| " + " | ".join(headers) + " |\n"
        markdown_table += "| " + " | ".join(["---"] * len(headers)) + " |\n"
        for row in rows:
            markdown_table += "| " + " | ".join(str(cell) for cell in row) + " |\n"
        st.markdown(markdown_table)

        # --- Export CSV without pandas ---
        col_exp1, col_exp2 = st.columns(2)
        with col_exp1:
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(headers + ["Currency"])
            for row in rows:
                writer.writerow(row + [st.session_state["currency_code"]])
            csv_data = output.getvalue().encode("utf-8")
            st.download_button(
                label="📊 Export Dashboard CSV",
                data=csv_data,
                file_name=f"spending_summary_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
            )
        with col_exp2:
            if st.button("📄 Export Spending Report (Word)"):
                exec_name_filter = (
                    exec_filter if exec_filter != "All" else "All Executives"
                )
                doc_stream = doc_generator.generate_spending_report_doc(
                    exec_name_filter,
                    summary_data,
                    start_filter,
                    end_filter,
                    st.session_state["currency_symbol"],
                )
                st.download_button(
                    label="⬇️ Download Word Report",
                    data=doc_stream,
                    file_name=f"spending_report_{datetime.now().strftime('%Y%m%d')}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml",
                    key="spending_report_download",
                )
    else:
        st.info("No trips found matching the filters.")
