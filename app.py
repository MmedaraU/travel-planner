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
from openpyxl import Workbook
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
# SIDEBAR: Executive Selection & Full Management
# =========================================================
st.sidebar.header("👤 Executive Management")

executives = db.get_all_executives()
if not executives:
    st.sidebar.warning("No executives found. Add one using the button below.")
    exec_id = None
    profile = None
else:
    exec_options = {f"{name} (ID: {id})": id for id, name, _ in executives}
    selected_label = st.sidebar.selectbox("Choose Executive", list(exec_options.keys()))
    exec_id = exec_options[selected_label]
    profile = db.get_executive_profile(exec_id)

# --- "Add New Executive" Button (opens popover) ---
if st.sidebar.button("➕ Add New Executive", use_container_width=True):
    st.session_state["show_add_executive"] = True

if st.session_state.get("show_add_executive", False):
    with st.popover("➕ Add New Executive", use_container_width=True):
        st.subheader("Add New Executive")

        # ---- Add Company (inline, outside the form) ----
        with st.expander("➕ Add New Company"):
            new_comp_name = st.text_input("Company Name", key="add_new_comp_name")
            new_comp_cc = st.text_input(
                "Default Cost Center (optional)", key="add_new_comp_cc"
            )
            new_comp_policy = st.text_area(
                "Policy Notes (optional)", key="add_new_comp_policy"
            )
            if st.button("Add Company", key="add_new_comp_btn"):
                if new_comp_name:
                    db.add_company(new_comp_name, new_comp_cc, new_comp_policy)
                    st.success(f"Company '{new_comp_name}' added!")
                    st.rerun()
                else:
                    st.warning("Company Name required.")

        # ---- Main form for executive creation ----
        with st.form("add_executive_form"):
            # Company dropdown
            companies = db.get_all_companies()
            company_options = {name: id for id, name in companies}
            company_names = list(company_options.keys())
            if company_names:
                sel_company_label = st.selectbox(
                    "Company*", company_names, key="add_company_sel"
                )
                sel_company_id = company_options[sel_company_label]
            else:
                st.warning(
                    "No companies available. Please add a company first using the expander above."
                )
                sel_company_id = None

            # Executive fields
            exec_name = st.text_input("Full Name*", key="add_exec_name")
            exec_email = st.text_input("Email", key="add_exec_email")
            tz_display_names, tz_map = get_timezone_dropdown_options()
            default_tz = next(
                (n for n in tz_display_names if "America/New_York" in n),
                tz_display_names[0],
            )
            sel_tz = st.selectbox(
                "Timezone",
                tz_display_names,
                index=tz_display_names.index(default_tz),
                key="add_exec_tz",
            )
            exec_tz = tz_map[sel_tz]
            exec_seat = st.selectbox(
                "Seat Preference",
                ["No Preference", "Aisle", "Window", "Middle"],
                key="add_exec_seat",
            )
            exec_diet = st.text_input("Dietary Restrictions", key="add_exec_diet")
            exec_airline = st.text_input("Preferred Airline", key="add_exec_airline")
            exec_tsa = st.text_input("TSA PreCheck", key="add_exec_tsa")
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
                key="add_exec_meal",
            )

            # Submit button inside the form
            if st.form_submit_button("💾 Create Executive"):
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
                            if not st.checkbox("Add anyway?", key="force_add_exec"):
                                st.stop()
                    new_id = db.add_executive(
                        sel_company_id,
                        exec_name,
                        exec_email,
                        exec_tz,
                        exec_seat if exec_seat != "No Preference" else "",
                        "",  # hotel_loyalty removed
                        "",  # frequent_flyer_number removed
                        exec_diet,
                        None,  # passport_number removed
                        exec_airline,
                        exec_tsa,
                        exec_meal if exec_meal != "No Preference" else "",
                    )
                    st.success(
                        f"✅ Executive '{exec_name}' created! You can now add passports and memberships in the edit modal."
                    )
                    st.session_state["show_add_executive"] = False
                    st.rerun()
                else:
                    st.warning("Name and Company are required.")

# --- Quick Profile (collapsible) ---
if profile:
    with st.sidebar.expander("📋 Quick Profile", expanded=False):
        st.write(f"**{profile['name']}**")
        st.write(f"🏢 {profile.get('company_name', 'N/A')}")
        st.write(f"🕐 {profile.get('timezone', 'N/A')}")
        st.write(f"💺 {profile.get('seat_preference', 'N/A')}")
        mems = db.get_memberships(exec_id)
        if mems:
            st.caption(f"✈️ {len(mems)} memberships")

        if st.button("👤 View Full Profile", use_container_width=True):
            st.session_state["show_full_profile"] = True
            st.session_state["profile_edit_mode"] = False

