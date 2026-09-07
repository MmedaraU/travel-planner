from datetime import datetime, timedelta, date
from icalendar import Calendar, Event
import pytz


def detect_conflicts(items, exec_timezone_str="UTC"):
    """
    Check for overlapping events (flights, meetings, transport).
    Hotels are excluded.
    Returns a list of warning strings with item IDs and time details.
    All times are converted to UTC for comparison.
    """
    conflicts = []
    time_events = []

    # Fallback timezone
    fallback_tz = pytz.timezone(exec_timezone_str)

    for item in items:
        # Skip hotels – they represent stays, not timed events
        if item.get("item_type", "").lower() == "hotel":
            continue
        try:
            # Parse naive datetime strings
            start_naive = datetime.fromisoformat(item["datetime_start"])
            end_naive = (
                datetime.fromisoformat(item["datetime_end"])
                if item["datetime_end"]
                else start_naive + timedelta(hours=1)
            )

            # Get timezone from item, fallback to executive's
            tz_str = item.get("timezone") or exec_timezone_str
            tz = pytz.timezone(tz_str)

            # Localize and convert to UTC
            start_aware = tz.localize(start_naive)
            end_aware = tz.localize(end_naive)
            start_utc = start_aware.astimezone(pytz.UTC)
            end_utc = end_aware.astimezone(pytz.UTC)

            time_events.append(
                {
                    "id": item["id"],
                    "desc": item["description"],
                    "start": start_utc,
                    "end": end_utc,
                    "tz_str": tz_str,
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
                        f"from {ev1['start'].strftime('%H:%M')} to {ev1['end'].strftime('%H:%M')} UTC "
                        f"vs {ev2['start'].strftime('%H:%M')}–{ev2['end'].strftime('%H:%M')} UTC"
                    )

    return conflicts


def generate_ics(items, exec_timezone_str, destination):
    """
    Generate an .ics calendar file (as bytes) from itinerary items.
    Hotels become all-day/multi-day events.
    Each event uses its own timezone (fallback to executive's).
    """
    cal = Calendar()
    cal.add("prodid", "-//Executive Travel Planner//local//")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")

    fallback_tz = pytz.timezone(exec_timezone_str)

    for item in items:
        event = Event()
        item_type = item.get("item_type", "").lower()
        item_tz_str = item.get("timezone") or exec_timezone_str
        tz = pytz.timezone(item_tz_str)

        if item_type == "hotel":
            start_dt = datetime.fromisoformat(item["datetime_start"])
            end_dt = (
                datetime.fromisoformat(item["datetime_end"])
                if item["datetime_end"]
                else start_dt + timedelta(days=1)
            )
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
            start_naive = datetime.fromisoformat(item["datetime_start"])
            end_naive = (
                datetime.fromisoformat(item["datetime_end"])
                if item["datetime_end"]
                else start_naive + timedelta(hours=1)
            )
            # Localize to item timezone, then convert to UTC for ICS (many clients handle UTC)
            start_aware = tz.localize(start_naive)
            end_aware = tz.localize(end_naive)
            start_utc = start_aware.astimezone(pytz.UTC)
            end_utc = end_aware.astimezone(pytz.UTC)

            emoji_map = {"flight": "✈️", "meeting": "🤝", "transport": "🚗"}
            emoji = emoji_map.get(item_type, "📌")

            event.add("summary", f"{emoji} {item['description']}")
            event.add("dtstart", start_utc)
            event.add("dtend", end_utc)
            event.add("location", item.get("location", ""))
            desc = f"Type: {item['item_type']}\nConf: {item.get('confirmation_code', 'N/A')}"
            if item.get("cost"):
                desc += f"\nCost: ${item['cost']:.2f}"
            if item.get("notes"):
                desc += f"\nNotes: {item['notes']}"
            desc += f"\nOriginal timezone: {item_tz_str}"
            event.add("description", desc)

        cal.add_component(event)

    return cal.to_ical()


def format_datetime_with_timezone(
    dt_str, item_tz_str, display_tz_str, format_str="%d-%m-%Y %H:%M"
):
    """
    Convert a naive datetime string to a formatted string in a given display timezone.
    If item_tz_str is None, use display_tz_str as both source and target (no conversion).
    """
    if not dt_str:
        return ""
    try:
        dt_naive = datetime.fromisoformat(dt_str)
        # If no item timezone, assume it's already in display timezone
        if not item_tz_str:
            display_tz = pytz.timezone(display_tz_str)
            # Treat naive as if it's in display timezone
            dt_aware = display_tz.localize(dt_naive)
            return dt_aware.strftime(format_str)
        else:
            item_tz = pytz.timezone(item_tz_str)
            display_tz = pytz.timezone(display_tz_str)
            dt_aware = item_tz.localize(dt_naive)
            dt_display = dt_aware.astimezone(display_tz)
            return dt_display.strftime(format_str)
    except Exception:
        return dt_str
