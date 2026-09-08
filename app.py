import streamlit as st
import database as db
import doc_generator
import utils
from datetime import datetime, timedelta
import csv
import io
import pytz
import os
import json
import pycountry
from openpyxl import Workbook
from excel_export import (
    export_profile_to_excel,
    export_itinerary_to_excel,
    export_expense_to_excel,
    export_spending_to_excel,
    export_company_profile_to_excel,
)
from currency import get_currency_symbol
import duplicate_detection
import sqlite3
import zipfile

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


def get_company_delegation_options(company_id):
    """Return a dict of delegation member label -> id for a company."""
    members = db.get_delegation_members(company_id, active_only=True)
    return {f"{m['name']} ({m.get('role', '')})".strip(): m["id"] for m in members}


def get_company_contact_options(company_id):
    """Return a dict of contact label -> id for a company."""
    contacts = db.get_contacts(company_id, active_only=True)
    return {f"{c['name']} ({c.get('role', '')})".strip(): c["id"] for c in contacts}


def get_delegation_names(delegation_ids):
    """Return a comma-separated string of delegation member names for display."""
    if not delegation_ids:
        return ""
    conn = sqlite3.connect(db.DB_PATH)
    c = conn.cursor()
    placeholders = ",".join(["?"] * len(delegation_ids))
    c.execute(
        f"SELECT name FROM delegation_members WHERE id IN ({placeholders})",
        delegation_ids,
    )
    names = [row[0] for row in c.fetchall()]
    conn.close()
    return ", ".join(names)


def get_contact_names(contact_ids):
    """Return a comma-separated string of contact names for display."""
    if not contact_ids:
        return ""
    conn = sqlite3.connect(db.DB_PATH)
    c = conn.cursor()
    placeholders = ",".join(["?"] * len(contact_ids))
    c.execute(f"SELECT name FROM contacts WHERE id IN ({placeholders})", contact_ids)
    names = [row[0] for row in c.fetchall()]
    conn.close()
    return ", ".join(names)


# ---- Helper for timezone formatting (Phase 4) ----
def format_item_datetime(item, exec_timezone, display_mode="Home"):
    """Return a formatted datetime string for an item based on display mode."""
    tz_str = item.get("timezone") or exec_timezone
    if display_mode == "Home":
        display_tz = exec_timezone
    else:
        display_tz = tz_str
    return utils.format_datetime_with_timezone(
        item["datetime_start"], tz_str, display_tz
    )