# --- Full Profile Popover (Read-Only + Edit/Delete with Passports & Memberships) ---
if st.session_state.get("show_full_profile", False):
    with st.popover("👤 Full Profile", use_container_width=True):
        # -------- EDIT MODE --------
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
                    "Full Name*", value=profile.get("name", ""), key="edit_name_popover"
                )
                new_email = st.text_input(
                    "Email", value=profile.get("email", ""), key="edit_email_popover"
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
                        seat_options, profile.get("seat_preference", "No Preference")
                    ),
                    key="edit_seat_popover",
                )
                new_diet = st.text_input(
                    "Dietary Restrictions",
                    value=profile.get("dietary_restrictions", ""),
                    key="edit_diet_popover",
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
                        meal_options, profile.get("meal_preference", "No Preference")
                    ),
                    key="edit_meal_popover",
                )

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
                        None,  # passport_number removed
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
                    st.warning(f"⚠️ Permanently delete executive '{profile['name']}'?")
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

            # ---- PASSPORTS (EDIT MODE) ----
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
                        if st.button("🗑️", key=f"del_pass_edit_{p['id']}"):
                            db.delete_passport(p["id"])
                            st.rerun()
            else:
                st.caption("No passports added.")

            with st.expander("➕ Add Passport"):
                col_c, col_n = st.columns(2)
                with col_c:
                    new_country = st.text_input("Country", key="edit_pass_country")
                with col_n:
                    new_pass_num = st.text_input("Passport Number", key="edit_pass_num")
                col_e, col_i = st.columns(2)
                with col_e:
                    new_expiry = st.date_input(
                        "Expiry Date", value=None, key="edit_pass_expiry"
                    )
                with col_i:
                    new_issued = st.date_input(
                        "Issued Date", value=None, key="edit_pass_issued"
                    )
                new_notes_pass = st.text_area("Notes", key="edit_pass_notes")
                if st.button("➕ Add Passport", key="edit_pass_btn"):
                    if new_country and new_pass_num:
                        db.add_passport(
                            exec_id,
                            new_country,
                            new_pass_num,
                            expiry_date=new_expiry.isoformat() if new_expiry else None,
                            issued_date=new_issued.isoformat() if new_issued else None,
                            notes=new_notes_pass,
                        )
                        st.rerun()
                    else:
                        st.warning("Country and Passport Number required.")

            # ---- MEMBERSHIPS (EDIT MODE) ----
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
                        if st.button("🗑️", key=f"del_mem_edit_{m['id']}"):
                            db.delete_membership(m["id"])
                            st.rerun()
            else:
                st.caption("No memberships added.")

            with st.expander("➕ Add Membership"):
                col_cat, col_name, col_num = st.columns(3)
                with col_cat:
                    new_cat = st.selectbox(
                        "Category",
                        ["Airline", "Hotel", "Car Rental"],
                        key="edit_mem_cat",
                    )
                with col_name:
                    new_name_mem = st.text_input("Program Name", key="edit_mem_name")
                with col_num:
                    new_num_mem = st.text_input("Membership Number", key="edit_mem_num")
                # Extra fields inside nested expander (hidden by default)
                with st.expander("➕ More details (optional)"):
                    col_extra1, col_extra2 = st.columns(2)
                    if new_cat == "Airline":
                        with col_extra1:
                            new_tier = st.text_input("Tier", key="edit_mem_tier")
                            new_alliance = st.text_input(
                                "Alliance", key="edit_mem_alliance"
                            )
                        with col_extra2:
                            new_airport = st.text_input(
                                "Airport Code", key="edit_mem_airport"
                            )
                            new_notes_mem = st.text_area("Notes", key="edit_mem_notes")
                        new_alliance = new_alliance or None
                        new_airport = new_airport or None
                    elif new_cat == "Hotel":
                        with col_extra1:
                            new_tier = st.text_input("Status/Tier", key="edit_mem_tier")
                        with col_extra2:
                            new_notes_mem = st.text_area("Notes", key="edit_mem_notes")
                        new_alliance = None
                        new_airport = None
                    else:  # Car
                        with col_extra1:
                            new_notes_mem = st.text_area("Notes", key="edit_mem_notes")
                        new_tier = None
                        new_alliance = None
                        new_airport = None

                if st.button("➕ Add Membership", key="edit_mem_add_btn"):
                    if new_name_mem and new_num_mem:
                        db.add_membership(
                            exec_id,
                            new_cat.lower(),
                            new_name_mem,
                            new_num_mem,
                            tier=new_tier,
                            alliance=new_alliance,
                            airport_code=new_airport,
                            notes=new_notes_mem,
                        )
                        st.rerun()
                    else:
                        st.warning("Program Name and Membership Number required.")

        # -------- READ-ONLY MODE --------
        else:
            profile_data = db.get_full_executive_profile(exec_id)
            if profile_data:
                for key, value in profile_data.items():
                    st.write(f"**{key}:** {value}")

            # ---- PASSPORTS (READ-ONLY) ----
            st.divider()
            st.subheader("🛂 Passports")
            passports = db.get_passports(exec_id)
            if passports:
                for p in passports:
                    col1, col2, col3 = st.columns([2, 2, 2])
                    with col1:
                        st.write(f"{p['country']}: {p['passport_number']}")
                    with col2:
                        st.write(f"Exp: {p.get('expiry_date') or ''}")
                    with col3:
                        st.write(p.get("notes") or "")
            else:
                st.caption("No passports added.")

            # ---- MEMBERSHIPS (READ-ONLY) ----
            st.subheader("✈️ Memberships")
            mems = db.get_memberships(exec_id)
            if mems:
                for m in mems:
                    col1, col2, col3 = st.columns([2, 2, 2])
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
                        st.write(m.get("notes") or "")
            else:
                st.caption("No memberships added.")

            # ---- ACTION BUTTONS ----
            st.divider()
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("✏️ Edit Executive", use_container_width=True):
                    st.session_state["profile_edit_mode"] = True
                    st.rerun()
            with col2:
                if st.button("🗑️ Delete Executive", use_container_width=True):
                    st.session_state["confirm_delete_from_view"] = True
            with col3:
                if st.button("❌ Close Profile", use_container_width=True):
                    st.session_state["show_full_profile"] = False
                    st.session_state["profile_edit_mode"] = False
                    st.session_state["confirm_delete_from_view"] = False
                    st.rerun()

            if st.session_state.get("confirm_delete_from_view", False):
                st.warning(f"⚠️ Permanently delete executive '{profile['name']}'?")
                trip_count = db.get_executive_trip_count(exec_id)
                if trip_count > 0:
                    st.error(
                        f"⚠️ This executive has {trip_count} trip(s). They will also be deleted."
                    )
                col_yes, col_no = st.columns(2)
                with col_yes:
                    if st.button("✅ Yes, Delete", key="confirm_delete_view_yes"):
                        success, msg = db.delete_executive(exec_id, force=True)
                        if success:
                            st.success(msg)
                            st.session_state["show_full_profile"] = False
                            st.session_state["profile_edit_mode"] = False
                            st.session_state["confirm_delete_from_view"] = False
                            if "current_trip_id" in st.session_state:
                                del st.session_state["current_trip_id"]
                            if "trip_stops" in st.session_state:
                                del st.session_state["trip_stops"]
                            st.rerun()
                        else:
                            st.error(msg)
                with col_no:
                    if st.button("❌ Cancel", key="confirm_delete_view_no"):
                        st.session_state["confirm_delete_from_view"] = False
                        st.rerun()

