# ✈️ Executive Travel Planner

### *The Complete Travel Management System for Executive Assistants & Personal Assistants*

**Version 3.0** – *Now with Full CRUD, Excel Exports, Custom Categories, and Interactive Dashboards*

---

## 📋 Table of Contents

- [✈️ Executive Travel Planner](#️-executive-travel-planner)
    - [*The Complete Travel Management System for Executive Assistants \& Personal Assistants*](#the-complete-travel-management-system-for-executive-assistants--personal-assistants)
  - [📋 Table of Contents](#-table-of-contents)
  - [Overview](#overview)
  - [🚀 What's New (Recent Major Upgrades)](#-whats-new-recent-major-upgrades)
  - [✨ Full Feature Breakdown](#-full-feature-breakdown)
    - [🏢 1. Executive \& Company Management](#-1-executive--company-management)
    - [🗺️ 2. Trip Planning (Multi-City)](#️-2-trip-planning-multi-city)
    - [📋 3. Itinerary Builder (Full CRUD)](#-3-itinerary-builder-full-crud)
    - [💰 4. Budgeting \& Spending Management](#-4-budgeting--spending-management)
    - [📊 5. Spending Dashboard (Interactive)](#-5-spending-dashboard-interactive)
    - [🏷️ 6. Custom Categories](#️-6-custom-categories)
    - [📄 7. Exports \& Reporting (Now with Excel!)](#-7-exports--reporting-now-with-excel)
  - [🛠️ Tech Stack](#️-tech-stack)
  - [📦 Installation \& Setup](#-installation--setup)
    - [1. Prerequisites](#1-prerequisites)
    - [2. Download the Project](#2-download-the-project)
    - [3. Run the Setup Commands](#3-run-the-setup-commands)
  - [▶️ Running the App](#️-running-the-app)
  - [🧠 How the PA Uses It (Daily Workflow)](#-how-the-pa-uses-it-daily-workflow)
  - [📤 Complete Export Matrix](#-complete-export-matrix)
  - [📊 What Each Export Looks Like](#-what-each-export-looks-like)
    - [📄 Word Documents](#-word-documents)
    - [📊 Excel Spreadsheets](#-excel-spreadsheets)
    - [📊 CSV Files](#-csv-files)
    - [📅 Calendar (.ics)](#-calendar-ics)
  - [🗃️ File Structure](#️-file-structure)
  - [💱 Currency \& Date Management](#-currency--date-management)
  - [🧩 Extending the Tool](#-extending-the-tool)
    - [Adding a New Field to Executive Profiles](#adding-a-new-field-to-executive-profiles)
    - [Adding a New Export Format](#adding-a-new-export-format)
  - [🔒 Data Backup](#-data-backup)
  - [🐞 Troubleshooting](#-troubleshooting)
  - [📄 License](#-license)

---

## Overview

Stop juggling between spreadsheets, Word docs, and calendar invites. This tool is a single, self-contained Python application that allows **one Personal Assistant** to manage **multiple executives across multiple companies** – from storing detailed travel profiles to generating polished itineraries, expense reports, and interactive spending dashboards.

**Best of all:** 100% local. No cloud fees. No API subscriptions. All data stays on your machine.

---

## 🚀 What's New (Recent Major Upgrades)

| Feature                                      | Description                                                                                                         |
| :------------------------------------------- | :------------------------------------------------------------------------------------------------------------------ |
| **Full CRUD (Create, Read, Update, Delete)** | Edit or delete any itinerary item, trip stop, or entire trip directly from the UI. No more manual database editing! |
| **Custom Itinerary Categories**              | Create your own item types (e.g., "Car Rental", "Dinner", "Conference") alongside the defaults.                     |
| **Trip Status Workflow**                     | Mark trips as **Draft → Approved → Final** to track the planning lifecycle.                                         |
| **Interactive Spending Dashboard**           | Open (📂) any trip directly for editing, or delete (🗑️) it with a confirmation popup – all from the dashboard.        |
| **Excel Exports**                            | Export everything to Excel (.xlsx): Executive Profiles, Itineraries, Expense Reports, and Spending Dashboards.      |
| **Receipt Attachments**                      | Upload receipts (PNG, JPG, PDF) to individual itinerary items. Embedded as thumbnails in Expense Reports.           |
| **Multi‑City / Multi‑Country Stops**         | Plan complex roadshows. Each stop includes City, Region/State, and a Country dropdown.                              |
| **Structured Departure Location**            | Define a "Home Base" with City, Region, and Country for accurate route mapping.                                     |
| **DD-MM-YYYY Date Format**                   | European-style date format applied across the UI and all exported documents.                                        |
| **In-App Category Management**               | Add, view, and delete custom categories directly from the sidebar.                                                  |
| **Edit Stops**                               | Modify city, country, region, dates, or notes for any stop in the trip.                                             |

---

## ✨ Full Feature Breakdown

### 🏢 1. Executive & Company Management
- Add unlimited **Companies** with cost centers and policy notes.
- Add **Executives** with rich profiles:
  - *Core*: Name, Email, Timezone, Seat Preference.
  - *Travel Documents*: Passport Number, TSA PreCheck.
  - *Preferences*: Preferred Airline, Hotel Loyalty, Dietary, and Meal preferences.
  - **Multiple Memberships**: Store unlimited Frequent Flyer numbers and Hotel Loyalty numbers (Airline, Hotel, Car Rental).
- **Export Profiles**: Word, CSV, and Excel.

### 🗺️ 2. Trip Planning (Multi-City)
- **Departure Location**: Define the executive's "Home Base" (City, Region, Country).
- **Trip Stops**: Add unlimited stops. Each stop captures City, Region, Country, Start Date, and End Date.
- **Automatic Routing**: The system visualizes the route as `Home Base → Stop 1 → Stop 2`.
- **DD-MM-YYYY Format**: All dates are displayed and exported in the clear European format.
- **Edit Stops**: Modify any stop's details after creation.

### 📋 3. Itinerary Builder (Full CRUD)
- **Add Items**: Add Flights, Hotels, Meetings, Transport, or any **Custom Category** you create.
- **Toggle Confirmed/Estimated**: Mark items as "Booked" (Confirmed) to separate estimated costs from actual spend.
- **Edit Items**: Click the ✏️ button next to any item to update its details (time, location, cost, etc.).
- **Delete Items**: Click the 🗑️ button to instantly remove an item.
- **Receipt Attachments**: Upload receipts directly to items. View status ("Attached" / "No receipt").

### 💰 4. Budgeting & Spending Management
- Set a **Trip Budget** (multi-currency aware).
- Real-time **Spending Summary** (Estimated vs. Confirmed vs. Total).
- **Visual Progress Bar** showing budget usage percentage (Green/Orange/Red).
- **Conflict Detection**: Automatically highlights overlapping meetings and flights.

### 📊 5. Spending Dashboard (Interactive)
- **Aggregate Filters**: Filter spending by Executive or Date Range.
- **Trip-Level Breakdown**: See a detailed table of all trips with budget and spending metrics.
- **Interactive Actions**:
  - 📂 **Open Trip**: Load any trip into the main editor to modify it.
  - 🗑️ **Delete Trip**: Permanently delete trips with an inline confirmation check.
- **Status Display**: See if a trip is "Draft", "Approved", or "Final" at a glance.
- **Export**: CSV, Word, and Excel.

### 🏷️ 6. Custom Categories
- **Add Categories**: Create custom itinerary item types (e.g., "Car Rental", "Dinner", "Conference").
- **Delete Categories**: Remove unused categories from the sidebar.
- **Dynamic Dropdowns**: All item type dropdowns update automatically.

### 📄 7. Exports & Reporting (Now with Excel!)

| Export                 | Formats                            | Description                                                                                                                                          |
| :--------------------- | :--------------------------------- | :--------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Itinerary**          | Word (.docx) + Excel (.xlsx)       | Daily agenda with costs, confirmation codes, conflict warnings, and spending summary. Excel includes 3 sheets: Trip Summary, Stops, Itinerary Items. |
| **Expense Report**     | Word (.docx) + Excel (.xlsx)       | Items grouped by day with **embedded receipt thumbnails** (Word) or structured spreadsheet (Excel). Daily subtotals and grand totals.                |
| **Executive Profile**  | Word (.docx) + Excel (.xlsx) + CSV | Complete profile with preferences, memberships, and finance details.                                                                                 |
| **Calendar**           | .ics                               | One-click import into Google/Apple/Outlook calendars (hotels as multi-day events).                                                                   |
| **Spending Dashboard** | Word (.docx) + Excel (.xlsx) + CSV | Aggregate reports with totals and trip‑level breakdowns.                                                                                             |

---

## 🛠️ Tech Stack

| Layer                   | Technology                |
| :---------------------- | :------------------------ |
| **Language**            | Python 3.9+               |
| **UI Framework**        | Streamlit (1.62.0)        |
| **Database**            | SQLite (local `.db` file) |
| **Document Generation** | python-docx               |
| **Excel Export**        | openpyxl                  |
| **Calendar Files**      | icalendar                 |
| **Timezone Handling**   | pytz                      |
| **Country Dropdown**    | pycountry                 |
| **Data Export**         | Built-in `csv` module     |

---

## 📦 Installation & Setup

### 1. Prerequisites
- Python 3.9 or higher installed.
- (Optional) Git for cloning.

### 2. Download the Project
Place the following files in a folder called `travel-planner`:

```
travel-planner/
├── app.py
├── database.py
├── doc_generator.py
├── excel_export.py
├── utils.py
├── requirements.txt
└── README.md
```

### 3. Run the Setup Commands
Open your terminal and navigate to the project folder:

```bash
# 1. Create a virtual environment
python -m venv venv

# 2. Activate it
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt
```

---

## ▶️ Running the App

Every time you use the tool:

```bash
streamlit run app.py
```

Your browser will open automatically to `http://localhost:8501`.

> **Pro Tip:** If you see `bash: streamlit: command not found`, use `python -m streamlit run app.py` instead.

---

## 🧠 How the PA Uses It (Daily Workflow)

1. **Select Executive**: Choose from the dropdown. Their preferences load instantly.
2. **Create Trip**: Enter the purpose, define the *Departure City*, and add *Stops* with dates.
3. **Set Budget**: Define the overall budget for the trip.
4. **Plan Itinerary**: Add flights, hotels, meetings, etc. Use the "Add/Edit Categories" in the sidebar to customize item types.
5. **Attach Receipts**: Upload receipts directly to items using the "Attach" button.
6. **Review**: Check the real-time spending summary, budget progress bar, and conflict warnings.
7. **Generate Exports**:
   - 📄 Word Itinerary
   - 📊 Excel Itinerary
   - 🧾 Word Expense Report
   - 📊 Excel Expense Report
   - 📅 Calendar (.ics)
8. **Manage from Dashboard**: Use the spending dashboard to review historical trips, open them for edits, or delete them.

---

## 📤 Complete Export Matrix

| **What You Want to Export** | **Word (.docx)** | **Excel (.xlsx)** | **CSV** | **Calendar (.ics)** |
| :-------------------------- | :--------------- | :---------------- | :------ | :------------------ |
| **Executive Profile**       | ✅                | ✅                 | ✅       | ❌                   |
| **Trip Itinerary**          | ✅                | ✅                 | ❌       | ❌                   |
| **Expense Report**          | ✅                | ✅                 | ❌       | ❌                   |
| **Calendar Events**         | ❌                | ❌                 | ❌       | ✅                   |
| **Spending Dashboard**      | ✅                | ✅                 | ✅       | ❌                   |
| **Spending Report**         | ✅                | ❌                 | ❌       | ❌                   |

**Total export combinations:** 4 formats × 6 categories = **14 export options**.

---

## 📊 What Each Export Looks Like

### 📄 Word Documents
- **Itinerary**: Professional layout with title, route summary, executive profile, sorted daily agenda, conflict warnings, and spending summary table.
- **Expense Report**: Days as headings, tables with Time/Description/Type/Cost/Receipt (with receipt thumbnails embedded), daily totals, and final summary.
- **Executive Profile**: Company header, preference table (10+ rows), memberships section, and finance details.
- **Spending Report**: Executive name, date range, aggregate metrics, and trip‑level breakdown table.

### 📊 Excel Spreadsheets
- **Executive Profile**: Key/value table + separate memberships table.
- **Itinerary**: 3 sheets – Trip Summary, Stops, Itinerary Items – all auto‑sized with bold headers.
- **Expense Report**: Grouped by day with Date (merged), Time, Description, Type, Cost, Receipt; day subtotals; grand totals (Confirmed, Estimated, Total) with gold background.
- **Spending Dashboard**: Filtered data with bold headers and a totals row.

### 📊 CSV Files
- Raw, comma‑separated values with headers. Ideal for finance imports or pivot tables.

### 📅 Calendar (.ics)
- Standard iCalendar format. Double‑click to add to Google Calendar, Apple Calendar, or Outlook. Events are time‑zoned and include confirmation codes in descriptions.

---

## 🗃️ File Structure

```text
travel-planner/
├── app.py                      # Main Streamlit UI (All features)
├── database.py                 # SQLite models + migrations + full CRUD
├── doc_generator.py            # Word document generation (itinerary, expense, profile, spending)
├── excel_export.py             # Excel (.xlsx) exports for all data
├── utils.py                    # Conflict detection & ICS calendar generation
├── requirements.txt            # Dependencies
├── generated_itineraries/      # Saved Word itineraries (auto-created)
├── generated_expense_reports/  # Saved Expense reports (auto-created)
├── receipts/                   # Uploaded receipt images (auto-created)
└── travel_planner.db           # SQLite database (auto-created)
```

**Database Highlights**:
- **Automatic Migrations**: Adding a new column? The app handles it automatically on startup.
- **Cascade Deletes**: Deleting a trip removes all its stops and items automatically.
- **ON DELETE CASCADE**: Ensures data integrity across all related tables.

---

## 💱 Currency & Date Management

- **Currency**: Select from **USD, EUR, GBP, NGN, JPY, BRL** in the sidebar. All numbers (budgets, costs, exports) update instantly.
- **Date Format**: All dates are displayed and exported in **DD-MM-YYYY** format.
- **Timezone Dropdown**: Displays timezones with current abbreviation (e.g., `America/New_York (EDT)`).

---

## 🧩 Extending the Tool

### Adding a New Field to Executive Profiles

1. **Update `database.py`**: Add the column to the `new_exec_columns` list in `migrate_db()`.
2. **Update `database.py`**: Add the parameter to `add_executive()` and `update_executive()`.
3. **Update `app.py`**: Add a new input field in the "Add Executive" form and pass it to the DB functions.
4. **Update `doc_generator.py`**: Add the field to the `rows_data` list in `generate_executive_profile_doc()`.
5. **Update `excel_export.py`**: Add the field to the `fields` list in `export_profile_to_excel()`.

### Adding a New Export Format

1. Create a new function in `excel_export.py` (or a new file).
2. Import it into `app.py`.
3. Add a new button in the relevant section and call the function.

---

## 🔒 Data Backup

Since this is a local tool, **you are responsible for backups**:

- Click the **"💾 Backup Database"** button in the sidebar to save a timestamped copy of your `.db` file.
- For extra safety, manually copy `travel_planner.db` to a cloud drive (Dropbox, OneDrive) weekly.

---

## 🐞 Troubleshooting

| Issue                                    | Solution                                                                              |
| :--------------------------------------- | :------------------------------------------------------------------------------------ |
| **"No module named 'streamlit'"**        | Run `pip install -r requirements.txt` in your virtual environment.                    |
| **Port 8501 is busy**                    | Run `streamlit run app.py --server.port 8502`.                                        |
| **`StreamlitDuplicateElementId`**        | This is fixed in the latest version (unique `key` parameters added). Update `app.py`. |
| **"No module named 'utils'"**            | Make sure `utils.py` is in the same folder as `app.py`.                               |
| **Excel export fails**                   | Check that `openpyxl` is installed and `import os` is present in `excel_export.py`.   |
| **Database is locked**                   | Only one PA uses it – just restart the app.                                           |
| **`bash: streamlit: command not found`** | Use `python -m streamlit run app.py` instead.                                         |
| **VS Code shows import errors**          | Select the correct Python interpreter (`venv\Scripts\python.exe`).                    |

---

## 📄 License

This tool is proprietary and built specifically for internal administrative use. You are free to use and modify it for your own company workflows.

---

**Happy Planning! ✈️**

---

*Built with ❤️ for Executive Assistants everywhere.*
```