def get_non_local_support_contacts(company_id):
    """Return contacts of a company that are NOT 'Local Support'."""
    contacts = db.get_contacts(company_id, active_only=True)
    return {
        f"{c['name']} ({c.get('role', '')})".strip(): c["id"]
        for c in contacts
        if c.get("type") != "Local Support"
    }


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
                    col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 1, 1])
                    with col1:
                        st.write(f"{p['country']}: {p['passport_number']}")
                    with col2:
                        st.write(f"Exp: {p.get('expiry_date') or ''}")
                    with col3:
                        st.write((p.get("notes") or "")[:30])
                    with col4:
                        if st.button("✏️", key=f"edit_pass_{p['id']}"):
                            st.session_state[f"editing_passport_{p['id']}"] = True
                    with col5:
                        if st.button("🗑️", key=f"del_pass_edit_{p['id']}"):
                            db.delete_passport(p["id"])
                            st.rerun()

                    # ---- Edit Passport Form ----
                    if st.session_state.get(f"editing_passport_{p['id']}", False):
                        with st.expander(
                            f"Edit Passport: {p['country']}", expanded=True
                        ):
                            with st.form(key=f"edit_pass_form_{p['id']}"):
                                edit_country = st.text_input(
                                    "Country",
                                    value=p["country"],
                                    key=f"edit_pass_country_{p['id']}",
                                )
                                edit_pass_num = st.text_input(
                                    "Passport Number",
                                    value=p["passport_number"],
                                    key=f"edit_pass_num_{p['id']}",
                                )
                                edit_expiry = st.date_input(
                                    "Expiry Date",
                                    value=(
                                        datetime.fromisoformat(p["expiry_date"])
                                        if p.get("expiry_date")
                                        else None
                                    ),
                                    key=f"edit_pass_expiry_{p['id']}",
                                )
                                edit_issued = st.date_input(
                                    "Issued Date",
                                    value=(
                                        datetime.fromisoformat(p["issued_date"])
                                        if p.get("issued_date")
                                        else None
                                    ),
                                    key=f"edit_pass_issued_{p['id']}",
                                )
                                edit_notes = st.text_area(
                                    "Notes",
                                    value=p.get("notes", ""),
                                    key=f"edit_pass_notes_{p['id']}",
                                )
                                col_save, col_cancel = st.columns(2)
                                with col_save:
                                    if st.form_submit_button("💾 Save"):
                                        if edit_country and edit_pass_num:
                                            db.update_passport(
                                                p["id"],
                                                edit_country,
                                                edit_pass_num,
                                                expiry_date=(
                                                    edit_expiry.isoformat()
                                                    if edit_expiry
                                                    else None
                                                ),
                                                issued_date=(
                                                    edit_issued.isoformat()
                                                    if edit_issued
                                                    else None
                                                ),
                                                notes=edit_notes,
                                            )
                                            st.session_state.pop(
                                                f"editing_passport_{p['id']}", None
                                            )
                                            st.rerun()
                                        else:
                                            st.warning(
                                                "Country and Passport Number are required."
                                            )
                                with col_cancel:
                                    if st.form_submit_button("❌ Cancel"):
                                        st.session_state.pop(
                                            f"editing_passport_{p['id']}", None
                                        )
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
                    col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 1, 1])
                    with col1:
                        emoji = (
    "✈️" if m["category"] == "airline" else
    "🏨" if m["category"] == "hotel" else
    "🚗" if m["category"] == "car rental" else
    "🛋️" if m["category"] == "lounge" else
    "🚄" if m["category"] == "rail" else
    "⛴️" if m["category"] == "ferry" else
    "🚗" if m["category"] == "ride-share" else
    "💳" if m["category"] == "credit card" else
    "📌"  # fallback
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
                        if st.button("✏️", key=f"edit_mem_{m['id']}"):
                            st.session_state[f"editing_membership_{m['id']}"] = True
                    with col5:
                        if st.button("🗑️", key=f"del_mem_edit_{m['id']}"):
                            db.delete_membership(m["id"])
                            st.rerun()

                    # ---- Edit Membership Form ----
                    if st.session_state.get(f"editing_membership_{m['id']}", False):
                        with st.expander(
                            f"Edit Membership: {m['program_name']}", expanded=True
                        ):
                            with st.form(key=f"edit_mem_form_{m['id']}"):
                                edit_cat = st.selectbox(
                                    "Category",
                                    ["Airline", "Hotel", "Car Rental", "Lounge", "Rail", "Ferry", "Ride-Share", "Credit Card"],
                                    index=["airline", "hotel", "car rental", "lounge", "rail", "ferry", "ride-share", "credit card"].index(m["category"]),
                                    key=f"edit_mem_cat_{m['id']}"
                                )
                                edit_prog = st.text_input(
                                    "Program Name",
                                    value=m["program_name"],
                                    key=f"edit_mem_prog_{m['id']}",
                                )
                                edit_num = st.text_input(
                                    "Membership Number",
                                    value=m["membership_number"],
                                    key=f"edit_mem_num_{m['id']}",
                                )

                                # Extra fields
                                with st.expander("More details (optional)"):
                                    if edit_cat == "Airline":
                                        edit_tier = st.text_input(
                                            "Tier",
                                            value=m.get("tier") or "",
                                            key=f"edit_mem_tier_{m['id']}",
                                        )
                                        edit_alliance = st.text_input(
                                            "Alliance",
                                            value=m.get("alliance") or "",
                                            key=f"edit_mem_alliance_{m['id']}",
                                        )
                                        edit_airport = st.text_input(
                                            "Airport Code",
                                            value=m.get("airport_code") or "",
                                            key=f"edit_mem_airport_{m['id']}",
                                        )
                                        edit_notes = st.text_area(
                                            "Notes",
                                            value=m.get("notes") or "",
                                            key=f"edit_mem_notes_{m['id']}",
                                        )
                                    elif edit_cat == "Hotel":
                                        edit_tier = st.text_input(
                                            "Status/Tier",
                                            value=m.get("tier") or "",
                                            key=f"edit_mem_tier_{m['id']}",
                                        )
                                        edit_notes = st.text_area(
                                            "Notes",
                                            value=m.get("notes") or "",
                                            key=f"edit_mem_notes_{m['id']}",
                                        )
                                        edit_alliance = None
                                        edit_airport = None
                                    else:  # Car
                                        edit_notes = st.text_area(
                                            "Notes",
                                            value=m.get("notes") or "",
                                            key=f"edit_mem_notes_{m['id']}",
                                        )
                                        edit_tier = None
                                        edit_alliance = None
                                        edit_airport = None

                                col_save, col_cancel = st.columns(2)
                                with col_save:
                                    if st.form_submit_button("💾 Save"):
                                        if edit_prog and edit_num:
                                            db.update_membership(
                                                m["id"],
                                                edit_cat.lower(),
                                                edit_prog,
                                                edit_num,
                                                tier=edit_tier,
                                                alliance=edit_alliance,
                                                airport_code=edit_airport,
                                                notes=edit_notes,
                                            )
                                            st.session_state.pop(
                                                f"editing_membership_{m['id']}", None
                                            )
                                            st.rerun()
                                        else:
                                            st.warning(
                                                "Program Name and Membership Number are required."
                                            )
                                with col_cancel:
                                    if st.form_submit_button("❌ Cancel"):
                                        st.session_state.pop(
                                            f"editing_membership_{m['id']}", None
                                        )
                                        st.rerun()
            else:
                st.caption("No memberships added.")

            with st.expander("➕ Add Membership"):
                col_cat, col_name, col_num = st.columns(3)
                with col_cat:
                    new_cat = st.selectbox(
                        "Category",
                        ["Airline", "Hotel", "Car Rental", "Lounge", "Rail", "Ferry", "Ride-Share", "Credit Card"],
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

# --- Export Database ---
with st.sidebar.expander("📤 Export Database", expanded=False):
    st.caption("Export all data as JSON or CSV (ZIP).")
    col_exp_json, col_exp_csv = st.columns(2)
    with col_exp_json:
        if st.button("📄 JSON", use_container_width=True):
            data = db.export_all_data()
            json_str = json.dumps(data, indent=2, default=str)
            st.download_button(
                label="⬇️ Download JSON",
                data=json_str,
                file_name=f"database_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                key="export_json"
            )
    with col_exp_csv:
        if st.button("📊 CSV (ZIP)", use_container_width=True):
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
                tables = [
                    'companies', 'executives', 'contacts', 'delegation_members',
                    'trips', 'itinerary_items', 'trip_stops', 'trip_templates',
                    'categories', 'executive_memberships', 'executive_passports',
                    'item_delegation', 'item_contacts'
                ]
                for table in tables:
                    rows = db.get_all_rows(table)
                    if rows:
                        csv_buffer = io.StringIO()
                        writer = csv.DictWriter(csv_buffer, fieldnames=rows[0].keys())
                        writer.writeheader()
                        writer.writerows(rows)
                        zipf.writestr(f"{table}.csv", csv_buffer.getvalue())
                    else:
                        # Write empty file with just headers? Or skip.
                        # We'll write a file with just headers.
                        # We need to know columns. We can query PRAGMA table_info.
                        conn = sqlite3.connect(db.DB_PATH)
                        c = conn.cursor()
                        c.execute(f"PRAGMA table_info({table})")
                        cols = [row[1] for row in c.fetchall()]
                        conn.close()
                        if cols:
                            csv_buffer = io.StringIO()
                            writer = csv.DictWriter(csv_buffer, fieldnames=cols)
                            writer.writeheader()
                            zipf.writestr(f"{table}.csv", csv_buffer.getvalue())
            zip_buffer.seek(0)
            st.download_button(
                label="⬇️ Download ZIP",
                data=zip_buffer,
                file_name=f"database_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
                mime="application/zip",
                key="export_csv_zip"
            )

# =========================================================
# MAIN AREA: TABS
# =========================================================
tab_names = [
    "✈️ Trip Planner",
    "📋 Trip Templates",
    "📋 All Trips",
    "🏢 Companies",
    "👥 Contacts",
]
default_tab = st.session_state.get("active_tab", "✈️ Trip Planner")
default_index = tab_names.index(default_tab) if default_tab in tab_names else 0
if "active_tab" in st.session_state:
    del st.session_state["active_tab"]

tab1, tab2, tab3, tab4, tab5 = st.tabs(tab_names)

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

    # --- Budget & Currency (same row) ---
    col_budget, col_currency = st.columns(2)
    with col_budget:
        budget = st.number_input(
            "Budget Amount (in Base Currency)",
            min_value=0.0,
            step=100.0,
            value=0.0,
            key="create_trip_budget",
        )
    with col_currency:
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
            "Base Currency",
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

    # ---- Timezone Display for this Trip ----
    tz_display_mode = st.radio(
        "Show times in:",
        options=["Home", "Destination"],
        index=0,
        key="create_tz_display_mode",
        horizontal=True,
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

    # ---- Contacts for this Trip (Local Support) ----
    company_id = profile.get("company_id")
    st.subheader("📋 Contacts for This Trip")
    # Get distinct countries from contacts
    conn = sqlite3.connect(db.DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT DISTINCT country FROM contacts WHERE country IS NOT NULL AND country != '' ORDER BY country"
    )
    countries = [row[0] for row in c.fetchall()]
    conn.close()
    country_options = ["All Countries"] + countries
    selected_country = st.selectbox(
        "Filter contacts by country",
        options=country_options,
        index=0,
        key="create_contact_country_filter",
    )
    filter_country = None if selected_country == "All Countries" else selected_country

    # Get contacts filtered by country (and active only)
    all_contacts = db.get_contacts(active_only=True, country=filter_country)
    if all_contacts:
        contact_options = {}
        for contact in all_contacts:
            comp = (
                db.get_company(contact["company_id"])
                if contact.get("company_id")
                else None
            )
            comp_name = comp["name"] if comp else "No Company"
            label = f"{contact['name']} ({contact.get('role','')}) – {comp_name}"
            contact_options[label] = contact["id"]
        selected_contact_labels = st.multiselect(
            "Select local support contacts to include in the travel pack",
            options=list(contact_options.keys()),
            default=[],
            key="create_trip_contacts",
        )
        selected_contact_ids = [
            contact_options[label] for label in selected_contact_labels
        ]
        st.session_state["create_trip_contact_ids"] = selected_contact_ids
    else:
        st.warning("No contacts found for the selected country.")
        st.session_state["create_trip_contact_ids"] = []

    # ---- Delegation (travelling group) ----
    st.subheader("👥 Delegation")
    if company_id:
        if "create_trip_delegation" not in st.session_state:
            st.session_state["create_trip_delegation"] = []

        if st.session_state["create_trip_delegation"]:
            for idx, member in enumerate(st.session_state["create_trip_delegation"]):
                col1, col2, col3 = st.columns([3, 2, 1])
                with col1:
                    st.write(f"**{member['name']}** ({member.get('role', '')})")
                with col2:
                    st.write(f"{member.get('email', '')} | {member.get('phone', '')}")
                with col3:
                    if st.button("🗑️", key=f"create_del_delegation_{idx}"):
                        st.session_state["create_trip_delegation"].pop(idx)
                        st.rerun()
        else:
            st.caption("No delegation members added yet.")

        with st.expander(
            "➕ Add Delegation Members from Contacts (excluding Local Support)",
            expanded=False,
        ):
            # Use helper that filters out Local Support contacts
            contact_options = get_non_local_support_contacts(company_id)
            if contact_options:
                selected_labels = st.multiselect(
                    "Select contacts to add as delegation members",
                    options=list(contact_options.keys()),
                    key="add_contacts_to_delegation",
                )
                if st.button("Add Selected", key="add_contacts_delegation_btn"):
                    if selected_labels:
                        added_count = 0
                        existing_ids = [
                            m.get("id")
                            for m in st.session_state["create_trip_delegation"]
                            if m.get("id")
                        ]
                        for label in selected_labels:
                            contact_id = contact_options[label]
                            if contact_id in existing_ids:
                                continue
                            contact = db.get_contact(contact_id)
                            if contact:
                                dupes = db.find_duplicate_delegation_members(
                                    company_id, name=contact["name"]
                                )
                                if dupes:
                                    real_id = dupes[0]["id"]
                                else:
                                    real_id = db.add_delegation_member(
                                        company_id=company_id,
                                        name=contact["name"],
                                        email=contact.get("email"),
                                        role=contact.get("role"),
                                        phone=contact.get("phone"),
                                    )
                                st.session_state["create_trip_delegation"].append(
                                    {
                                        "id": real_id,
                                        "name": contact["name"],
                                        "email": contact.get("email"),
                                        "role": contact.get("role"),
                                        "phone": contact.get("phone"),
                                    }
                                )
                                added_count += 1
                        st.success(f"Added {added_count} delegation member(s).")
                        st.rerun()
                    else:
                        st.warning("Please select at least one contact.")
            else:
                st.caption("No non-local-support contacts available for this company.")
    else:
        st.warning("No company selected – cannot add delegation members.")

    # --- Itinerary Items (optional) ---
    if "create_trip_items" not in st.session_state:
        st.session_state["create_trip_items"] = []

    if st.session_state["create_trip_items"]:
        # Get display mode and exec timezone for formatting
        exec_tz = profile.get("timezone", "America/New_York")
        display_mode = st.session_state.get("create_tz_display_mode", "Home")

        for idx, item in enumerate(st.session_state["create_trip_items"]):
            # Format datetime
            dt_display = format_item_datetime(item, exec_tz, display_mode)

            # Use 5 columns to match the widths list (2,2,2,1,1)
            col_i1, col_i2, col_i3, col_i4, col_i5 = st.columns([2, 2, 2, 1, 1])
            with col_i1:
                st.write(f"{item['description']} ({item['item_type']})")
                st.caption(f"🕐 {dt_display}")
            with col_i2:
                st.write(f"{item.get('cost',0):.2f} {item.get('cost_currency','USD')}")
                delegation = item.get("delegation_ids", [])
                if delegation and st.session_state.get("create_trip_delegation"):
                    names = [
                        st.session_state["create_trip_delegation"][i].get("name", "")
                        for i in delegation
                        if i < len(st.session_state["create_trip_delegation"])
                    ]
                    if names:
                        st.caption(f"👥 {', '.join(names)}")
                contacts = item.get("contact_ids", [])
                if contacts and company_id:
                    contact_names = get_contact_names(contacts)
                    if contact_names:
                        st.caption(f"📞 {contact_names}")
            with col_i3:
                if st.button("✏️", key=f"create_edit_item_{idx}"):
                    st.session_state[f"create_editing_item_{idx}"] = True
            with col_i4:
                if st.button("🗑️", key=f"create_del_item_{idx}"):
                    st.session_state["create_trip_items"].pop(idx)
                    st.rerun()
            # col_i5 is unused; you can leave it or add future elements

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
                        # Currency dropdown
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
                        # ---- Timezone dropdown (Phase 4) ----
                        tz_display_names, tz_map = get_timezone_dropdown_options()
                        current_tz = item.get("timezone") or profile.get(
                            "timezone", "America/New_York"
                        )
                        current_tz_display = next(
                            (n for n in tz_display_names if current_tz in n),
                            tz_display_names[0],
                        )
                        e_timezone = st.selectbox(
                            "Time Zone",
                            options=tz_display_names,
                            index=tz_display_names.index(current_tz_display),
                            key=f"create_e_timezone_{idx}",
                        )
                        e_timezone_value = tz_map[e_timezone]

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
                        # Delegation assignment
                        if company_id and st.session_state.get(
                            "create_trip_delegation"
                        ):
                            delegation_options = {
                                f"{m['name']} ({m.get('role', '')})": idx
                                for idx, m in enumerate(
                                    st.session_state["create_trip_delegation"]
                                )
                            }
                            current_delegation = item.get("delegation_ids", [])
                            current_labels = [
                                label
                                for label, i in delegation_options.items()
                                if i in current_delegation
                            ]
                            selected_parts = st.multiselect(
                                "Assign Delegation Members",
                                options=list(delegation_options.keys()),
                                default=current_labels,
                                key=f"create_e_delegation_{idx}",
                            )
                            e_delegation_ids = [
                                delegation_options[label] for label in selected_parts
                            ]
                        else:
                            e_delegation_ids = []

                        # ---- Contact assignment (per item) ----
                        if company_id:
                            contact_options = get_company_contact_options(company_id)
                            current_contact_ids = item.get("contact_ids", [])
                            current_labels = [
                                label
                                for label, cid in contact_options.items()
                                if cid in current_contact_ids
                            ]
                            selected_contacts = st.multiselect(
                                "Assign Local Support Contacts",
                                options=list(contact_options.keys()),
                                default=current_labels,
                                key=f"create_e_contacts_{idx}",
                            )
                            e_contact_ids = [
                                contact_options[label] for label in selected_contacts
                            ]
                        else:
                            e_contact_ids = []

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
                                "delegation_ids": e_delegation_ids,
                                "contact_ids": e_contact_ids,
                                "timezone": e_timezone_value,
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
            # ---- Timezone dropdown (Phase 4) ----
            tz_display_names, tz_map = get_timezone_dropdown_options()
            if profile and profile.get("timezone"):
                default_tz_display = next(
                    (n for n in tz_display_names if profile["timezone"] in n),
                    tz_display_names[0],
                )
            else:
                default_tz_display = tz_display_names[0]
            n_timezone = st.selectbox(
                "Time Zone (for this event)",
                options=tz_display_names,
                index=tz_display_names.index(default_tz_display),
                key="create_n_timezone",
            )
            n_timezone_value = tz_map[n_timezone]

            st.caption("💡 [Check current rates on XE.com](https://www.xe.com)")
            n_confirmed = st.checkbox("Confirmed", key="create_n_confirmed")
            n_notes = st.text_area("Notes", key="create_n_notes")

            # Delegation assignment
            if company_id and st.session_state.get("create_trip_delegation"):
                delegation_options = {
                    f"{m['name']} ({m.get('role', '')})": idx
                    for idx, m in enumerate(st.session_state["create_trip_delegation"])
                }
                selected_delegation = st.multiselect(
                    "Assign Delegation Members",
                    options=list(delegation_options.keys()),
                    key="create_item_delegation",
                )
                selected_delegation_ids = [
                    delegation_options[label] for label in selected_delegation
                ]
            else:
                selected_delegation_ids = []

            # ---- Contact assignment (per item) ----
            if company_id:
                contact_options = get_company_contact_options(company_id)
                selected_contacts = st.multiselect(
                    "Assign Local Support Contacts",
                    options=list(contact_options.keys()),
                    key="create_item_contacts",
                )
                selected_contact_ids = [
                    contact_options[label] for label in selected_contacts
                ]
            else:
                selected_contact_ids = []

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
                            "delegation_ids": selected_delegation_ids,
                            "contact_ids": selected_contact_ids,
                            "timezone": n_timezone_value,
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
            st.session_state["create_trip_delegation"] = []
            st.session_state["create_trip_contact_ids"] = []
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

                # ---- Contacts and Delegation ----
                selected_contact_ids = st.session_state.get(
                    "create_trip_contact_ids", []
                )

                # Map delegation indices to real IDs
                delegation_id_map = {}
                for idx, member in enumerate(
                    st.session_state.get("create_trip_delegation", [])
                ):
                    if member.get("id"):
                        real_id = member["id"]
                    else:
                        dupes = db.find_duplicate_delegation_members(
                            company_id, name=member["name"]
                        )
                        if dupes:
                            real_id = dupes[0]["id"]
                        else:
                            real_id = db.add_delegation_member(
                                company_id=company_id,
                                name=member["name"],
                                email=member.get("email"),
                                role=member.get("role"),
                                phone=member.get("phone"),
                            )
                    delegation_id_map[idx] = real_id

                # Create trip
                trip_id = db.create_or_get_trip(
                    trip_exec_id,
                    dest_summary,
                    overall_start,
                    overall_end,
                    trip_purpose,
                    trip_base_currency,
                    trip_base_currency,
                    trip_status,
                    trip_contacts=selected_contact_ids,
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

                # Add items with delegation and contact assignments
                for item in st.session_state["create_trip_items"]:
                    item_id = db.add_itinerary_item(
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
                        timezone=item.get("timezone"),
                    )
                    if item.get("delegation_ids"):
                        real_delegation_ids = [
                            delegation_id_map[idx]
                            for idx in item["delegation_ids"]
                            if idx in delegation_id_map
                        ]
                        if real_delegation_ids:
                            db.set_item_delegation_members(item_id, real_delegation_ids)
                    if item.get("contact_ids"):
                        # contact_ids are already real IDs (from company contacts)
                        if item["contact_ids"]:
                            db.set_item_contacts(item_id, item["contact_ids"])

                # Clear the form and session state
                st.session_state["create_trip_stops"] = []
                st.session_state["create_trip_items"] = []
                st.session_state["create_trip_delegation"] = []
                st.session_state["create_trip_contact_ids"] = []

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

                # ---- Save as Template ----
                st.session_state["last_created_trip_id"] = trip_id
                st.session_state["last_created_trip_name"] = trip_purpose

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

    # ---- Search bar (Phase 8) ----
    search_trip = st.text_input(
        "🔍 Search Trips",
        placeholder="Destination, purpose, or executive name...",
        key="dash_search",
    )

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

    # ---- Apply search filter ----
    if search_trip:
        search_lower = search_trip.lower()
        summary_data = [
            trip
            for trip in summary_data
            if search_lower in trip.get("destination", "").lower()
            or search_lower in trip.get("purpose", "").lower()
            or search_lower in trip.get("executive_name", "").lower()
        ]

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

                                # ---- Timezone Display for this Trip ----
                                st.write("**Timezone Display**")
                                if (
                                    f"modal_tz_display_{trip_id_modal}"
                                    not in st.session_state
                                ):
                                    st.session_state[
                                        f"modal_tz_display_{trip_id_modal}"
                                    ] = "Home"
                                modal_tz_display = st.radio(
                                    "Show times in:",
                                    options=["Home", "Destination"],
                                    index=(
                                        0
                                        if st.session_state[
                                            f"modal_tz_display_{trip_id_modal}"
                                        ]
                                        == "Home"
                                        else 1
                                    ),
                                    key=f"modal_tz_display_radio_{trip_id_modal}",
                                )
                                # No manual assignment – widget updates session state automatically

                                # ---- Contacts for this trip ----
                                st.write("**Contacts**")
                                exec_profile_modal = db.get_executive_profile(
                                    trip_modal_data["exec_id"]
                                )
                                company_id_modal = (
                                    exec_profile_modal.get("company_id")
                                    if exec_profile_modal
                                    else None
                                )
                                if company_id_modal:
                                    contact_options_modal = get_non_local_support_contacts(company_id_modal)
                                    existing_contact_ids = (
                                        json.loads(
                                            trip_modal_data.get("trip_contacts", "[]")
                                        )
                                        if trip_modal_data.get("trip_contacts")
                                        else []
                                    )
                                    existing_labels = [
                                        label
                                        for label, cid in contact_options_modal.items()
                                        if cid in existing_contact_ids
                                    ]
                                    selected_contacts_modal = st.multiselect(
                                        "Select local support contacts for this trip",
                                        options=list(contact_options_modal.keys()),
                                        default=existing_labels,
                                        key=f"modal_contacts_{trip_id_modal}",
                                        disabled=is_locked,
                                    )
                                    selected_contact_ids_modal = [
                                        contact_options_modal[label]
                                        for label in selected_contacts_modal
                                    ]
                                else:
                                    selected_contact_ids_modal = []

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
                                        # Save contacts
                                        db.update_trip_contacts(
                                            trip_id_modal, selected_contact_ids_modal
                                        )

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

                                        conn = sqlite3.connect(db.DB_PATH)
                                        c = conn.cursor()
                                        c.execute(
                                            "DELETE FROM itinerary_items WHERE trip_id = ?",
                                            (trip_id_modal,),
                                        )
                                        conn.commit()
                                        conn.close()

                                        # Re-add items from session state
                                        for item in st.session_state[
                                            f"modal_items_{trip_id_modal}"
                                        ]:
                                            item_id = db.add_itinerary_item(
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
                                                timezone=item.get("timezone"),
                                            )
                                            # Restore delegation and contacts
                                            if item.get("delegation_ids"):
                                                if item["delegation_ids"]:
                                                    db.set_item_delegation_members(
                                                        item_id, item["delegation_ids"]
                                                    )
                                            if item.get("contact_ids"):
                                                if item["contact_ids"]:
                                                    db.set_item_contacts(
                                                        item_id, item["contact_ids"]
                                                    )

                                        st.success("✅ Trip updated successfully!")
                                        st.session_state.pop(
                                            f"modal_stops_{trip_id_modal}", None
                                        )
                                        st.session_state.pop(
                                            f"modal_items_{trip_id_modal}", None
                                        )
                                        st.rerun()

                            # ---- Stops management ----
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

                            # ---- Items management ----
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
                            # Get exec timezone for the modal
                            exec_tz_modal = (
                                exec_profile_modal.get("timezone", "America/New_York")
                                if exec_profile_modal
                                else "America/New_York"
                            )
                            display_mode_modal = st.session_state.get(
                                f"modal_tz_display_{trip_id_modal}", "Home"
                            )

                            for idx, item in enumerate(items):
                                # Format datetime
                                dt_display = format_item_datetime(
                                    item, exec_tz_modal, display_mode_modal
                                )

                                col_i1, col_i2, col_i3, col_i4 = st.columns(
                                    [3, 2, 1, 1]
                                )
                                with col_i1:
                                    st.write(
                                        f"{item['description']} ({item['item_type']})"
                                    )
                                    st.caption(f"🕐 {dt_display}")
                                    # Show delegation if available
                                    if item.get("delegation_ids"):
                                        d_names = get_delegation_names(
                                            item["delegation_ids"]
                                        )
                                        if d_names:
                                            st.caption(f"👥 {d_names}")
                                    # Show contacts if available
                                    if item.get("contact_ids"):
                                        c_names = get_contact_names(item["contact_ids"])
                                        if c_names:
                                            st.caption(f"📞 {c_names}")
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
                                            # ---- Timezone dropdown (Phase 4) ----
                                            tz_display_names, tz_map = (
                                                get_timezone_dropdown_options()
                                            )
                                            current_tz_modal = (
                                                item.get("timezone") or exec_tz_modal
                                            )
                                            current_tz_display_modal = next(
                                                (
                                                    n
                                                    for n in tz_display_names
                                                    if current_tz_modal in n
                                                ),
                                                tz_display_names[0],
                                            )
                                            e_timezone_modal = st.selectbox(
                                                "Time Zone",
                                                options=tz_display_names,
                                                index=tz_display_names.index(
                                                    current_tz_display_modal
                                                ),
                                                key=f"modal_e_timezone_{trip_id_modal}_{idx}",
                                            )
                                            e_timezone_value_modal = tz_map[
                                                e_timezone_modal
                                            ]

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
                                            # Delegation assignment
                                            if company_id_modal:
                                                delegation_options_modal = (
                                                    get_company_delegation_options(
                                                        company_id_modal
                                                    )
                                                )
                                                current_delegation_ids = item.get(
                                                    "delegation_ids", []
                                                )
                                                current_labels = [
                                                    label
                                                    for label, did in delegation_options_modal.items()
                                                    if did in current_delegation_ids
                                                ]
                                                selected_delegation_modal = st.multiselect(
                                                    "Assign Delegation Members",
                                                    options=list(
                                                        delegation_options_modal.keys()
                                                    ),
                                                    default=current_labels,
                                                    key=f"modal_item_delegation_{trip_id_modal}_{idx}",
                                                )
                                                selected_delegation_ids_modal = [
                                                    delegation_options_modal[label]
                                                    for label in selected_delegation_modal
                                                ]
                                            else:
                                                selected_delegation_ids_modal = []

                                            # ---- Contact assignment (per item) ----
                                            if company_id_modal:
                                                contact_options_modal = (
                                                    get_company_contact_options(
                                                        company_id_modal
                                                    )
                                                )
                                                current_contact_ids = item.get(
                                                    "contact_ids", []
                                                )
                                                current_labels = [
                                                    label
                                                    for label, cid in contact_options_modal.items()
                                                    if cid in current_contact_ids
                                                ]
                                                selected_contacts_modal = st.multiselect(
                                                    "Assign Local Support Contacts",
                                                    options=list(
                                                        contact_options_modal.keys()
                                                    ),
                                                    default=current_labels,
                                                    key=f"modal_item_contacts_{trip_id_modal}_{idx}",
                                                )
                                                selected_contact_ids_modal = [
                                                    contact_options_modal[label]
                                                    for label in selected_contacts_modal
                                                ]
                                            else:
                                                selected_contact_ids_modal = []

                                            if st.form_submit_button("💾 Update Item"):
                                                # Update the item in session state
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
                                                    "delegation_ids": selected_delegation_ids_modal,
                                                    "contact_ids": selected_contact_ids_modal,
                                                    "timezone": e_timezone_value_modal,
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
                                    # ---- Timezone dropdown (Phase 4) ----
                                    tz_display_names, tz_map = (
                                        get_timezone_dropdown_options()
                                    )
                                    if exec_profile_modal and exec_profile_modal.get(
                                        "timezone"
                                    ):
                                        default_tz_display_modal = next(
                                            (
                                                n
                                                for n in tz_display_names
                                                if exec_profile_modal["timezone"] in n
                                            ),
                                            tz_display_names[0],
                                        )
                                    else:
                                        default_tz_display_modal = tz_display_names[0]
                                    n_timezone_modal = st.selectbox(
                                        "Time Zone (for this event)",
                                        options=tz_display_names,
                                        index=tz_display_names.index(
                                            default_tz_display_modal
                                        ),
                                        key=f"modal_n_timezone_{trip_id_modal}",
                                        disabled=is_locked,
                                    )
                                    n_timezone_value_modal = tz_map[n_timezone_modal]

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
                                    # Delegation assignment
                                    if not is_locked and company_id_modal:
                                        delegation_options_modal = (
                                            get_company_delegation_options(
                                                company_id_modal
                                            )
                                        )
                                        selected_delegation_modal_new = st.multiselect(
                                            "Assign Delegation Members",
                                            options=list(
                                                delegation_options_modal.keys()
                                            ),
                                            key=f"modal_new_item_delegation_{trip_id_modal}",
                                        )
                                        selected_delegation_ids_modal_new = [
                                            delegation_options_modal[label]
                                            for label in selected_delegation_modal_new
                                        ]
                                    else:
                                        selected_delegation_ids_modal_new = []

                                    # ---- Contact assignment (per item) ----
                                    if not is_locked and company_id_modal:
                                        contact_options_modal = (
                                            get_company_contact_options(
                                                company_id_modal
                                            )
                                        )
                                        selected_contacts_modal_new = st.multiselect(
                                            "Assign Local Support Contacts",
                                            options=list(contact_options_modal.keys()),
                                            key=f"modal_new_item_contacts_{trip_id_modal}",
                                        )
                                        selected_contact_ids_modal_new = [
                                            contact_options_modal[label]
                                            for label in selected_contacts_modal_new
                                        ]
                                    else:
                                        selected_contact_ids_modal_new = []

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
                                                        "delegation_ids": selected_delegation_ids_modal_new,
                                                        "contact_ids": selected_contact_ids_modal_new,
                                                        "timezone": n_timezone_value_modal,
                                                    }
                                                )
                                                st.rerun()
                                            else:
                                                st.warning(
                                                    "Description and Start Time are required."
                                                )

                            # ---- Delegation management for edit modal ----
                            st.write("**👥 Delegation**")
                            if company_id_modal:
                                all_members = db.get_delegation_members(
                                    company_id_modal, active_only=True
                                )
                                if all_members:
                                    for member in all_members:
                                        col1, col2, col3 = st.columns([3, 2, 1])
                                        with col1:
                                            st.write(
                                                f"**{member['name']}** ({member.get('role', '')})"
                                            )
                                        with col2:
                                            st.write(
                                                f"{member.get('email', '')} | {member.get('phone', '')}"
                                            )
                                        with col3:
                                            st.write("")
                                else:
                                    st.caption(
                                        "No delegation members for this company."
                                    )
                                with st.expander("➕ Add Delegation Member"):
                                    with st.form(
                                        key=f"add_delegation_modal_{trip_id_modal}"
                                    ):
                                        d_name = st.text_input(
                                            "Name*",
                                            key=f"modal_delegation_name_{trip_id_modal}",
                                        )
                                        d_email = st.text_input(
                                            "Email",
                                            key=f"modal_delegation_email_{trip_id_modal}",
                                        )
                                        d_role = st.text_input(
                                            "Role",
                                            key=f"modal_delegation_role_{trip_id_modal}",
                                        )
                                        d_phone = st.text_input(
                                            "Phone",
                                            key=f"modal_delegation_phone_{trip_id_modal}",
                                        )
                                        if st.form_submit_button(
                                            "Add Delegation Member"
                                        ):
                                            if d_name:
                                                dupes = db.find_duplicate_delegation_members(
                                                    company_id_modal, name=d_name
                                                )
                                                if not dupes:
                                                    db.add_delegation_member(
                                                        company_id=company_id_modal,
                                                        name=d_name,
                                                        email=d_email,
                                                        role=d_role,
                                                        phone=d_phone,
                                                    )
                                                    st.success(
                                                        "Delegation member added!"
                                                    )
                                                    st.rerun()
                                                else:
                                                    st.warning(
                                                        "A member with that name already exists."
                                                    )
                                            else:
                                                st.warning("Name is required.")
                            else:
                                st.warning("No company associated with this trip.")

                            # ---- Additional actions ----
                            st.divider()
                            (
                                col_actions_left,
                                col_actions_mid,
                                col_actions_right,
                                col_actions_travel,
                            ) = st.columns(4)
                            with col_actions_left:
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
                                if st.button(
                                    "📋 Save as Template",
                                    use_container_width=True,
                                    key=f"save_template_modal_{trip_id_modal}",
                                ):
                                    st.session_state[
                                        f"show_save_template_modal_{trip_id_modal}"
                                    ] = True

                            with col_actions_travel:
                                if st.button(
                                    "📦 Travel Pack",
                                    use_container_width=True,
                                    key=f"travel_pack_modal_{trip_id_modal}",
                                ):
                                    st.session_state[
                                        f"show_travel_pack_modal_{trip_id_modal}"
                                    ] = True

                            # ---- Save as Template confirmation ----
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

                                                        # ---- Travel Pack generation ----
                            if st.session_state.get(f"show_travel_pack_modal_{trip_id_modal}", False):
                                st.info("Generate a self-contained Travel Pack in your preferred format.")
                                html_content = doc_generator.generate_travel_pack_html(
                                    trip_id_modal, exec_tz_modal, display_mode_modal
                                )
                                if html_content:
                                    col_html, col_pdf, col_word = st.columns(3)
                                    with col_html:
                                        st.download_button(
                                            label="🌐 HTML",
                                            data=html_content,
                                            file_name=f"TravelPack_{trip_modal_data.get('purpose', 'trip')}.html",
                                            mime="text/html",
                                            key=f"download_travel_pack_html_{trip_id_modal}"
                                        )
                                    with col_pdf:
                                        pdf_stream = doc_generator.generate_travel_pack_pdf(
                                            trip_id_modal, exec_tz_modal, display_mode_modal
                                        )
                                        if pdf_stream:
                                            st.download_button(
                                                label="📄 PDF",
                                                data=pdf_stream,
                                                file_name=f"TravelPack_{trip_modal_data.get('purpose', 'trip')}.pdf",
                                                mime="application/pdf",
                                                key=f"download_travel_pack_pdf_{trip_id_modal}"
                                            )
                                    with col_word:
                                        docx_stream = doc_generator.generate_travel_pack_docx(
                                            trip_id_modal, exec_tz_modal, display_mode_modal
                                        )
                                        if docx_stream:
                                            st.download_button(
                                                label="📄 Word",
                                                data=docx_stream,
                                                file_name=f"TravelPack_{trip_modal_data.get('purpose', 'trip')}.docx",
                                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml",
                                                key=f"download_travel_pack_docx_{trip_id_modal}"
                                            )
                                    if st.button("Close", key=f"close_travel_pack_{trip_id_modal}"):
                                        st.session_state.pop(f"show_travel_pack_modal_{trip_id_modal}", None)
                                        st.rerun()
                                else:
                                    st.error("Failed to generate travel pack.")

                                    
                            # ---- Delete confirmation ----
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
                excel_stream = export_spending_to_excel(summary_data, "USD")
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
    # ---- Search companies (Phase 8) ----
    search_company = st.text_input(
        "🔍 Search Companies", placeholder="Company name...", key="company_search"
    )

    companies = db.get_all_companies()
    if search_company:
        search_lower = search_company.lower()
        companies = [
            (id, name) for id, name in companies if search_lower in name.lower()
        ]

    if not companies:
        st.info("No companies found matching your search.")
    else:
        st.write(f"**{len(companies)} company(ies) found**")
        for comp_id, comp_name in companies:
            comp = db.get_company(comp_id)
            with st.container():
                # ---- Company header row ----
                col1, col2, col3, col4, col5, col6 = st.columns(
                    [2, 1.5, 2, 0.8, 0.8, 1]
                )
                with col1:
                    st.write(f"**{comp['name']}**")
                with col2:
                    st.write(comp.get("default_cost_center", "") or "—")
                with col3:
                    st.write(comp.get("policy_notes", "") or "—")
                with col4:
                    if st.button("✏️", key=f"edit_comp_{comp_id}"):
                        st.session_state[f"edit_company_{comp_id}"] = True
                with col5:
                    if st.button("🗑️", key=f"del_comp_{comp_id}"):
                        st.session_state[f"confirm_del_comp_{comp_id}"] = True
                with col6:
                    if st.button("📄", key=f"export_comp_{comp_id}"):
                        st.session_state[f"export_company_{comp_id}"] = True

                # ---- Edit company popover ----
                if st.session_state.get(f"edit_company_{comp_id}", False):
                    with st.popover("Edit Company", use_container_width=True):
                        with st.form(key=f"edit_comp_form_{comp_id}"):
                            edit_name = st.text_input(
                                "Company Name*",
                                value=comp["name"],
                                key=f"edit_comp_name_{comp_id}",
                            )
                            edit_cc = st.text_input(
                                "Default Cost Center (optional)",
                                value=comp.get("default_cost_center", ""),
                                key=f"edit_comp_cc_{comp_id}",
                            )
                            edit_policy = st.text_area(
                                "Policy Notes (optional)",
                                value=comp.get("policy_notes", ""),
                                key=f"edit_comp_policy_{comp_id}",
                            )
                            if st.form_submit_button("💾 Save Changes"):
                                if edit_name:
                                    db.update_company(
                                        comp_id, edit_name, edit_cc, edit_policy
                                    )
                                    st.success(f"Company '{edit_name}' updated!")
                                    st.session_state.pop(
                                        f"edit_company_{comp_id}", None
                                    )
                                    st.rerun()
                                else:
                                    st.warning("Company Name is required.")
                            if st.form_submit_button("❌ Cancel"):
                                st.session_state.pop(f"edit_company_{comp_id}", None)
                                st.rerun()

                # ---- Delete confirmation ----
                if st.session_state.get(f"confirm_del_comp_{comp_id}", False):
                    st.warning(f"⚠️ Permanently delete company '{comp['name']}'?")
                    col_yes, col_no = st.columns(2)
                    with col_yes:
                        if st.button(
                            "✅ Yes, Delete", key=f"confirm_del_comp_yes_{comp_id}"
                        ):
                            success, msg = db.delete_company(comp_id)
                            if success:
                                st.success(msg)
                                st.session_state.pop(
                                    f"confirm_del_comp_{comp_id}", None
                                )
                                st.rerun()
                            else:
                                st.error(msg)
                    with col_no:
                        if st.button("❌ Cancel", key=f"confirm_del_comp_no_{comp_id}"):
                            st.session_state.pop(f"confirm_del_comp_{comp_id}", None)
                            st.rerun()

                # ---- Export company profile popover ----
                if st.session_state.get(f"export_company_{comp_id}", False):
                    with st.popover("Export Company Profile", use_container_width=True):
                        st.write(f"Export: **{comp['name']}**")
                        col_html, col_word, col_excel = st.columns(3)
                        with col_html:
                            if st.button("🌐 HTML", key=f"export_html_{comp_id}"):
                                html = doc_generator.generate_company_profile_html(
                                    comp_id
                                )
                                if html:
                                    st.download_button(
                                        label="⬇️ Download HTML",
                                        data=html,
                                        file_name=f"{comp['name']}_profile.html",
                                        mime="text/html",
                                        key=f"download_html_{comp_id}",
                                    )
                                else:
                                    st.error("Failed to generate HTML.")
                        with col_word:
                            if st.button("📄 Word", key=f"export_word_{comp_id}"):
                                docx = doc_generator.generate_company_profile_docx(
                                    comp_id
                                )
                                if docx:
                                    st.download_button(
                                        label="⬇️ Download Word",
                                        data=docx,
                                        file_name=f"{comp['name']}_profile.docx",
                                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml",
                                        key=f"download_word_{comp_id}",
                                    )
                                else:
                                    st.error("Failed to generate Word.")
                        with col_excel:
                            if st.button("📊 Excel", key=f"export_excel_{comp_id}"):
                                excel = export_company_profile_to_excel(comp_id)
                                if excel:
                                    st.download_button(
                                        label="⬇️ Download Excel",
                                        data=excel,
                                        file_name=f"{comp['name']}_profile.xlsx",
                                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                        key=f"download_excel_{comp_id}",
                                    )
                                else:
                                    st.error("Failed to generate Excel.")
                        if st.button("Close", key=f"close_export_comp_{comp_id}"):
                            st.session_state.pop(f"export_company_{comp_id}", None)
                            st.rerun()

                # ---- Phase 7: Delegation Management for this company ----
                with st.expander(
                    f"👥 Delegation ({len(db.get_delegation_members(comp_id, active_only=True))})",
                    expanded=False,
                ):
                    # ---- Add new delegation member ----
                    with st.form(key=f"add_delegation_comp_{comp_id}"):
                        col_name, col_email, col_role, col_phone = st.columns(4)
                        with col_name:
                            d_name = st.text_input(
                                "Name*", key=f"add_delegation_name_{comp_id}"
                            )
                        with col_email:
                            d_email = st.text_input(
                                "Email", key=f"add_delegation_email_{comp_id}"
                            )
                        with col_role:
                            d_role = st.text_input(
                                "Role", key=f"add_delegation_role_{comp_id}"
                            )
                        with col_phone:
                            d_phone = st.text_input(
                                "Phone", key=f"add_delegation_phone_{comp_id}"
                            )
                        if st.form_submit_button("➕ Add Delegation Member"):
                            if d_name:
                                # Check duplicate
                                dupes = db.find_duplicate_delegation_members(
                                    comp_id, name=d_name
                                )
                                if not dupes:
                                    db.add_delegation_member(
                                        comp_id, d_name, d_email, d_role, d_phone
                                    )
                                    st.success(f"Delegation member '{d_name}' added!")
                                    st.rerun()
                                else:
                                    st.warning(
                                        "A member with that name already exists."
                                    )
                            else:
                                st.warning("Name is required.")

                    # ---- CSV Import ----
                    st.write("**📤 CSV Import / Export**")
                    col_imp, col_exp = st.columns(2)
                    with col_imp:
                        uploaded_file = st.file_uploader(
                            "Import CSV",
                            type=["csv"],
                            key=f"import_delegation_{comp_id}",
                            help="Columns: Name, Email, Role, Phone",
                        )
                        if uploaded_file is not None:
                            try:
                                content = (
                                    uploaded_file.getvalue()
                                    .decode("utf-8")
                                    .splitlines()
                                )
                                reader = csv.DictReader(content)
                                expected = ["Name", "Email", "Role", "Phone"]
                                if all(h in reader.fieldnames for h in expected):
                                    if st.button(
                                        f"Start Import",
                                        key=f"start_import_delegation_{comp_id}",
                                    ):
                                        added = 0
                                        skipped = 0
                                        for row in reader:
                                            name = row.get("Name", "").strip()
                                            if not name:
                                                continue
                                            # Check duplicate
                                            dupes = (
                                                db.find_duplicate_delegation_members(
                                                    comp_id, name=name
                                                )
                                            )
                                            if dupes and not st.checkbox(
                                                f"Duplicate '{name}' – add anyway?",
                                                key=f"force_import_delegation_{name}_{comp_id}",
                                            ):
                                                skipped += 1
                                                continue
                                            db.add_delegation_member(
                                                company_id=comp_id,
                                                name=name,
                                                email=row.get("Email", "").strip()
                                                or None,
                                                role=row.get("Role", "").strip()
                                                or None,
                                                phone=row.get("Phone", "").strip()
                                                or None,
                                            )
                                            added += 1
                                        st.success(
                                            f"✅ Imported {added} delegation members. Skipped {skipped} duplicates."
                                        )
                                        st.rerun()
                                else:
                                    st.error(
                                        f"CSV must have columns: {', '.join(expected)}"
                                    )
                            except Exception as e:
                                st.error(f"Import failed: {e}")

                    with col_exp:
                        # Export CSV button
                        if st.button(
                            "📥 Export CSV", key=f"export_delegation_{comp_id}"
                        ):
                            members = db.get_delegation_members(
                                comp_id, active_only=True
                            )
                            output = io.StringIO()
                            writer = csv.writer(output)
                            writer.writerow(["Name", "Email", "Role", "Phone"])
                            for m in members:
                                writer.writerow(
                                    [
                                        m["name"],
                                        m.get("email", ""),
                                        m.get("role", ""),
                                        m.get("phone", ""),
                                    ]
                                )
                            st.download_button(
                                label="⬇️ Download CSV",
                                data=output.getvalue().encode("utf-8"),
                                file_name=f"delegation_{comp['name']}_{datetime.now().strftime('%Y%m%d')}.csv",
                                mime="text/csv",
                                key=f"download_delegation_{comp_id}",
                            )

                    # ---- List existing delegation members ----
                    members = db.get_delegation_members(comp_id, active_only=True)
                    if not members:
                        st.caption("No delegation members yet.")
                    else:
                        st.write(f"**{len(members)} active members**")
                        for m in members:
                            col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 1, 1])
                            with col1:
                                st.write(f"**{m['name']}**")
                            with col2:
                                st.write(m.get("email", ""))
                            with col3:
                                st.write(f"{m.get('role', '')} | {m.get('phone', '')}")
                            with col4:
                                if st.button(
                                    "✏️", key=f"edit_delegation_{m['id']}_{comp_id}"
                                ):
                                    st.session_state[
                                        f"editing_delegation_{m['id']}"
                                    ] = True
                            with col5:
                                if st.button(
                                    "🗑️", key=f"del_delegation_{m['id']}_{comp_id}"
                                ):
                                    st.session_state[f"delete_delegation_{m['id']}"] = (
                                        True
                                    )

                            # ---- Edit delegation member popover ----
                            if st.session_state.get(
                                f"editing_delegation_{m['id']}", False
                            ):
                                with st.popover(
                                    f"Edit {m['name']}", use_container_width=True
                                ):
                                    with st.form(key=f"edit_delegation_form_{m['id']}"):
                                        e_name = st.text_input(
                                            "Name*",
                                            value=m["name"],
                                            key=f"edit_delegation_name_{m['id']}",
                                        )
                                        e_email = st.text_input(
                                            "Email",
                                            value=m.get("email", ""),
                                            key=f"edit_delegation_email_{m['id']}",
                                        )
                                        e_role = st.text_input(
                                            "Role",
                                            value=m.get("role", ""),
                                            key=f"edit_delegation_role_{m['id']}",
                                        )
                                        e_phone = st.text_input(
                                            "Phone",
                                            value=m.get("phone", ""),
                                            key=f"edit_delegation_phone_{m['id']}",
                                        )
                                        if st.form_submit_button("💾 Save"):
                                            if e_name:
                                                db.update_delegation_member(
                                                    m["id"],
                                                    name=e_name,
                                                    email=e_email,
                                                    role=e_role,
                                                    phone=e_phone,
                                                )
                                                st.session_state.pop(
                                                    f"editing_delegation_{m['id']}",
                                                    None,
                                                )
                                                st.success("Updated!")
                                                st.rerun()
                                            else:
                                                st.warning("Name is required.")
                                        if st.form_submit_button("❌ Cancel"):
                                            st.session_state.pop(
                                                f"editing_delegation_{m['id']}", None
                                            )
                                            st.rerun()

                            # ---- Delete confirmation ----
                            if st.session_state.get(
                                f"delete_delegation_{m['id']}", False
                            ):
                                st.warning(
                                    f"⚠️ Permanently delete delegation member '{m['name']}'?"
                                )
                                col_yes, col_no = st.columns(2)
                                with col_yes:
                                    if st.button(
                                        "✅ Yes",
                                        key=f"confirm_del_delegation_{m['id']}",
                                    ):
                                        db.delete_delegation_member(m["id"])
                                        st.session_state.pop(
                                            f"delete_delegation_{m['id']}", None
                                        )
                                        st.success("Deleted.")
                                        st.rerun()
                                with col_no:
                                    if st.button(
                                        "❌ Cancel",
                                        key=f"cancel_del_delegation_{m['id']}",
                                    ):
                                        st.session_state.pop(
                                            f"delete_delegation_{m['id']}", None
                                        )
                                        st.rerun()
                            st.divider()

                st.divider()

