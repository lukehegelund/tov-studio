"""Google Calendar read access for TOV Studio.
Uses the same OAuth token as Gmail (re-authorized to include calendar.readonly).
Availability rule: a date is 'booked' if any event that day has the keyword 'booked'
in its title (Luke's convention). Read-only — never writes to the calendar.
"""
import requests, datetime
import gmail_lib as G   # reuse the shared OAuth token refresh

CAL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
BUSY_KEYWORD = "booked"

def _h():
    return {"Authorization": "Bearer " + G._access_token()}

def list_events(time_min_iso, time_max_iso, max_results=250):
    r = requests.get(CAL, headers=_h(), params={
        "timeMin": time_min_iso, "timeMax": time_max_iso,
        "singleEvents": "true", "orderBy": "startTime", "maxResults": max_results})
    r.raise_for_status()
    out = []
    for e in r.json().get("items", []):
        s = e.get("start", {}); en = e.get("end", {})
        out.append({
            "id": e.get("id"), "title": e.get("summary", "(no title)"),
            "start": s.get("date") or s.get("dateTime"),
            "end": en.get("date") or en.get("dateTime"),
            "all_day": "date" in s, "location": e.get("location", ""),
        })
    return out

def events_on(date_str):
    """All events overlapping a given YYYY-MM-DD."""
    d = datetime.date.fromisoformat(date_str)
    tmin = datetime.datetime.combine(d, datetime.time.min).isoformat() + "Z"
    tmax = datetime.datetime.combine(d, datetime.time.max).isoformat() + "Z"
    return list_events(tmin, tmax)

def is_booked(date_str, keyword=BUSY_KEYWORD):
    """True if Luke has an event marked '<keyword>' on that date (he's unavailable)."""
    try:
        evs = events_on(date_str)
    except Exception:
        return None  # unknown — caller treats as 'don't assert'
    return any(keyword.lower() in (e["title"] or "").lower() for e in evs)

def upcoming(days=150):
    now = datetime.datetime.utcnow()
    tmin = now.isoformat() + "Z"
    tmax = (now + datetime.timedelta(days=days)).isoformat() + "Z"
    return list_events(tmin, tmax)
