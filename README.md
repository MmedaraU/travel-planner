# ✈️ Executive Travel Planner
### *A Local, All-in-One Desktop Tool for Executive Assistants & Personal Assistants*

**Stop manually formatting itineraries in Word. Stop tracking travel expenses in messy spreadsheets.** 

This tool is a single, self-contained Python application that allows one PA to manage multiple executives across different companies. It handles everything from storing detailed executive preferences (including passports and TSA PreCheck) to generating polished itineraries, calendar files (.ics), and comprehensive spending reports—all **entirely offline** with **zero recurring cloud costs**.

---

## 🚀 Features at a Glance

| Category                 | Key Features                                                                                                                                                                                            |
| :----------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **🏢 Administration**     | Add/Manage unlimited **Companies** and **Executives** directly from the UI. Store detailed profiles (Timezone, Seat, Airline, Passport, TSA, Meal/Dietary prefs).                                       |
| **🗓️ Itinerary Building** | Create trips with budgets. Use one-click links to **Google Flights & Booking.com** to research manually (no API costs). Add Flights, Hotels, Meetings, or Transport with costs and confirmation codes.  |
| **💰 Smart Budgeting**    | Toggle items as "Confirmed" (booked) or "Estimated" (quoted). See a **live spending summary**, a **visual budget progress bar**, and automatic **overlap/conflict detection** for meetings and flights. |
| **💱 Multi-Currency**     | Switch between **USD, EUR, GBP, NGN, JPY, BRL** on the fly. All numbers and exports update instantly.                                                                                                   |
| **📄 Executive Exports**  | Export an executive’s full profile as a **clean Word (.docx)** document or a machine-readable **CSV**.                                                                                                  |
| **📅 Itinerary Exports**  | Generate a polished **Word itinerary** (with a built-in spending summary) or a **Calendar (.ics)** file for one-click import into Google/Apple/Outlook calendars.                                       |
| **📊 Spending Dashboard** | View aggregate spending across *all* trips. Filter by Executive and Date Range. Export the data as a **CSV for finance** or a **professional Word spending report**.                                    |
| **💾 Zero Cost & Local**  | Runs 100% on your laptop. No cloud hosting, no API subscriptions, no monthly fees. One-click database backup ensures your data is safe.                                                                 |

---

## 🛠️ Tech Stack

- **Language:** Python 3.9+
- **UI Framework:** Streamlit
- **Database:** SQLite (local `.db` file)
- **Document Generation:** python-docx
- **Calendar Files:** icalendar
- **Data Manipulation:** Pandas, pytz

---

## 📦 Installation & Setup (5 Minutes)

### 1. Prerequisites
- Ensure you have **Python 3.9 or higher** installed on your machine. 
- *(Check by opening a terminal and running `python --version`)*.

### 2. Download the Project
Create a folder called `travel-planner-tool` and place the following files inside it:
- `app.py`
- `database.py`
- `doc_generator.py`
- `utils.py`
- `requirements.txt`

### 3. Run the Setup Commands
Open your terminal/command prompt, navigate to the project folder, and run:

```bash
# 1. Create a virtual environment (recommended)
python -m venv venv

# 2. Activate it
# On Windows:
venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate

# 3. Install the required packages
pip install -r requirements.txt

# 4. (Optional) Seed the database with sample executives/companies
python seed_data.py
```

