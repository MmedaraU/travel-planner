from datetime import datetime, timedelta, date
from icalendar import Calendar, Event
import pytz


def detect_conflicts(items):
    """
    Check for overlapping events (flights, meetings, transport).
    Hotels are excluded from overlap checks.
    Returns a list of warning strings with item IDs and time details.
    """
    conflicts = []
    time_events = []

    for item in items:
        # Skip hotels – they represent stays, not timed events
        if item["item_type"].lower() == "hotel":
            continue
        try:
            start = datetime.fromisoformat(item["datetime_start"])
            end = (
                datetime.fromisoformat(item["datetime_end"])
                if item["datetime_end"]
                else start + timedelta(hours=1)
            )
            time_events.append(
                {
                    "id": item["id"],
                    "desc": item["description"],
                    "start": start,
                    "end": end,
                }
            )
        except (TypeError, ValueError):
            continue

    for i, ev1 in enumerate(time_events):
        for j, ev2 in enumerate(time_events):
            if i < j:
                if ev1["start"] < ev2["end"] and ev2["start"] < ev1["end"]:
                    conflicts.append(
                        f"⏰ '{ev1['desc']}' (ID: {ev1['id']}) overlaps with "
                        f"'{ev2['desc']}' (ID: {ev2['id']}) "
                        f"from {ev1['start'].strftime('%H:%M')} to {ev1['end'].strftime('%H:%M')} "
                        f"vs {ev2['start'].strftime('%H:%M')}–{ev2['end'].strftime('%H:%M')}"
                    )

    return conflicts


def generate_ics(items, exec_timezone_str, destination):
    """
    Generate an .ics calendar file (as bytes) from itinerary items.
    Hotels become all-day/multi-day events.
    """
    cal = Calendar()
    cal.add("prodid", "-//Executive Travel Planner//local//")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")

    tz = pytz.timezone(exec_timezone_str)

    for item in items:
        event = Event()
        item_type = item["item_type"].lower()

        if item_type == "hotel":
            start_dt = datetime.fromisoformat(item["datetime_start"])
            end_dt = datetime.fromisoformat(item["datetime_end"])
            start_date = start_dt.date()
            end_date = end_dt.date()

            event.add("summary", f"🏨 Hotel: {item['description']}")
            event.add("dtstart", start_date)
            event.add("dtend", end_date)
            event.add("location", item.get("location", ""))
            desc = f"Confirmation: {item.get('confirmation_code', 'N/A')}"
            if item.get("notes"):
                desc += f"\nNotes: {item['notes']}"
            event.add("description", desc)

        else:
            start_dt = datetime.fromisoformat(item["datetime_start"])
            if item["datetime_end"]:
                end_dt = datetime.fromisoformat(item["datetime_end"])
            else:
                end_dt = start_dt + timedelta(hours=1)

            start_dt = tz.localize(start_dt)
            end_dt = tz.localize(end_dt)

            emoji_map = {"flight": "✈️", "meeting": "🤝", "transport": "🚗"}
            emoji = emoji_map.get(item_type, "📌")

            event.add("summary", f"{emoji} {item['description']}")
            event.add("dtstart", start_dt)
            event.add("dtend", end_dt)
            event.add("location", item.get("location", ""))
            desc = f"Type: {item['item_type']}\nConf: {item.get('confirmation_code', 'N/A')}"
            if item.get("cost"):
                desc += f"\nCost: ${item['cost']:.2f}"
            if item.get("notes"):
                desc += f"\nNotes: {item['notes']}"
            event.add("description", desc)

        cal.add_component(event)

    return cal.to_ical()
