#!/usr/bin/env python3
"""Sync upcoming Google Calendar events into the DB so the dashboard can render them.
Read-only. Marks each event is_booked if its title contains the 'booked' keyword.
Usage: python3 calendar_sync.py [--days N]
"""
import sys, json, requests
import calendar_lib as C
import db

def main():
    days = 150
    if "--days" in sys.argv: days = int(sys.argv[sys.argv.index("--days")+1])
    evs = C.upcoming(days)
    # replace the cached set
    requests.delete(f"{db.URL}/rest/v1/calendar_events?id=gt.0",
                    headers={**db._H, "Prefer": "return=minimal"})
    rows = [{"gcal_id": e["id"], "title": e["title"], "start_at": e["start"], "end_at": e["end"],
             "all_day": e["all_day"], "location": e["location"],
             "is_booked": C.BUSY_KEYWORD in (e["title"] or "").lower()} for e in evs]
    if rows:
        requests.post(f"{db.URL}/rest/v1/calendar_events",
                      headers={**db._H, "Prefer": "return=minimal"}, json=rows)
    booked = sum(1 for r in rows if r["is_booked"])
    db.log("calendar_sync", f"{len(rows)} events synced, {booked} booked")
    print(f"Synced {len(rows)} events ({booked} marked booked).")

if __name__ == "__main__":
    main()