*(If you don't have a `seed_data.py`, just add your first executive using the "Manage Executives & Companies" panel in the app).*

---

## ▶️ How to Run the Tool

Every time you want to use the tool, simply open your terminal, activate your virtual environment, and run:

```bash
streamlit run app.py
```

Your default browser will automatically open to `http://localhost:8501`. Keep this tab open while you work.

---

## 🖥️ How the PA Uses It (Daily Workflow)

1.  **Select the Executive**: Use the dropdown in the left sidebar. Their specific preferences (timezone, seat, diet) load automatically.
2.  **Set Up the Trip**: Enter the destination, dates, purpose, and **set a budget**. Click "Create or Update Trip".
3.  **Research Prices**: Click the **"Search Flights"** and **"Search Hotels"** buttons. These open pre-filled Google Flights and Booking.com tabs. Copy the best prices and confirmation codes.
4.  **Add Items**: In the "Add Itinerary Item" form, paste the details. 
    - *Pro Tip:* Leave the **"Confirmed" checkbox unchecked** while researching (Estimated). **Check it** once the booking is actually purchased (Confirmed).
5.  **Review the Dashboard**: Look at the real-time **Spending Summary** and the **Budget Progress Bar**. If a meeting overlaps with a flight, a red "Conflict Detected" warning appears.
6.  **Export the Deliverables**:
    - Click **"Generate Word Itinerary"** → sends a `.docx` to the executive.
    - Click **"Export to Calendar (.ics)"** → sends a file the executive can double-click to add to their Google/Apple calendar.
7.  **Monthly Reporting**: Scroll down to the **"Spending Dashboard"**. Filter by date range, click **"Export Dashboard CSV"** for accounting, or **"Export Spending Report (Word)"** for a formal review meeting.

---

## 💰 Managing Currency

The tool supports **6 global currencies**. 

- The PA can switch between **USD, EUR, GBP, NGN, JPY, and BRL** at any time using the **"💱 Currency Settings"** dropdown in the sidebar.
- **Everything updates instantly**: The budget input labels, the spending metrics, the Word documents, and even the CSV exports (which include a `Currency` column so finance knows the unit).

---

## 🗃️ File Structure (For Developers)

Here is what each file in the project does:

| File                     | Purpose                                                                                                                             |
| :----------------------- | :---------------------------------------------------------------------------------------------------------------------------------- |
| `app.py`                 | **The entire User Interface.** Contains all the Streamlit forms, buttons, and displays.                                             |
| `database.py`            | **Database Manager.** Handles SQLite queries (adding execs, trips, items). Includes auto-migration logic for new preference fields. |
| `doc_generator.py`       | **Document Engine.** Uses `python-docx` to generate the formatted Word files (Itineraries, Profiles, Spending Reports).             |
| `utils.py`               | **Helpers.** Detects scheduling conflicts and generates the `.ics` calendar files.                                                  |
| `travel_planner.db`      | **(Auto-generated)** The SQLite database storing all your companies, executives, trips, and items.                                  |
| `generated_itineraries/` | **(Auto-generated)** Folder where all your Word document exports are saved locally.                                                 |

---

## 🧩 Extending the Tool (Adding New Preferences)

If you want to add a new field to an executive's profile (e.g., `"Corporate Credit Card Number"`), follow this 4-step process:

1.  **Update `database.py`**: Add the new column name to the `exec_columns` list inside the `migrate_db()` function.
2.  **Update `database.py`**: Add the new parameter to the `add_executive()` function and the SQL `INSERT` statement.
3.  **Update `app.py`**: Add a new `st.text_input()` in the "Add Executive" form, and pass it to the `db.add_executive()` call.
4.  **Update `doc_generator.py`**: Add the new field to the `rows_data` list in `generate_executive_profile_doc()` so it appears in exports.

---

## 🔒 Data Backup (Critical)

Because this runs entirely on your local machine, **you are responsible for backups.**

- The sidebar contains a **"💾 Backup Database"** button. Click it daily to save a timestamped copy of your `travel_planner.db` file.
- For maximum safety, manually copy the `travel_planner.db` file to a cloud drive (Dropbox, Google Drive, OneDrive) at the end of each week.

---

## 🐞 Troubleshooting

| Issue                                  | Solution                                                                                                                             |
| :------------------------------------- | :----------------------------------------------------------------------------------------------------------------------------------- |
| **"No module named 'streamlit'"**      | You forgot to install the requirements. Run `pip install -r requirements.txt` in your virtual environment.                           |
| **App won't load / Port 8501 is busy** | Another Streamlit app is running. Press `Ctrl+C` in the terminal to kill it, or run `streamlit run app.py --server.port 8502`.       |
| **Database Locked error**              | SQLite locks if two processes try to write simultaneously. Only one PA uses the tool, so just restart the app.                       |
| **Can't find a specific currency**     | The tool supports 6 major currencies. If you need a custom one (e.g., CHF), add it to the `currency_options` dictionary in `app.py`. |

---

## 🤝 Contributing & Support

This is a custom-built internal tool. If you want to modify it further:

- **Add new export formats** (e.g., PDF): Look at the `doc_generator.py` file.
- **Change the budget warning threshold**: Search for `percent_used < 80` in `app.py` and change the value.
- **Add new item types** (e.g., "Car Rental"): Add it to the `item_type` list in the "Add Item" form in `app.py`.

---

## 📄 License

This tool is proprietary and built specifically for internal administrative use. You are free to use and modify it for your own company workflows.

---

**Happy Planning! 🚀**