#!/usr/bin/env python3
"""Project follow-up engine. For each active wedding (Booked/InProduction with a future date):
  1. ensure the standard milestone checklist exists (auto-created tasks), and
  2. auto-draft a follow-up email (Gmail draft, never sent) for any milestone that's come due.

Milestones are templated and dated relative to the wedding date — change them here.
"""
import datetime
import db, gmail_lib as G

TODAY = datetime.date.today()

# offset = days relative to wedding date (negative = before). email=True milestones get a draft when due.
MILESTONES = [
    {"key": "contract",  "title": "Send contract",                 "offset": -90, "email": True},
    {"key": "deposit",   "title": "Send deposit invoice",          "offset": -90, "email": False},
    {"key": "timeline",  "title": "Confirm timeline & shot list",  "offset": -30, "email": True},
    {"key": "final",     "title": "Final payment reminder",        "offset": -7,  "email": True},
    {"key": "delivery",  "title": "Deliver video & request review","offset": 2,   "email": True},
]

def email_body(key, name, date_str):
    n = (name or "there").split()[0]
    return {
        "contract":  f"Hi {n}! Sending over your contract for the wedding on {date_str}. Take a look and "
                     "let me know if anything needs adjusting, then you can sign whenever you're ready!",
        "timeline":  f"Hi {n}! Your wedding on {date_str} is coming up — I'd love to confirm the timeline "
                     "and any must-have moments you want captured. When's a good time for a quick call?",
        "final":     f"Hi {n}! Quick reminder that the final payment is due before {date_str}. Let me know "
                     "if you have any questions — so excited to film your day!",
        "delivery":  f"Hi {n}! It was such a joy filming your wedding! Your video is ready. If you loved it, "
                     "a quick review would mean the world to me. Thank you again for having me!",
    }.get(key, f"Hi {n}! Just following up about your wedding on {date_str}.")

def ensure_and_draft(client):
    wd = client.get("wedding_date")
    if not wd: return 0
    wdate = datetime.date.fromisoformat(wd)
    existing = {t["milestone_key"]: t for t in db.select("tasks",
                {"client_id": f"eq.{client['id']}", "select": "*"}) if t.get("milestone_key")}
    made = 0
    for m in MILESTONES:
        due = (wdate + datetime.timedelta(days=m["offset"])).isoformat()
        t = existing.get(m["key"])
        if not t:
            t = db.insert("tasks", {"title": f"{m['title']} — {client['name']}",
                    "client_id": client["id"], "milestone_key": m["key"], "due_date": due,
                    "kind": "followup", "status": "open"})
            made += 1
        # auto-draft a follow-up email once it's due (email milestones only, not yet drafted/done)
        if (m["email"] and t["status"] == "open" and due <= TODAY.isoformat()
                and client.get("email")):
            body = email_body(m["key"], client["name"], wd)
            draft_id = G.create_draft_reply(client["email"], f"Take One Visuals — {m['title']}",
                                            body, None)
            db.insert("messages", {"client_id": client["id"], "channel": "email",
                      "to_address": client["email"], "subject": f"Take One Visuals — {m['title']}",
                      "body": body, "template_used": f"followup:{m['key']}", "status": "draft",
                      "gmail_draft_id": draft_id}, return_row=False)
            db.update("tasks", {"id": f"eq.{t['id']}"}, {"status": "in_progress"})
            db.log("followup_drafted", f"{client['name']}: {m['title']}")
    return made

def main():
    clients = db.select("clients", {"select": "*", "status": "in.(Booked,InProduction)"})
    total = 0
    for c in clients:
        if c.get("wedding_date") and c["wedding_date"] >= TODAY.isoformat():
            total += ensure_and_draft(c)
    print(f"Follow-ups: ensured milestones for active weddings ({total} new tasks).")

if __name__ == "__main__":
    main()