# ------------------------------------------------------------------
# TAB 5: CONTACTS (Local Support & More)
# ------------------------------------------------------------------
with tab5:
    st.caption(
        "Manage contacts for local support (drivers, hotel concierge, local office, etc.), staff, partners, and other contacts. "
        "These can be included in your travel packs and assigned to specific itinerary items."
    )

    # ---- Session state for company filter ----
    if "selected_company_id" not in st.session_state:
        st.session_state.selected_company_id = None

    # ---- Company filter (for viewing only) ----
    companies = db.get_all_companies()
    company_options = {name: id for id, name in companies}
    company_names = list(company_options.keys())
    selected_company_label = st.selectbox(
        "Filter by Company",
        options=["All Companies"] + company_names,
        index=0,
        key="contact_filter_company",
    )
    if selected_company_label == "All Companies":
        filter_company_id = None
    else:
        filter_company_id = company_options[selected_company_label]

    # ---- Search ----
    search_term = st.text_input(
        "🔍 Search Contacts",
        placeholder="Name, role, phone, email, country, city...",
        key="contact_search",
    )

    # ---- Type filter (pill buttons) ----
    type_options = ["All", "Local Support", "Staff", "Partner", "Other"]
    selected_type = st.radio(
        "Filter by Type",
        options=type_options,
        horizontal=True,
        index=0,
        key="contact_type_filter",
    )

    # ---- Tag Filter ----
    all_contacts_for_tags = (
        db.get_contacts(filter_company_id, active_only=True)
        if filter_company_id
        else db.get_contacts(active_only=True)
    )
    all_tags = set()
    for c in all_contacts_for_tags:
        if c.get("tags"):
            for tag in [t.strip() for t in c["tags"].split(",") if t.strip()]:
                all_tags.add(tag)
    tag_options = sorted(list(all_tags))
    selected_tags = st.multiselect(
        "🏷️ Filter by Tags", options=tag_options, key="contact_tag_filter"
    )

    # ---- Add Contact Form (with company dropdown optional) ----
    with st.expander("➕ Add New Contact", expanded=False):
        with st.form("add_contact_form"):
            col1, col2 = st.columns(2)
            with col1:
                # Company dropdown (now optional)
                company_options_with_none = ["(No Company)"] + company_names
                add_company_label = st.selectbox(
                    "Company (optional)",
                    options=company_options_with_none,
                    index=0,
                    key="add_contact_company",
                )
                if add_company_label == "(No Company)":
                    add_company_id = None
                else:
                    add_company_id = company_options[add_company_label]
                add_name = st.text_input("Name*", key="add_contact_name")
                add_role = st.text_input("Role", key="add_contact_role")
                add_phone = st.text_input("Phone", key="add_contact_phone")
            with col2:
                add_email = st.text_input("Email", key="add_contact_email")
                country_list = sorted([c.name for c in pycountry.countries])
                add_country = st.selectbox(
                    "Country", options=[""] + country_list, key="add_contact_country"
                )
                add_city = st.text_input("City", key="add_contact_city")
                add_type = st.selectbox(
                    "Type",
                    options=["Local Support", "Staff", "Partner", "Other"],
                    key="add_contact_type",
                )
                add_notes = st.text_area("Notes", key="add_contact_notes")
                add_tags = st.text_input(
                    "Tags (comma-separated)", key="add_contact_tags"
                )

            submitted = st.form_submit_button("➕ Add Contact")
            if submitted:
                if not add_name:
                    st.warning("Name is required.")
                else:
                    # Check duplicates (company can be None)
                    dupes = db.find_duplicate_contacts(
                        add_company_id, name=add_name, email=add_email, phone=add_phone
                    )
                    if dupes:
                        st.warning(
                            "⚠️ A contact with the same name, email, or phone already exists in this company:"
                        )
                        for d in dupes:
                            st.write(f"- {d['name']} ({d.get('role','')})")
                        if not st.checkbox("Add anyway?", key="force_add_contact"):
                            st.stop()
                    db.add_contact(
                        company_id=add_company_id,
                        name=add_name,
                        role=add_role,
                        phone=add_phone,
                        email=add_email,
                        country=add_country,
                        city=add_city,
                        notes=add_notes,
                        tags=add_tags,
                        type=add_type,
                    )
                    st.success(f"✅ Contact '{add_name}' added!")
                    st.rerun()

    # ---- Fetch contacts based on filter ----
    all_contacts = (
        db.get_contacts(filter_company_id, active_only=True)
        if filter_company_id
        else db.get_contacts(active_only=True)
    )

    # Filter by search term
    if search_term:
        search_lower = search_term.lower()
        all_contacts = [
            c
            for c in all_contacts
            if search_lower in c["name"].lower()
            or search_lower in (c.get("role") or "").lower()
            or search_lower in (c.get("phone") or "").lower()
            or search_lower in (c.get("email") or "").lower()
            or search_lower in (c.get("country") or "").lower()
            or search_lower in (c.get("city") or "").lower()
        ]

    # Filter by type
    if selected_type != "All":
        all_contacts = [c for c in all_contacts if c.get("type") == selected_type]

    # Filter by tags
    if selected_tags:
        filtered = []
        for c in all_contacts:
            if not c.get("tags"):
                continue
            contact_tags = [t.strip() for t in c["tags"].split(",") if t.strip()]
            if any(tag in contact_tags for tag in selected_tags):
                filtered.append(c)
        all_contacts = filtered

    # ---- Display contacts ----
    if not all_contacts:
        st.info("No contacts found. Add one using the form above.")
    else:
        st.write(f"**{len(all_contacts)} contact(s)**")

        # ---- CSV Export ----
        col_export1, col_export2 = st.columns(2)
        with col_export1:
            if st.button("📥 Export CSV", key="export_contacts_csv"):
                output = io.StringIO()
                writer = csv.writer(output)
                writer.writerow(
                    [
                        "Company",
                        "Name",
                        "Role",
                        "Phone",
                        "Email",
                        "Country",
                        "City",
                        "Type",
                        "Notes",
                        "Tags",
                    ]
                )
                for c in all_contacts:
                    company_name = (
                        db.get_company(c["company_id"])["name"]
                        if c.get("company_id")
                        else ""
                    )
                    writer.writerow(
                        [
                            company_name,
                            c["name"],
                            c.get("role", ""),
                            c.get("phone", ""),
                            c.get("email", ""),
                            c.get("country", ""),
                            c.get("city", ""),
                            c.get("type", "Local Support"),
                            c.get("notes", ""),
                            c.get("tags", ""),
                        ]
                    )
                st.download_button(
                    label="⬇️ Download CSV",
                    data=output.getvalue().encode("utf-8"),
                    file_name=f"contacts_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    key="contact_csv_download",
                )

        # ---- CSV Import ----
        with col_export2:
            uploaded_file = st.file_uploader(
                "📤 Import CSV",
                type=["csv"],
                key="contact_csv_upload",
                help="Columns: Company, Name, Role, Phone, Email, Country, City, Type, Notes, Tags",
            )
            if uploaded_file is not None:
                try:
                    content = uploaded_file.getvalue().decode("utf-8").splitlines()
                    reader = csv.DictReader(content)
                    expected = [
                        "Company",
                        "Name",
                        "Role",
                        "Phone",
                        "Email",
                        "Country",
                        "City",
                        "Type",
                        "Notes",
                        "Tags",
                    ]
                    if all(h in reader.fieldnames for h in expected):
                        if st.button("Start Import", key="contact_import_btn"):
                            added = 0
                            skipped = 0
                            for row in reader:
                                company_name = row.get("Company", "").strip()
                                if company_name and company_name.lower() != "none":
                                    company_id = db._find_or_create_company(
                                        company_name
                                    )
                                else:
                                    company_id = None
                                name = row.get("Name", "").strip()
                                if not name:
                                    continue
                                # Check duplicates
                                dupes = db.find_duplicate_contacts(
                                    company_id,
                                    name=name,
                                    email=row.get("Email", "").strip() or None,
                                    phone=row.get("Phone", "").strip() or None,
                                )
                                if dupes and not st.checkbox(
                                    f"Duplicate contact '{name}' – add anyway?",
                                    key=f"force_import_{name}",
                                ):
                                    skipped += 1
                                    continue
                                db.add_contact(
                                    company_id=company_id,
                                    name=name,
                                    role=row.get("Role", "").strip() or None,
                                    phone=row.get("Phone", "").strip() or None,
                                    email=row.get("Email", "").strip() or None,
                                    country=row.get("Country", "").strip() or None,
                                    city=row.get("City", "").strip() or None,
                                    notes=row.get("Notes", "").strip() or None,
                                    tags=row.get("Tags", "").strip() or None,
                                    type=row.get("Type", "Local Support").strip()
                                    or "Local Support",
                                )
                                added += 1
                            st.success(
                                f"✅ Imported {added} contacts. Skipped {skipped} duplicates."
                            )
                            st.rerun()
                    else:
                        st.error(f"CSV must have columns: {', '.join(expected)}")
                except Exception as e:
                    st.error(f"Import failed: {e}")

        # ---- List contacts with Edit/Delete ----
        for contact in all_contacts:
            cid = contact["id"]
            # Get company name for display
            comp_name = (
                db.get_company(contact["company_id"])["name"]
                if contact.get("company_id")
                else "—"
            )
            # Type badge color
            type_color_map = {
                "Local Support": "#3b82f6",
                "Staff": "#22c55e",
                "Partner": "#ea580c",
                "Other": "#1e40af",
            }
            contact_type = contact.get("type", "Local Support")
            badge_color = type_color_map.get(contact_type, "#94a3b8")

            col1, col2, col3, col4, col5, col6 = st.columns(
                [1.5, 1.5, 1.5, 1.5, 0.8, 0.8]
            )
            with col1:
                st.write(f"**{contact['name']}**")
                if contact.get("role"):
                    st.caption(f"👤 {contact['role']}")
                # Type badge
                st.markdown(
                    f"<span style='background:{badge_color};color:white;padding:2px 10px;border-radius:12px;font-size:12px;'>"
                    f"{contact_type}</span>",
                    unsafe_allow_html=True,
                )
            with col2:
                st.write(f"🏢 {comp_name}")
            with col3:
                if contact.get("phone"):
                    st.write(f"📞 {contact['phone']}")
                if contact.get("email"):
                    st.write(f"✉️ {contact['email']}")
            with col4:
                if contact.get("country") or contact.get("city"):
                    location = f"{contact.get('city', '')}{', ' if contact.get('city') and contact.get('country') else ''}{contact.get('country', '')}"
                    st.write(f"🌍 {location}")
                if contact.get("tags"):
                    tags_list = [
                        t.strip() for t in contact["tags"].split(",") if t.strip()
                    ]
                    if tags_list:
                        badge_html = " ".join(
                            [
                                f"<span style='background:#e2e8f0;padding:2px 8px;border-radius:12px;font-size:12px;margin-right:4px;'>{t}</span>"
                                for t in tags_list
                            ]
                        )
                        st.markdown(
                            f"<div style='margin-top:4px;'>{badge_html}</div>",
                            unsafe_allow_html=True,
                        )
            with col5:
                if st.button("✏️", key=f"edit_contact_{cid}"):
                    st.session_state[f"editing_contact_{cid}"] = True
            with col6:
                if st.button("🗑️", key=f"del_contact_{cid}"):
                    st.session_state[f"delete_contact_{cid}"] = True

            # ---- Edit expander ----
            if st.session_state.get(f"editing_contact_{cid}", False):
                with st.expander(f"Edit {contact['name']}", expanded=True):
                    with st.form(key=f"edit_contact_form_{cid}"):
                        # Company dropdown (editable, optional)
                        edit_company_options_with_none = [
                            "(No Company)"
                        ] + company_names
                        current_company = (
                            comp_name if comp_name in company_names else None
                        )
                        edit_company_label = st.selectbox(
                            "Company (optional)",
                            options=edit_company_options_with_none,
                            index=(
                                edit_company_options_with_none.index(current_company)
                                if current_company in edit_company_options_with_none
                                else 0
                            ),
                            key=f"edit_contact_company_{cid}",
                        )
                        if edit_company_label == "(No Company)":
                            edit_company_id = None
                        else:
                            edit_company_id = company_options[edit_company_label]
                        edit_name = st.text_input(
                            "Name*", value=contact["name"], key=f"edit_name_{cid}"
                        )
                        edit_role = st.text_input(
                            "Role",
                            value=contact.get("role", ""),
                            key=f"edit_role_{cid}",
                        )
                        edit_phone = st.text_input(
                            "Phone",
                            value=contact.get("phone", ""),
                            key=f"edit_phone_{cid}",
                        )
                        edit_email = st.text_input(
                            "Email",
                            value=contact.get("email", ""),
                            key=f"edit_email_{cid}",
                        )
                        country_list = sorted([c.name for c in pycountry.countries])
                        edit_country = st.selectbox(
                            "Country",
                            options=[""] + country_list,
                            index=(
                                ([""] + country_list).index(contact.get("country", ""))
                                if contact.get("country", "") in country_list
                                else 0
                            ),
                            key=f"edit_country_{cid}",
                        )
                        edit_city = st.text_input(
                            "City",
                            value=contact.get("city", ""),
                            key=f"edit_city_{cid}",
                        )
                        edit_type = st.selectbox(
                            "Type",
                            options=["Local Support", "Staff", "Partner", "Other"],
                            index=["Local Support", "Staff", "Partner", "Other"].index(
                                contact.get("type", "Local Support")
                            ),
                            key=f"edit_contact_type_{cid}",
                        )
                        edit_notes = st.text_area(
                            "Notes",
                            value=contact.get("notes", ""),
                            key=f"edit_notes_{cid}",
                        )
                        edit_tags = st.text_input(
                            "Tags",
                            value=contact.get("tags", ""),
                            key=f"edit_tags_{cid}",
                        )
                        edit_active = st.checkbox(
                            "Active",
                            value=contact.get("is_active", 1),
                            key=f"edit_active_{cid}",
                        )

                        col_edit_save, col_edit_cancel = st.columns(2)
                        with col_edit_save:
                            if st.form_submit_button("💾 Save"):
                                if edit_name:
                                    db.update_contact(
                                        cid,
                                        name=edit_name,
                                        role=edit_role,
                                        phone=edit_phone,
                                        email=edit_email,
                                        country=edit_country,
                                        city=edit_city,
                                        notes=edit_notes,
                                        tags=edit_tags,
                                        is_active=edit_active,
                                        type=edit_type,
                                    )
                                    # Update company if changed
                                    if edit_company_id != contact.get("company_id"):
                                        conn = sqlite3.connect(db.DB_PATH)
                                        c = conn.cursor()
                                        c.execute(
                                            "UPDATE contacts SET company_id = ? WHERE id = ?",
                                            (edit_company_id, cid),
                                        )
                                        conn.commit()
                                        conn.close()
                                    st.session_state.pop(f"editing_contact_{cid}", None)
                                    st.success("Contact updated!")
                                    st.rerun()
                                else:
                                    st.warning("Name is required.")
                        with col_edit_cancel:
                            if st.form_submit_button("❌ Cancel"):
                                st.session_state.pop(f"editing_contact_{cid}", None)
                                st.rerun()

            # ---- Delete confirmation ----
            if st.session_state.get(f"delete_contact_{cid}", False):
                st.warning(f"⚠️ Permanently delete contact '{contact['name']}'?")
                col_yes, col_no = st.columns(2)
                with col_yes:
                    if st.button("✅ Yes", key=f"confirm_del_contact_{cid}"):
                        db.delete_contact(cid)
                        st.session_state.pop(f"delete_contact_{cid}", None)
                        st.success("Contact deleted.")
                        st.rerun()
                with col_no:
                    if st.button("❌ Cancel", key=f"cancel_del_contact_{cid}"):
                        st.session_state.pop(f"delete_contact_{cid}", None)
                        st.rerun()
            st.divider()

    # ---- Default Contacts section ----
    if filter_company_id:
        st.subheader("⭐ Default Contacts")
        company = db.get_company(filter_company_id)
        if company:
            default_ids = db.get_company_default_contacts(filter_company_id)
            all_company_contacts = db.get_contacts(filter_company_id, active_only=True)
            if all_company_contacts:
                contact_options = {
                    f"{c['name']} ({c.get('role','')})": c["id"]
                    for c in all_company_contacts
                }
                selected_defaults = [
                    f"{c['name']} ({c.get('role','')})"
                    for c in all_company_contacts
                    if c["id"] in default_ids
                ]
                new_defaults = st.multiselect(
                    "Select contacts to auto‑include in new trips for this company",
                    options=list(contact_options.keys()),
                    default=selected_defaults,
                    key="default_contact_selector",
                )
                if st.button("💾 Save Default Contacts", key="save_default_contacts"):
                    db.set_company_default_contacts(
                        filter_company_id,
                        [contact_options[opt] for opt in new_defaults],
                    )
                    st.success("Default contacts updated!")
                    st.rerun()
            else:
                st.caption("No active contacts for this company yet.")
    else:
        st.info("Select a company above to set default contacts.")
