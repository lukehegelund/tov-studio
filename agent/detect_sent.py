#!/usr/bin/env python3
"""Detect inquiries where Luke has now SENT a reply from Gmail, and archive them:
  - inquiry status -> 'Responded'
  - its draft message(s) -> 'sent' (and remove our now-superseded Gmail draft)
Runs every agent cycle so the dashboard stays in sync with what Luke actually sent.
"""
import datetime
import gmail_lib as G
import db
NOW = datetime.datetime.utcnow().isoformat()

def main():
    active = db.select("inquiries", {"select": "*",
        "status": "in.(New,Drafted,Responded)", "gmail_thread_id": "not.is.null"})
    archived = 0
    for inq in active:
        tid = inq["gmail_thread_id"]
        if not tid: continue
        try:
            sent = G.thread_has_sent_reply(tid)
        except Exception:
            continue
        if not sent: continue
        if inq["status"] != "Responded":
            db.update("inquiries", {"id": f"eq.{inq['id']}"}, {"status": "Responded"})
        # mark our draft message(s) as sent, clean up leftover Gmail drafts
        for m in db.select("messages", {"inquiry_id": f"eq.{inq['id']}", "status": "eq.draft", "select": "*"}):
            if m.get("gmail_draft_id"):
                G.delete_draft(m["gmail_draft_id"])   # safe if already gone (sent draft auto-removes)
            db.update("messages", {"id": f"eq.{m['id']}"}, {"status": "sent", "sent_at": NOW})
        db.log("sent_detected", f"{inq['name']} — marked Responded & archived")
        archived += 1
        print(f"  ✓ {inq['name']}: detected sent reply -> archived")
    print(f"Sent-detection: {archived} inquiry(ies) archived.")

if __name__ == "__main__":
    main()