# Export buttons (collapsible) – moved to sidebar
if profile:
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
                    mems = db.get_memberships(exec_id)
                    mem_str = "; ".join(
                        [f"{m['program_name']}: {m['membership_number']}" for m in mems]
                    )
                    profile_data["Memberships"] = mem_str
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

    # ---- Export All Profiles ----
    with st.sidebar.expander("📤 Export All Profiles", expanded=False):
        all_profiles = db.get_all_executive_profiles()
        if all_profiles:
            col_aw, col_ac, col_ae = st.columns(3)
            with col_aw:
                if st.button("📄 Word (All)"):
                    doc_stream = doc_generator.generate_all_executive_profiles_doc(
                        all_profiles
                    )
                    st.download_button(
                        label="⬇️ Download Word",
                        data=doc_stream,
                        file_name=f"All_Executives_{datetime.now().strftime('%Y%m%d')}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml",
                        key="all_doc_download",
                    )
            with col_ac:
                if st.button("📊 CSV (All)"):
                    output = io.StringIO()
                    if all_profiles:
                        # Use the same headers as single profile (excluding Memberships if needed)
                        # The first profile has all keys; we'll include all.
                        headers = list(all_profiles[0].keys())
                        writer = csv.DictWriter(output, fieldnames=headers)
                        writer.writeheader()
                        for p in all_profiles:
                            writer.writerow(p)
                        st.download_button(
                            label="⬇️ Download CSV",
                            data=output.getvalue().encode("utf-8"),
                            file_name=f"All_Executives_{datetime.now().strftime('%Y%m%d')}.csv",
                            mime="text/csv",
                            key="all_csv_download",
                        )
            with col_ae:
                if st.button("📊 Excel (All)"):
                    from openpyxl import Workbook

                    wb = Workbook()
                    ws = wb.active
                    ws.title = "All Executives"
                    headers = list(all_profiles[0].keys())
                    for col_idx, header in enumerate(headers, 1):
                        ws.cell(row=1, column=col_idx, value=header)
                    for row_idx, p in enumerate(all_profiles, 2):
                        for col_idx, key in enumerate(headers, 1):
                            ws.cell(row=row_idx, column=col_idx, value=p.get(key, ""))
                    excel_stream = io.BytesIO()
                    wb.save(excel_stream)
                    excel_stream.seek(0)
                    st.download_button(
                        label="⬇️ Download Excel",
                        data=excel_stream,
                        file_name=f"All_Executives_{datetime.now().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="all_excel_download",
                    )
        else:
            st.caption("No executives available to export.")

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
# MAIN AREA: TABS (Only Trip Planner, Templates, All Trips, Companies)
# =========================================================
tab_names = [
    "✈️ Trip Planner",
    "📋 Trip Templates",
    "📋 All Trips",
    "🏢 Companies",
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
        st.warning("Please add an executive using the sidebar first.")
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
            "Start Date*",
            value=st.session_state.get("create_overall_start", datetime.now()),
            key="create_overall_start",
        )
    with col_end:
        overall_end = st.date_input(
            "End Date*",
            value=st.session_state.get(
                "create_overall_end", datetime.now() + timedelta(days=1)
            ),
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

    # --- Budget (always in Base Currency) ---
    col_budget1, col_budget2 = st.columns(2)
    with col_budget1:
        budget = st.number_input(
            "Budget Amount (in Base Currency)",
            min_value=0.0,
            step=100.0,
            value=0.0,
            key="create_trip_budget",
        )
    with col_budget2:
        st.write("")  # placeholder

    # --- Currencies (only Base Currency) ---
    st.subheader("💱 Trip Currency")
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
                        # Currency dropdown – all common currencies
                        currency_options = [
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
                        e_currency = st.selectbox(
                            "Currency",
                            options=currency_options,
                            index=(
                                currency_options.index(item.get("cost_currency", "USD"))
                                if item.get("cost_currency", "USD") in currency_options
                                else 0
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
            currency_options = [
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
            n_currency = st.selectbox(
                "Currency",
                options=currency_options,
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
            # Clear all text/number/select/date fields
            keys_to_clear = [
                "create_trip_purpose",
                "create_departure_city",
                "create_departure_region",
                "create_departure_country",
                "create_trip_budget",
                "create_base_currency",
                "create_trip_status",
                "create_overall_start",
                "create_overall_end",
            ]
            for key in keys_to_clear:
                st.session_state.pop(key, None)
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

                # Budget is already in base currency
                budget_base = budget

                trip_id = db.create_or_get_trip(
                    trip_exec_id,
                    dest_summary,
                    overall_start,
                    overall_end,
                    trip_purpose,
                    trip_base_currency,  # display_currency is now same as base
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
                for item in st.session_state["create_trip_items"]:
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

                # ---- Save as Template (after creation) ----
                st.session_state["last_created_trip_id"] = trip_id
                st.session_state["last_created_trip_name"] = trip_purpose

                # Display Save as Template option
                col_save_template, col_continue = st.columns(2)
                with col_save_template:
                    if st.button(
                        "📋 Save as Template", key="save_template_after_create"
                    ):
                        st.session_state["show_save_template_after_create"] = True
                with col_continue:
                    if st.button("Continue", key="continue_after_create"):
                        st.session_state.pop("last_created_trip_id", None)
                        st.session_state.pop("last_created_trip_name", None)
                        st.session_state.pop("show_save_template_after_create", None)
                        st.rerun()

                if st.session_state.get("show_save_template_after_create", False):
                    st.info("Save this trip as a reusable template.")
                    template_name = st.text_input(
                        "Template Name*",
                        value=f"{trip_purpose} Template",
                        key="template_name_after_create",
                    )
                    template_desc = st.text_input(
                        "Description (optional)", key="template_desc_after_create"
                    )
                    col_yes, col_no = st.columns(2)
                    with col_yes:
                        if st.button("💾 Save", key="confirm_save_after_create"):
                            if template_name:
                                new_id = db.save_trip_as_template(
                                    trip_id, template_name, template_desc
                                )
                                if new_id:
                                    st.success(f"✅ Template '{template_name}' saved!")
                                    st.session_state.pop(
                                        "show_save_template_after_create", None
                                    )
                                    st.session_state.pop("last_created_trip_id", None)
                                    st.session_state.pop("last_created_trip_name", None)
                                    st.rerun()
                                else:
                                    st.error("Failed to save template.")
                            else:
                                st.warning("Template Name is required.")
                    with col_no:
                        if st.button("Cancel", key="cancel_save_after_create"):
                            st.session_state.pop(
                                "show_save_template_after_create", None
                            )
                            st.rerun()

            else:
                st.warning("Enter a Trip Name and add at least one stop.")

# ------------------------------------------------------------------
# TAB 2: TRIP TEMPLATES (unchanged)
# ------------------------------------------------------------------
with tab2:
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
# TAB 3: ALL TRIPS (was Spending Dashboard)
# ------------------------------------------------------------------
with tab3:
    st.subheader("Filter & View Trips")
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
        header_cols = st.columns([0.5, 1.5, 1.5, 1.5, 1.2, 1, 1, 1, 1, 0.8, 0.8])
        with header_cols[0]:
            st.write("")
        with header_cols[1]:
            st.write("**Executive**")
        with header_cols[2]:
            st.write("**Company**")
        with header_cols[3]:
            st.write("**Destination**")
        with header_cols[4]:
            st.write("**Budget (Base)**")
        with header_cols[5]:
            st.write("**Total Spent (Base)**")
        with header_cols[6]:
            st.write("**Confirmed (Base)**")
        with header_cols[7]:
            st.write("**Estimated (Base)**")
        with header_cols[8]:
            st.write("**Status**")
        with header_cols[9]:
            st.write("**Open**")
        with header_cols[10]:
            st.write("**Delete**")

        # --- Loop through trips ---
        for trip in summary_data:
            trip_base_currency = trip.get("base_currency", "USD")
            trip_id = trip["trip_id"]

            with st.container():
                cols = st.columns([0.5, 1.5, 1.5, 1.5, 1.2, 1, 1, 1, 1, 0.8, 0.8])

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
                    st.write(f"{trip['budget']:.2f} {trip_base_currency}")
                with cols[5]:
                    st.write(f"{trip['total_spent']:.2f} {trip_base_currency}")
                with cols[6]:
                    st.write(f"{trip['confirmed_spent']:.2f} {trip_base_currency}")
                with cols[7]:
                    st.write(f"{trip['estimated_spent']:.2f} {trip_base_currency}")
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
                    # Full edit modal – using popover with CSS for width
                    with st.popover("📂 Edit", use_container_width=True):
                        trip_id_modal = trip["trip_id"]
                        trip_modal_data = db.get_trip(trip_id_modal)
                        if trip_modal_data:
                            # Determine if locked (approved or final)
                            is_locked = trip_modal_data.get("status") in [
                                "approved",
                                "final",
                            ]

                            if f"modal_stops_{trip_id_modal}" not in st.session_state:
                                st.session_state[f"modal_stops_{trip_id_modal}"] = (
                                    db.get_trip_stops(trip_id_modal)
                                )
                            if f"modal_items_{trip_id_modal}" not in st.session_state:
                                st.session_state[f"modal_items_{trip_id_modal}"] = (
                                    db.get_items_for_trip(trip_id_modal)
                                )

                            st.subheader(
                                f"✈️ Edit Trip: {trip_modal_data.get('purpose', 'Untitled')}"
                            )
                            if is_locked:
                                st.info(
                                    "🔒 This trip is Approved or Final – read‑only view."
                                )

                            # ---- MAIN FORM ----
                            with st.form(key=f"edit_trip_form_{trip_id_modal}"):
                                new_purpose = st.text_input(
                                    "Trip Name",
                                    value=trip_modal_data.get("purpose", ""),
                                    key=f"modal_purpose_{trip_id_modal}",
                                    disabled=is_locked,
                                )

                                col_dep1, col_dep2 = st.columns(2)
                                with col_dep1:
                                    new_dep_city = st.text_input(
                                        "Departure City",
                                        value=trip_modal_data.get("departure_city", ""),
                                        key=f"modal_dep_city_{trip_id_modal}",
                                        disabled=is_locked,
                                    )
                                with col_dep2:
                                    new_dep_region = st.text_input(
                                        "Departure Region",
                                        value=trip_modal_data.get(
                                            "departure_region", ""
                                        ),
                                        key=f"modal_dep_region_{trip_id_modal}",
                                        disabled=is_locked,
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
                                    disabled=is_locked,
                                )

                                st.write("**Budget**")
                                col_bud1, col_bud2 = st.columns(2)
                                with col_bud1:
                                    base_cur = trip_modal_data.get(
                                        "base_currency", "USD"
                                    )
                                    budget_base = trip_modal_data.get("budget", 0.0)
                                    new_budget = st.number_input(
                                        "Budget Amount (in Base Currency)",
                                        min_value=0.0,
                                        step=100.0,
                                        value=float(budget_base),
                                        key=f"modal_budget_{trip_id_modal}",
                                        disabled=is_locked,
                                    )
                                with col_bud2:
                                    st.write(f"Base Currency: {base_cur}")

                                # ---- Currencies (only Base Currency) ----
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
                                new_base_currency = st.selectbox(
                                    "Base Currency",
                                    options=base_currency_options,
                                    index=(
                                        base_currency_options.index(
                                            trip_modal_data.get("base_currency", "USD")
                                        )
                                        if trip_modal_data.get("base_currency")
                                        in base_currency_options
                                        else 0
                                    ),
                                    key=f"modal_base_currency_{trip_id_modal}",
                                    disabled=is_locked,
                                )

                                # ---- Status ----
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
                                    disabled=is_locked,
                                )

                                # ---- Save button ----
                                if not is_locked:
                                    submitted = st.form_submit_button("💾 Save Changes")
                                    if submitted:
                                        db.update_trip_purpose(
                                            trip_id_modal, new_purpose
                                        )
                                        db.update_trip_budget(trip_id_modal, new_budget)
                                        db.update_trip_departure_details(
                                            trip_id_modal,
                                            new_dep_city,
                                            new_dep_region,
                                            new_dep_country,
                                        )
                                        db.update_trip_base_currency(
                                            trip_id_modal, new_base_currency
                                        )
                                        db.update_trip_display_currency(
                                            trip_id_modal, new_base_currency
                                        )
                                        db.update_trip_status(trip_id_modal, new_status)

                                        db.delete_all_trip_stops(trip_id_modal)
                                        for idx, stop in enumerate(
                                            st.session_state[
                                                f"modal_stops_{trip_id_modal}"
                                            ]
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
                                            new_base_currency
                                        ] + base_currency_options  # allow all
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

                            # ---- Stops management (outside form) ----
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
                                    if not is_locked:
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
                                        disabled=is_locked,
                                    )
                                with col_sc2:
                                    new_stop_country = st.selectbox(
                                        "Country",
                                        options=[""] + country_list,
                                        key=f"modal_new_stop_country_{trip_id_modal}",
                                        disabled=is_locked,
                                    )
                                col_sr, col_sn = st.columns(2)
                                with col_sr:
                                    new_stop_region = st.text_input(
                                        "Region",
                                        key=f"modal_new_stop_region_{trip_id_modal}",
                                        disabled=is_locked,
                                    )
                                with col_sn:
                                    new_stop_notes = st.text_input(
                                        "Notes",
                                        key=f"modal_new_stop_notes_{trip_id_modal}",
                                        disabled=is_locked,
                                    )
                                col_ss, col_se = st.columns(2)
                                with col_ss:
                                    new_stop_start = st.date_input(
                                        "Start Date*",
                                        value=datetime.now(),
                                        key=f"modal_new_stop_start_{trip_id_modal}",
                                        disabled=is_locked,
                                    )
                                with col_se:
                                    new_stop_end = st.date_input(
                                        "End Date*",
                                        value=datetime.now(),
                                        key=f"modal_new_stop_end_{trip_id_modal}",
                                        disabled=is_locked,
                                    )
                                if not is_locked:
                                    if st.button(
                                        "➕ Add Stop",
                                        key=f"modal_add_stop_{trip_id_modal}",
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

                            # ---- Items management (outside form) ----
                            st.write("**📋 Itinerary Items**")
                            base_cur_modal = trip_modal_data.get("base_currency", "USD")
                            currency_options_all = [
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
                                    if not is_locked:
                                        if st.button(
                                            "✏️",
                                            key=f"modal_edit_item_{trip_id_modal}_{idx}",
                                        ):
                                            st.session_state[
                                                f"modal_editing_item_{trip_id_modal}_{idx}"
                                            ] = True
                                with col_i4:
                                    if not is_locked:
                                        if st.button(
                                            "🗑️",
                                            key=f"modal_del_item_{trip_id_modal}_{idx}",
                                        ):
                                            st.session_state[
                                                f"modal_items_{trip_id_modal}"
                                            ].pop(idx)
                                            st.rerun()

                                if (
                                    st.session_state.get(
                                        f"modal_editing_item_{trip_id_modal}_{idx}",
                                        False,
                                    )
                                    and not is_locked
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
                                                options=currency_options_all,
                                                index=(
                                                    currency_options_all.index(
                                                        item.get("cost_currency", "USD")
                                                    )
                                                    if item.get("cost_currency", "USD")
                                                    in currency_options_all
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
                                        disabled=is_locked,
                                    )
                                    n_desc = st.text_input(
                                        "Description",
                                        key=f"modal_n_desc_{trip_id_modal}",
                                        disabled=is_locked,
                                    )
                                    n_start = st.datetime_input(
                                        "Start",
                                        value=datetime.now(),
                                        key=f"modal_n_start_{trip_id_modal}",
                                        disabled=is_locked,
                                    )
                                    n_end = st.datetime_input(
                                        "End",
                                        value=datetime.now(),
                                        key=f"modal_n_end_{trip_id_modal}",
                                        disabled=is_locked,
                                    )
                                    n_loc = st.text_input(
                                        "Location",
                                        key=f"modal_n_loc_{trip_id_modal}",
                                        disabled=is_locked,
                                    )
                                    n_cost = st.number_input(
                                        "Cost",
                                        min_value=0.0,
                                        value=0.0,
                                        key=f"modal_n_cost_{trip_id_modal}",
                                        disabled=is_locked,
                                    )
                                    n_currency = st.selectbox(
                                        "Currency",
                                        options=currency_options_all,
                                        key=f"modal_n_currency_{trip_id_modal}",
                                        disabled=is_locked,
                                    )
                                    n_rate = st.number_input(
                                        "Exchange Rate (1 base currency = X this currency)",
                                        min_value=0.0,
                                        step=0.01,
                                        value=1.0,
                                        key=f"modal_n_rate_{trip_id_modal}",
                                        disabled=is_locked,
                                    )
                                    st.caption(
                                        "💡 [Check current rates on XE.com](https://www.xe.com)"
                                    )
                                    n_confirmed = st.checkbox(
                                        "Confirmed",
                                        key=f"modal_n_confirmed_{trip_id_modal}",
                                        disabled=is_locked,
                                    )
                                    n_notes = st.text_area(
                                        "Notes",
                                        key=f"modal_n_notes_{trip_id_modal}",
                                        disabled=is_locked,
                                    )
                                    if not is_locked:
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

                            # ---- Additional actions (Delete, Revert, Save as Template) ----
                            st.divider()
                            col_actions_left, col_actions_mid, col_actions_right = (
                                st.columns(3)
                            )
                            with col_actions_left:
                                # Delete button
                                if not is_locked:
                                    if st.button(
                                        "🗑️ Delete This Trip",
                                        type="primary",
                                        use_container_width=True,
                                        key=f"delete_trip_modal_{trip_id_modal}",
                                    ):
                                        st.session_state[
                                            f"confirm_del_modal_{trip_id_modal}"
                                        ] = True
                            with col_actions_mid:
                                # Revert to Draft (only if status is approved or final)
                                if current_status in ["approved", "final"]:
                                    if st.button(
                                        "↩️ Revert to Draft",
                                        use_container_width=True,
                                        key=f"revert_trip_modal_{trip_id_modal}",
                                    ):
                                        db.update_trip_status(trip_id_modal, "draft")
                                        st.success("Trip reverted to Draft status.")
                                        st.session_state.pop(
                                            f"modal_stops_{trip_id_modal}", None
                                        )
                                        st.session_state.pop(
                                            f"modal_items_{trip_id_modal}", None
                                        )
                                        st.rerun()
                            with col_actions_right:
                                # Save as Template
                                if st.button(
                                    "📋 Save as Template",
                                    use_container_width=True,
                                    key=f"save_template_modal_{trip_id_modal}",
                                ):
                                    st.session_state[
                                        f"show_save_template_modal_{trip_id_modal}"
                                    ] = True

                            # Save as Template confirmation
                            if st.session_state.get(
                                f"show_save_template_modal_{trip_id_modal}", False
                            ):
                                st.info("Save this trip as a reusable template.")
                                template_name_modal = st.text_input(
                                    "Template Name*",
                                    value=f"{trip_modal_data.get('purpose', '')} Template",
                                    key=f"template_name_modal_{trip_id_modal}",
                                )
                                template_desc_modal = st.text_input(
                                    "Description (optional)",
                                    key=f"template_desc_modal_{trip_id_modal}",
                                )
                                col_yes_modal, col_no_modal = st.columns(2)
                                with col_yes_modal:
                                    if st.button(
                                        "💾 Save",
                                        key=f"confirm_save_template_modal_{trip_id_modal}",
                                    ):
                                        if template_name_modal:
                                            new_id = db.save_trip_as_template(
                                                trip_id_modal,
                                                template_name_modal,
                                                template_desc_modal,
                                            )
                                            if new_id:
                                                st.success(
                                                    f"✅ Template '{template_name_modal}' saved!"
                                                )
                                                st.session_state.pop(
                                                    f"show_save_template_modal_{trip_id_modal}",
                                                    None,
                                                )
                                                st.rerun()
                                            else:
                                                st.error("Failed to save template.")
                                        else:
                                            st.warning("Template Name is required.")
                                with col_no_modal:
                                    if st.button(
                                        "Cancel",
                                        key=f"cancel_save_template_modal_{trip_id_modal}",
                                    ):
                                        st.session_state.pop(
                                            f"show_save_template_modal_{trip_id_modal}",
                                            None,
                                        )
                                        st.rerun()

                            # Delete confirmation dialog
                            if st.session_state.get(
                                f"confirm_del_modal_{trip_id_modal}", False
                            ):
                                st.warning("⚠️ Permanently delete this trip?")
                                col_yes, col_no = st.columns(2)
                                with col_yes:
                                    if st.button(
                                        "✅ Yes, Delete",
                                        key=f"confirm_del_modal_yes_{trip_id_modal}",
                                    ):
                                        db.delete_trip(trip_id_modal)
                                        st.session_state.pop(
                                            f"modal_stops_{trip_id_modal}", None
                                        )
                                        st.session_state.pop(
                                            f"modal_items_{trip_id_modal}", None
                                        )
                                        st.session_state.pop(
                                            f"confirm_del_modal_{trip_id_modal}", None
                                        )
                                        st.success("Trip deleted.")
                                        st.rerun()
                                with col_no:
                                    if st.button(
                                        "❌ Cancel",
                                        key=f"confirm_del_modal_no_{trip_id_modal}",
                                    ):
                                        st.session_state.pop(
                                            f"confirm_del_modal_{trip_id_modal}", None
                                        )
                                        st.rerun()

                            # Close button for popover
                            if st.button("Close", key=f"close_modal_{trip_id_modal}"):
                                st.session_state.pop(
                                    f"modal_stops_{trip_id_modal}", None
                                )
                                st.session_state.pop(
                                    f"modal_items_{trip_id_modal}", None
                                )
                                st.rerun()
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
                "Base Currency",
            ]
            rows_with_currency = []
            for trip in summary_data:
                trip_base = trip.get("base_currency", "USD")
                rows_with_currency.append(
                    [
                        trip["executive_name"],
                        trip["company_name"],
                        trip["destination"],
                        f"{trip['budget']:.2f}",
                        f"{trip['total_spent']:.2f}",
                        f"{trip['confirmed_spent']:.2f}",
                        f"{trip['estimated_spent']:.2f}",
                        trip["status"],
                        trip_base,
                    ]
                )
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(headers)
            for row in rows_with_currency:
                writer.writerow(row)
            st.download_button(
                "📊 Export Trips CSV",
                data=output.getvalue().encode("utf-8"),
                file_name=f"trips_summary_{datetime.now().strftime('%Y%m%d')}.csv",
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
                    summary_data, get_currency_symbol("USD"), "USD"
                )
                if excel_stream:
                    st.download_button(
                        "⬇️ Download .xlsx",
                        data=excel_stream,
                        file_name=f"trips_summary_{datetime.now().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="dash_excel_download_tab",
                    )
    else:
        st.info("No trips found matching the filters.")

# ------------------------------------------------------------------
# TAB 4: COMPANIES (Management)
# ------------------------------------------------------------------
with tab4:
    st.header("🏢 Company Management")

    # ---- Add new company form ----
    with st.expander("➕ Add New Company", expanded=False):
        with st.form("add_company_manager_form"):
            new_name = st.text_input("Company Name*", key="mgr_comp_name")
            new_cc = st.text_input("Default Cost Center (optional)", key="mgr_comp_cc")
            new_policy = st.text_area("Policy Notes (optional)", key="mgr_comp_policy")
            if st.form_submit_button("Add Company"):
                if new_name:
                    db.add_company(new_name, new_cc, new_policy)
                    st.success(f"Company '{new_name}' added!")
                    st.rerun()
                else:
                    st.warning("Company Name is required.")

    # ---- List of companies ----
    companies = db.get_all_companies()
    if not companies:
        st.info("No companies yet. Add one using the expander above.")
    else:
        st.write("**Existing Companies**")
        for comp_id, comp_name in companies:
            # Get full details
            comp = db.get_company(comp_id)
            with st.container():
                col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 1, 1])
                with col1:
                    st.write(f"**{comp['name']}**")
                with col2:
                    st.write(comp.get('default_cost_center', '') or '—')
                with col3:
                    st.write(comp.get('policy_notes', '') or '—')
                with col4:
                    if st.button("✏️", key=f"edit_comp_{comp_id}"):
                        st.session_state[f"edit_company_{comp_id}"] = True
                with col5:
                    if st.button("🗑️", key=f"del_comp_{comp_id}"):
                        st.session_state[f"confirm_del_comp_{comp_id}"] = True

                # ---- Edit company popover ----
                if st.session_state.get(f"edit_company_{comp_id}", False):
                    with st.popover("Edit Company", use_container_width=True):
                        with st.form(key=f"edit_comp_form_{comp_id}"):
                            edit_name = st.text_input("Company Name*", value=comp['name'], key=f"edit_comp_name_{comp_id}")
                            edit_cc = st.text_input("Default Cost Center (optional)", value=comp.get('default_cost_center', ''), key=f"edit_comp_cc_{comp_id}")
                            edit_policy = st.text_area("Policy Notes (optional)", value=comp.get('policy_notes', ''), key=f"edit_comp_policy_{comp_id}")
                            if st.form_submit_button("💾 Save Changes"):
                                if edit_name:
                                    db.update_company(comp_id, edit_name, edit_cc, edit_policy)
                                    st.success(f"Company '{edit_name}' updated!")
                                    st.session_state.pop(f"edit_company_{comp_id}", None)
                                    st.rerun()
                                else:
                                    st.warning("Company Name is required.")
                            if st.form_submit_button("❌ Cancel"):
                                st.session_state.pop(f"edit_company_{comp_id}", None)
                                st.rerun()

                # ---- Delete confirmation (inside the container) ----
                if st.session_state.get(f"confirm_del_comp_{comp_id}", False):
                    st.warning(f"⚠️ Permanently delete company '{comp['name']}'?")
                    col_yes, col_no = st.columns(2)
                    with col_yes:
                        if st.button("✅ Yes, Delete", key=f"confirm_del_comp_yes_{comp_id}"):
                            success, msg = db.delete_company(comp_id)
                            if success:
                                st.success(msg)
                                st.session_state.pop(f"confirm_del_comp_{comp_id}", None)
                                st.rerun()
                            else:
                                st.error(msg)
                    with col_no:
                        if st.button("❌ Cancel", key=f"confirm_del_comp_no_{comp_id}"):
                            st.session_state.pop(f"confirm_del_comp_{comp_id}", None)
                            st.rerun()
                st.divider()