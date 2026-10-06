# ✈️ Executive Travel Planner

### *The Complete Travel Management System for Executive Assistants & Personal Assistants*

**Version 4.0** – *Per-Stop Weather, Bulk Import, Templates, Reorderable Stops & Items, Inline Add, and Mobile-Ready Travel Packs*

---

## 📋 Table of Contents

- [Overview](#overview)
- [What's New](#-whats-new-v40)
- [Full Feature Breakdown](#-full-feature-breakdown)
- [Tech Stack](#️-tech-stack)
- [Installation & Setup](#-installation--setup)
- [Running the App](#️-running-the-app)
- [How the PA Uses It (Daily Workflow)](#-how-the-pa-uses-it-daily-workflow)
- [Complete Export Matrix](#-complete-export-matrix)
- [What Each Export Looks Like](#-what-each-export-looks-like)
- [File Structure](#-file-structure)
- [Currency & Date Management](#-currency--date-management)
- [Extending the Tool](#-extending-the-tool)
- [Data Backup](#-data-backup)
- [Troubleshooting](#-troubleshooting)
- [License](#-license)

---

## Overview

Stop juggling between spreadsheets, Word docs, and calendar invites. This single Python application lets **one Personal Assistant** manage **multiple executives across multiple companies** – from storing detailed travel profiles to generating polished itineraries, expense reports, and a mobile-ready travel pack the executive can actually use on the road.

**Best of all:** 100% local. No cloud fees. No API subscriptions. All data stays on your machine.

---

## 🚀 What's New (v4.0)

| Feature                             | Description                                                                                                                                                                                          |
| :---------------------------------- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **🏠 Dashboard Tab**                 | New home tab with at-a-glance metrics: active executives, companies, upcoming trips (30 days), spending snapshot (month / quarter / YTD), per-executive spend breakdown, and library content counts. |
| **📦 Mobile-Ready Travel Pack**      | Self-contained HTML pack with a responsive layout the executive can read on a phone. Inline preview in the app — no need to download and open. Also exports to PDF and Word.                         |
| **🌦️ Per-Stop Weather**              | Weather is now shown **for each stop, in its own date window** — not just the first city. The "Now" line appears only for the stop currently in progress.                                            |
| **📋 Bulk Paste Itinerary**          | Paste rows straight from Excel, Google Sheets, or a CSV. Auto-detects headers, previews, and imports. Available in both the trip create form and the trip edit modal.                                |
| **💰 Bulk Import Expenses**          | Paste a spreadsheet of expenses for an entire delegation in one go. Validates traveler names against the trip roster.                                                                                |
| **📄 Duplicate Trip / Item**         | One-click copy of a trip (with stops, items, delegation, checklists) or an individual item (+1 day shift, carries delegation and contacts).                                                          |
| **↑ ↓ Reorder**                     | Reorder stops and items with up/down buttons. No more delete-and-re-add.                                                                                                                             |
| **☑ Bulk Item Delete**              | Tick items and delete them in one action, in both the trip modal and the create form.                                                                                                                |
| **➕ Inline Add**                    | Add a new venue or delegation member directly from the form that needs them — no tab switching.                                                                                                      |
| **📅 Curated Timezone Shortlist**    | Common business-travel timezones (New York, London, Tokyo, Dubai, Lagos, …) at the top of every timezone dropdown.                                                                                   |
| **🛂 Dismissible Passport Warnings** | Acknowledge a passport expiry warning for 90 days so it stops nagging after you've seen it.                                                                                                          |
| **📅 Monthly Backup Reminder**       | Banner in the last 5 days of each month if the last backup was >25 days ago.                                                                                                                         |
| **🧩 Library Tab**                   | Destination Guides, Visa Rules, Checklist Templates, Packing Templates, Trip Templates, and an Emergency Directory (hospitals, embassy / consulate records, per-country emergency numbers).          |

---

## ✨ Full Feature Breakdown

### 🏠 1. Dashboard

- **Top metrics**: active executives, companies, contacts, total trips.
- **Trip status split**: upcoming (next 30 days), in progress, past.
- **Spending snapshot**: this month, this quarter, this year-to-date.
- **Per-executive spend breakdown**, sorted descending.
- **Library content counts** — guides, visa rules, templates, hospitals, embassies, venues.
- **Recently created trips** — five most recent.

### 👤 2. Executive & Company Management

- **Executives**: rich profiles with timezone, seat preference, dietary, meal preference, preferred airline, TSA PreCheck, passport(s), and unlimited memberships.
- **Passports**: multiple per executive, with expiry warnings that escalate at 90 / 180 days and can be dismissed for 90 days.
- **Memberships**: airline, hotel, car rental, lounge, rail, ferry, ride-share, credit card.
- **Companies**: cost centers, policy notes, default contacts, active/inactive state.
- **Export Profiles**: Word, CSV, Excel.

### 🗺️ 3. Trip Planning (Multi-City)

- **Departure location**: Home Base with City, Region, Country.
- **Stops**: unlimited, with **↑ ↓ reorder**, edit, and delete.
- **Inline venue add**: create a new venue without leaving the stop or item form.
- **Trip status workflow**: Draft → Approved → Final (locks the trip from edits).
- **Timezone display mode**: Home (executive's timezone) or Destination (each item's own timezone).

### 📋 4. Itinerary Builder

- **Add items individually** or **bulk paste from a spreadsheet** (auto-detects headers, previews before import).
- **Per-item fields**: type, description, start / end, location, cost, currency, cost date, timezone, venue, confirmation code, notes, delegation members, local support contacts.
- **↑ ↓ reorder** items by swapping times with the item above or below.
- **📄 Duplicate item** — copies every field and shifts start / end / cost date forward one day. Ideal for return flights and next-night hotels.
- **☑ Batch select and delete** items with a Select-All toggle.
- **Inline venue add** inside every item edit form.
- **Receipt attachments**: upload PNG, JPG, or PDF.

### 💰 5. Budgeting & Expenses

- Set a **Trip Budget** in the base currency; per-item costs in any currency, converted using historical rates on the item's cost date.
- **Spending summary**: Estimated vs. Confirmed vs. Total, live in the trip modal.
- **Per diem**: daily rate and days per traveler.
- **Expenses**: single entry form with receipt upload, plus **bulk import from a spreadsheet** with traveler-name validation.
- **Per-traveler breakdown**: allowance, spent, remaining, color-coded.
- **Conflict detection**: warns on overlapping flights, meetings, and transport.

### 📊 6. All Trips (Spending Dashboard)

- **Filters**: executive, date range, free-text search, "include past trips" toggle.
- **Trip-level breakdown**: budget, total spent, confirmed, estimated, status.
- **Mass select and delete** trips in one action.
- **Open any trip** with **📂 Edit** — the full trip edit modal.
- **Export**: CSV, Word, Excel, and `.ics` calendar (all trips in the current filter).

### 👥 7. Contacts

- Contacts filtered by company, type, tag, and free text.
- Contact types: Emergency, Local Support, Staff, Partner, Other — each with its own collapsible group.
- **Default contacts per company** auto-populate on new trips.
- **CSV import / export** with duplicate detection.

### 🏢 8. Venues

- Reusable venue library with address, city, country, WiFi credentials, badge info, dress code, and notes.
- Attach any venue to a session-type itinerary item (Meeting, Conference, Dinner, Site Visit, Tour, Activity).
- Filter by country, search by name / address / city.

### 📚 9. Library

Six sub-tabs of reusable content:

- **📋 Trip Templates** — save any trip as a template, then create new trips from it with new dates and budget.
- **🌍 Destination Guides** — language, currency, emergency numbers, etiquette, phrases, packing tips, connectivity notes, recommended apps.
- **🛂 Visa Rules** — passport nationality → destination pairs with visa requirement, max stay, processing time, fee.
- **✅ Checklist Templates** — reusable checklist skeletons, applied per trip.
- **🎒 Packing Templates** — reusable packing lists, applied per traveler.
- **🚨 Emergency Directory** — hospitals (by city / country), emergency numbers per country (sourced from Destination Guides), embassies and consulates (by host and representing country).

### 📄 10. Exports & Reporting

| Export                | Formats                | Description                                                                                                                                                                             |
| :-------------------- | :--------------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Travel Pack**       | HTML + PDF + Word      | Self-contained itinerary: route, per-stop weather, delegation, hotels, agenda, venues, local support, expenses, packing lists, checklists, emergency info, and embedded receipt images. |
| **Itinerary**         | Word + Excel           | Daily agenda with costs, confirmation codes, and timezone-aware times.                                                                                                                  |
| **Expense Report**    | Word + Excel           | Items grouped by day with **embedded receipt thumbnails** (Word) or structured spreadsheet (Excel).                                                                                     |
| **Executive Profile** | Word + Excel + CSV     | Complete profile with preferences, memberships, and passport details.                                                                                                                   |
| **Company Profile**   | HTML + Word + Excel    | Company overview with executives, contacts, and policy notes.                                                                                                                           |
| **Calendar**          | .ics                   | Multi-trip calendar export — one event per itinerary item, prefixed with the trip name.                                                                                                 |
| **Spending Report**   | Word + Excel + CSV     | Aggregate reports with totals and trip-level breakdowns.                                                                                                                                |
| **Database**          | JSON + CSV (ZIP) + .db | Full snapshot for backup or migration.                                                                                                                                                  |

---

## 🛠️ Tech Stack

| Layer                 | Technology                          |
| :-------------------- | :---------------------------------- |
| **Language**          | Python 3.10+                        |
| **UI Framework**      | Streamlit                           |
| **Database**          | SQLite (local `.db` file, WAL mode) |
| **Word Documents**    | python-docx                         |
| **PDF Rendering**     | WeasyPrint                          |
| **HTML Templating**   | Jinja2                              |
| **Excel Export**      | openpyxl                            |
| **Calendar Files**    | icalendar                           |
| **Timezone Handling** | pytz                                |
| **Country Dropdown**  | pycountry                           |
| **Weather**           | Open-Meteo (no API key required)    |
| **Data Export**       | Built-in `csv` module               |

---

## 📦 Installation & Setup

### 1. Prerequisites

- Python **3.10** or higher
- **WeasyPrint system libraries** for PDF export:
  - **macOS**: `brew install pango libffi`
  - **Ubuntu / Debian**: `sudo apt install libpango-1.0-0 libpangoft2-1.0-0`
  - **Windows**: WeasyPrint ships wheels for recent versions; if PDF export fails, install the GTK runtime and add it to PATH

### 2. Download the Project

```
travel-planner/
├── app.py
├── database.py
├── doc_generator.py
├── excel_export.py
├── currency.py
├── duplicate_detection.py
├── utils.py
├── weather.py
├── templates/
│   ├── travel_pack.html
│   └── company_profile.html
├── requirements.txt
└── README.md
```

### 3. Run the Setup Commands

```bash
python -m venv venv

# Windows:
venv\Scripts\activate
# Mac / Linux:
source venv/bin/activate

pip install -r requirements.txt
```

---

## ▶️ Running the App

```bash
streamlit run app.py
```

Your browser opens at `http://localhost:8501`. On first run, `travel_planner.db` is created and all tables are set up automatically. Migrations run on every start, so updates to the schema are applied without manual work.

> **Pro Tip:** If `streamlit` isn't on your PATH, use `python -m streamlit run app.py`.

---

## 🧠 How the PA Uses It (Daily Workflow)

1. **Select Executive** — choose from the sidebar. Their timezone, preferences, and passport warnings load immediately.
2. **Create Trip** — enter purpose, dates, departure city, budget, and base currency. Status starts as Draft.
3. **Add Stops** — one at a time, in the order they'll be visited. Use ↑ ↓ to reorder.
4. **Add Delegation** — pick travelers from the company roster, or use the **➕ Add a new person** expander inline.
5. **Plan Itinerary** — add items one at a time, or **📋 Paste from spreadsheet**. Every item carries cost, currency, timezone, venue, and contacts.
6. **Attach Receipts** — upload per item, or drop them in the shared folder URL (shown on the travel pack).
7. **Set Per Diem & Expenses** — daily rate × days per traveler. Bulk import expenses from a spreadsheet.
8. **Review** — spending summary, budget usage, conflict warnings, and a live travel pack preview.
9. **Generate Travel Pack** — one click gives the executive a phone-friendly HTML, a PDF, or a Word document.
10. **Export** — Word / Excel / CSV / .ics from the All Trips tab, or push the trip through Draft → Approved → Final when ready.
11. **Reuse** — save recurring trips as templates in the Library, then create new trips from them in one click.

---

## 📤 Complete Export Matrix

| **What You Want to Export** | **HTML** | **PDF** | **Word** | **Excel** | **CSV** | **ICS** |
| :-------------------------- | :------: | :-----: | :------: | :-------: | :-----: | :-----: |
| **Travel Pack**             |    ✅     |    ✅    |    ✅     |     —     |    —    |    —    |
| **Executive Profile**       |    —     |    —    |    ✅     |     ✅     |    ✅    |    —    |
| **Company Profile**         |    ✅     |    —    |    ✅     |     ✅     |    —    |    —    |
| **Trip Itinerary**          |    —     |    —    |    ✅     |     ✅     |    —    |    —    |
| **Expense Report**          |    —     |    —    |    ✅     |     ✅     |    —    |    —    |
| **Multi-Trip Calendar**     |    —     |    —    |    —     |     —     |    —    |    ✅    |
| **Spending Dashboard**      |    —     |    —    |    ✅     |     ✅     |    ✅    |    —    |
| **Full Database**           |    —     |    —    |    —     |     —     |   ZIP   |    —    |

---

## 📊 What Each Export Looks Like

### 📦 Travel Pack

- **HTML** — self-contained, responsive, mobile-friendly. Embeds receipt images inline as base64. Coloured cards for each section: route, weather (per stop), delegation, hotels, agenda, venues, local support, expenses, packing lists, checklists, emergency info.
- **PDF** — same layout, rendered via WeasyPrint. Page breaks preserve section integrity.
- **Word** — same content, native Word headings and tables.

### 📄 Word Documents

- **Itinerary** — title, route summary, executive profile, sorted daily agenda, conflict warnings, spending summary.
- **Expense Report** — days as headings, tables with Time / Description / Type / Cost / Receipt, embedded receipt thumbnails, daily totals, grand totals.
- **Executive Profile** — company header, preference table, memberships, and finance details.
- **Spending Report** — executive name, date range, aggregate metrics, trip-level breakdown.
- **Company Profile** — company header, executive roster, contact list, policy notes.

### 📊 Excel Spreadsheets

- **Executive Profile** — key/value table + separate memberships sheet.
- **Itinerary** — 3 sheets: Trip Summary, Stops, Itinerary Items.
- **Expense Report** — grouped by day with Date merged, Time, Description, Type, Cost, Receipt; day subtotals; grand totals.
- **Spending Dashboard** — filtered data with bold headers and a totals row.

### 📅 Calendar (.ics)

Standard iCalendar format. Double-click to import into Google Calendar, Apple Calendar, or Outlook. Events are timezone-aware and include confirmation codes. Multi-trip export names each event with the trip's purpose.

### 💾 Database Snapshot

- **JSON** — every table, structured. Ideal for inspection or migration.
- **CSV (ZIP)** — one CSV per table. Ideal for spreadsheet-based analysis.
- **.db** — a byte-for-byte copy of `travel_planner.db`. The safest backup.

---

## 🗃️ File Structure

```
travel-planner/
├── app.py                          # Streamlit UI — every tab and form
├── database.py                     # SQLite schema, migrations, CRUD
├── doc_generator.py                # Travel Pack (HTML / PDF / Word),
│                                   # company & exec profiles, spending report
├── excel_export.py                 # Excel exports
├── utils.py                        # Timezone helpers, ICS export, bulk parsers
├── currency.py                     # Exchange rate fetching + conversion + symbols
├── duplicate_detection.py          # Fuzzy matching for execs, trips, contacts, venues
├── weather.py                      # Weather fetching (current, forecast, range)
├── templates/
│   ├── travel_pack.html            # Jinja2 template for the HTML travel pack
│   └── company_profile.html        # Jinja2 template for the HTML company profile
├── requirements.txt
├── travel_planner.db               # SQLite database (auto-created)
├── app_state.json                  # Backup reminder state (auto-created)
├── dismissed_warnings.json         # Acknowledged passport warnings (auto-created)
├── receipts/
│   └── trip_<id>/                  # Per-trip receipt uploads (auto-created)
└── README.md
```

**Database highlights:**

- **Automatic migrations** — schema upgrades run on every startup; no manual SQL.
- **Cascade deletes** — deleting a trip removes its stops, items, delegation, per-diem, expenses, packing lists, and checklists.
- **WAL mode** — a single writer, many readers, so reads don't block writes.

---

## 💱 Currency & Date Management

- **Multi-currency**: set a base currency per trip; enter costs in any supported currency.
- **Historical accuracy**: each item carries a **cost date**; conversion uses the rate on that date, not today's rate. Rates are fetched from a free API and cached in the database.
- **Date format**: DD-MM-YYYY throughout the UI and every exported document.
- **Timezone dropdown**: curated shortlist of ~28 business-travel zones at the top, followed by the full list, each showing its current abbreviation (e.g. `America/New_York (EDT)`).

---

## 🧩 Extending the Tool

### Adding a New Field to Executive Profiles

1. **`database.py`** — add the column to the `for col, ddl in [...]` list in `migrate_db()`.
2. **`database.py`** — add the parameter to `add_executive()` and `update_executive()`.
3. **`app.py`** — add the input field in the executive form and pass it to the DB functions.
4. **`doc_generator.py`** — add the field to the profile doc generation.
5. **`excel_export.py`** — add the field to `export_profile_to_excel()`.

### Adding a New Itinerary Category

The category list is seeded on first run and can be extended by inserting into the `categories` table:

```sql
INSERT INTO categories (name) VALUES ('Helicopter');
```

The new category appears in every Type dropdown immediately.

### Adding a New Export Format

1. Write a new function in `excel_export.py` (or a new module).
2. Import it into `app.py`.
3. Add a button in the relevant section and call the function.

### Adding a Bulk Import Parser

Two parsers already exist in `utils.py`:

- `parse_itinerary_paste(raw_text, default_timezone)` — TSV / CSV → itinerary items
- `parse_expense_paste(raw_text, default_currency)` — TSV / CSV → expenses

Both return `(parsed_rows, errors)`. Follow the same shape for any new bulk-import UI.

---

## 🔒 Data Backup

This is a local tool, so **backups are your responsibility**. The app helps:

- **📤 Export Database → ⬇️ Backup .db** — one-click timestamped copy of your database.
- **📤 Export Database → JSON / CSV (ZIP)** — for inspection or migration.
- **📅 Monthly reminder** — a banner appears in the last 5 days of each month if the last backup was more than 25 days ago. Click **✅ Mark as Backed Up** to acknowledge and silence the reminder.

For extra safety, sync `travel_planner.db` to a cloud drive (Dropbox, OneDrive, iCloud) once a week.

---

## 🐞 Troubleshooting

| Issue                                      | Solution                                                                                                                       |
| :----------------------------------------- | :----------------------------------------------------------------------------------------------------------------------------- |
| **`No module named 'streamlit'`**          | Activate the venv, then `pip install -r requirements.txt`.                                                                     |
| **Port 8501 is busy**                      | `streamlit run app.py --server.port 8502`.                                                                                     |
| **`StreamlitDuplicateElementKey`**         | Fixed in v4.0. If you still see it, run the diagnostic in the "Duplicate key" section below.                                   |
| **`No module named 'utils'`**              | Ensure all `.py` files sit in the same folder as `app.py`.                                                                     |
| **`No module named 'weather'`**            | Add `weather.py` (used by the trip modal and the travel pack).                                                                 |
| **Excel export fails**                     | Check `openpyxl` is installed.                                                                                                 |
| **PDF export fails**                       | Install WeasyPrint system libraries (see Installation).                                                                        |
| **Travel pack is empty / broken layout**   | Confirm `templates/travel_pack.html` exists and is valid HTML.                                                                 |
| **Weather section missing in travel pack** | Check the city names on the trip's stops; some spellings may not resolve. If all cities fail, the section is silently omitted. |
| **Database is locked**                     | Only one PA uses it — restart the app. WAL mode reduces this to near-zero.                                                     |
| **`bash: streamlit: command not found`**   | Use `python -m streamlit run app.py`.                                                                                          |
| **VS Code shows import errors**            | Select the venv interpreter: `venv\Scripts\python.exe`.                                                                        |

### Duplicate key diagnostic

If you see `StreamlitDuplicateElementKey` on a trip checkbox, run:

```bash
python -c "
import database as db
summary = db.get_spending_summary()
print('Rows:', len(summary))
seen = {}
for i, t in enumerate(summary):
    raw = t.get('trip_id')
    seen.setdefault((raw, type(raw).__name__), []).append(i)
for k, idxs in seen.items():
    if len(idxs) > 1:
        print('DUPLICATE:', k, 'at', idxs)
"
```

If a `DUPLICATE` line appears, `get_spending_summary()` is returning two rows for the same trip. The All Trips tab already dedupes on display, but the underlying query should be investigated.

---

## 📄 License

This tool is proprietary and built specifically for internal administrative use. You are free to use and modify it for your own company workflows.

**Happy Planning! ✈️**  
*Built with ❤️ for Executive Assistants everywhere.*


---

## Summary of what changed

| Section                 | Change                                                                                                                         |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| **Title**               | Version 3.0 → 4.0; new subtitle highlighting the v4.0 features                                                                 |
| **Table of contents**   | Updated anchors for the renamed "What's New" section                                                                           |
| **What's New**          | Complete rewrite — all 13 new features vs. the old 8                                                                           |
| **Feature breakdown**   | Split into 10 sections (was 7); added Dashboard, Contacts, Venues, Library, Travel Pack; refreshed Budgeting, Trips, Itinerary |
| **Tech stack**          | Python 3.9 → 3.10; Streamlit version removed (unpinned); added WeasyPrint, Jinja2, Open-Meteo                                  |
| **Installation**        | Added WeasyPrint system libraries per OS; updated file structure to include `weather.py` and `templates/`                      |
| **Daily workflow**      | Rewritten to reflect the actual flow: stops with reorder, bulk paste, per diem, travel pack, templates                         |
| **Export matrix**       | Now includes HTML and PDF; Travel Pack row added                                                                               |
| **Export descriptions** | Travel Pack section added; Company Profile section added; Calendar section updated for multi-trip export                       |
| **File structure**      | Added `weather.py`, `templates/`, `app_state.json`, `dismissed_warnings.json`; corrected `receipts/` path                      |
| **Currency section**    | Added historical cost-date conversion note and timezone shortlist mention                                                      |
| **Extending section**   | Added "New Itinerary Category" and "Bulk Import Parser" subsections                                                            |
| **Backup section**      | Updated to reflect the monthly reminder and Mark as Backed Up button                                                           |
| **Troubleshooting**     | Added weather, PDF, template, and duplicate-key entries; added diagnostic script                                               |
| **License**             | Unchanged                                                                                                                      |