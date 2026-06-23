#!/usr/bin/env python3
"""Scan Gmail for genuine wedding leads and prepare replies in Luke's voice.

Modes:
  --ingest-only  (default for unattended runs): store lead + proposed draft in the DB only.
                 Nothing is written to Gmail. Luke approves in the dashboard.
  --push         : create the reply as a real DRAFT in Gmail (never sends). Used after approval.
  --dry-run      : print what it would do, touch nothing.

Only genuine couple relays are treated as leads (The Knot / WeddingWire / WeddingPro).
Threads Luke already replied to are skipped. Deduped by thread.
"""
import re, argparse, datetime
import gmail_lib as G
import templates as T
import db
try:
    import calendar_lib as C
except Exception:
    C = None

_MON = {m: i for i, m in enumerate(
    ["jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"], 1)}

def to_iso(raw):
    """Best-effort 'Jun 7, 2025' or '9/25/2026' -> YYYY-MM-DD."""
    if not raw: return None
    m = re.match(r'([A-Za-z]{3})[a-z]*\.?\s+(\d{1,2}),?\s+(\d{4})', raw)
    if m and _MON.get(m.group(1).lower()):
        return f"{m.group(3)}-{_MON[m.group(1).lower()]:02d}-{int(m.group(2)):02d}"
    m = re.match(r'(\d{1,2})/(\d{1,2})/(\d{2,4})', raw)
    if m:
        y = m.group(3); y = ("20"+y) if len(y) == 2 else y
        return f"{y}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    return None

# Genuine couple-relay senders only — excludes vendor marketing (kajabi, etc.)
LEAD_SENDERS = ("member.theknot.com", "messages@weddingwire.com", "weddingpro.com",
                "mail.theknot.com")
SEARCH = ('(from:member.theknot.com OR from:messages@weddingwire.com OR from:weddingpro.com) '
          '-in:sent newer_than:{days}d')

DATE_RE = re.compile(r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}\b'
                     r'|\b\d{1,2}/\d{1,2}/\d{2,4}\b', re.I)
VENUE_RE = re.compile(r'venue[:\s]+([A-Z][^\n,;]{3,60})', re.I)

def is_lead(frm):
    f = frm.lower()
    return any(s in f for s in LEAD_SENDERS)

def get_cutoff():
    """Weddings on/after this date get the 'not booking that far ahead' reply. Changeable in-app."""
    try:
        rows = db.select("settings", {"key": "eq.booking_cutoff_date", "select": "value"})
        return rows[0]["value"] if rows and rows[0]["value"] else None
    except Exception:
        return None

def extract(msg):
    name, email = G.parse_from(msg["from"])
    first = (name or "there").split()[0]
    text = msg["subject"] + "\n" + msg["body"]
    d = DATE_RE.search(text); v = VENUE_RE.search(text)
    return {"name": first, "full_name": name, "email": email,
            "wedding_date_raw": d.group(0) if d else None,
            "venue": v.group(1).strip() if v else None}

def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--ingest-only", action="store_true")
    g.add_argument("--push", action="store_true")
    g.add_argument("--dry-run", action="store_true")
    ap.add_argument("--days", type=int, default=45)
    ap.add_argument("--max", type=int, default=25)
    args = ap.parse_args()
    mode = "push" if args.push else ("dry-run" if args.dry_run else "ingest-only")
    cutoff = get_cutoff()

    seen_threads = {i.get("gmail_thread_id") for i in
                    db.select("inquiries", {"select": "gmail_thread_id"})}
    msgs = G.search(SEARCH.format(days=args.days), max_results=args.max)
    print(f"Mode={mode}. {len(msgs)} candidate messages (last {args.days}d).\n")

    handled, made = set(), 0
    for ref in msgs:
        m = G.get_message(ref["id"])
        if not is_lead(m["from"]):           continue
        if m["threadId"] in seen_threads:    continue
        if m["threadId"] in handled:         continue   # dedup within this run
        if G.thread_has_my_reply(m["threadId"]):
            print(f"  (skip — already replied) {m['subject'][:50]}"); continue
        handled.add(m["threadId"])
        info = extract(m)
        wedding_iso = to_iso(info["wedding_date_raw"])
        booked = None
        if wedding_iso and C is not None:
            try: booked = C.is_booked(wedding_iso)
            except Exception: booked = None
        # routing: far-out date -> not-booking-yet; booked date -> decline; else available
        if wedding_iso and cutoff and wedding_iso >= cutoff:
            tmpl, body = "FAR_OUT", T.FAR_OUT(info["name"])
        elif booked:
            tmpl, body = "UNAVAILABLE", T.UNAVAILABLE(info["name"])
        else:
            tmpl, body = "AVAILABLE", T.AVAILABLE(info["name"])
        src = ("TheKnot" if "knot" in m["from"].lower()
               else "WeddingWire" if "weddingwire" in m["from"].lower() else "Direct")
        avail = "BOOKED" if booked else ("free" if booked is False else "unknown")
        print(f"• {info['full_name']} <{info['email']}> | date={wedding_iso or info['wedding_date_raw']} "
              f"venue={info['venue']} avail={avail} -> {tmpl}")
        if mode == "dry-run":
            print(f"   would prepare reply: {body[:90]}...\n"); continue

        inq = db.insert("inquiries", {
            "name": info["full_name"] or info["name"], "email": info["email"],
            "wedding_date": wedding_iso, "venue": info["venue"], "message": m["snippet"][:1000],
            "gmail_message_id": m["id"], "gmail_thread_id": m["threadId"],
            "source": src, "status": "Drafted",
            "notes": f"availability: {avail}; drafted {tmpl}"})
        msg_row = {"inquiry_id": inq["id"], "channel": "email", "to_address": info["email"],
                   "subject": "Re: " + m["subject"], "body": body, "template_used": tmpl,
                   "status": "draft", "gmail_thread_id": m["threadId"]}
        if mode == "push":
            draft_id = G.create_draft_reply(info["email"], m["subject"], body,
                                            m["threadId"], m["message_id_header"])
            msg_row["gmail_draft_id"] = draft_id
            print(f"   ✓ Gmail draft created ({draft_id})")
        db.insert("messages", msg_row, return_row=False)
        db.log("lead_ingested", f"{info['full_name']} <{info['email']}> ({mode})")
        made += 1
        print(f"   ✓ saved to dashboard\n")

    print(f"Done. {made} lead(s) prepared in {mode} mode.")

if __name__ == "__main__":
    main()
