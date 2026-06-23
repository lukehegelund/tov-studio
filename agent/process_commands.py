#!/usr/bin/env python3
"""Process the dashboard's command_queue.

Structured commands handled here:
  push_draft:<message_id>   -> create the approved reply as a real Gmail DRAFT (never sends)
  discard:<message_id>      -> mark message discarded

Free-text commands are left 'pending' for the Claude agent run to interpret and act on.
"""
import sys
import gmail_lib as G
import db

def push_draft(msg_id):
    rows = db.select("messages", {"id": f"eq.{msg_id}", "select": "*"})
    if not rows: return f"message {msg_id} not found"
    m = rows[0]
    if m.get("gmail_draft_id"): return "draft already exists"
    inq = db.select("inquiries", {"id": f"eq.{m['inquiry_id']}", "select": "*"})
    inq = inq[0] if inq else {}
    # fetch original to thread the reply correctly
    in_reply_to = None
    if inq.get("gmail_message_id"):
        try: in_reply_to = G.get_message(inq["gmail_message_id"]).get("message_id_header")
        except Exception: pass
    draft_id = G.create_draft_reply(m["to_address"], m["subject"], m["body"],
                                    m.get("gmail_thread_id"), in_reply_to)
    db.update("messages", {"id": f"eq.{msg_id}"},
              {"gmail_draft_id": draft_id})  # stays 'draft' — visible + editable in the app
    if inq: db.update("inquiries", {"id": f"eq.{inq['id']}"}, {"status": "Drafted"})
    return f"Gmail draft created ({draft_id}) for {m['to_address']}"

def draft_followup(task_id):
    """Draft the follow-up email for a milestone task (Gmail draft, never sent)."""
    import followups as F
    t = db.select("tasks", {"id": f"eq.{task_id}", "select": "*"})
    if not t: return "task not found"
    t = t[0]
    cl = db.select("clients", {"id": f"eq.{t['client_id']}", "select": "*"})[0]
    if not cl.get("email"): return "client has no email"
    title = (t.get("title") or "Follow-up").split(" — ")[0]
    body = F.email_body(t.get("milestone_key"), cl["name"], cl.get("wedding_date") or "your date")
    draft_id = G.create_draft_reply(cl["email"], f"Take One Visuals — {title}", body, None)
    db.insert("messages", {"client_id": cl["id"], "channel": "email", "to_address": cl["email"],
              "subject": f"Take One Visuals — {title}", "body": body,
              "template_used": f"followup:{t.get('milestone_key')}", "status": "draft",
              "gmail_draft_id": draft_id}, return_row=False)
    db.update("tasks", {"id": f"eq.{task_id}"}, {"status": "in_progress"})
    return f"follow-up draft created for {cl['email']}"

def create_invoice(client_id, amount, ptype):
    """Create + send a Stripe invoice for a client. Explicit, user-initiated action."""
    import integrations
    cl = db.select("clients", {"id": f"eq.{client_id}", "select": "*"})
    if not cl: return "client not found"
    cl = cl[0]
    if not cl.get("email"): return "client has no email"
    r = integrations.stripe_create_invoice(cl["email"], amount,
            f"{ptype} payment — Take One Visuals ({cl.get('package','')})", send=True)
    if not r.get("ok"): return r.get("reason", "stripe error")
    db.insert("invoices", {"client_id": client_id, "type": ptype, "amount": amount,
              "stripe_invoice_id": r["invoice_id"], "hosted_invoice_url": r["url"],
              "status": r.get("status", "sent"), "due_date": None}, return_row=False)
    return f"invoice for ${amount:.0f} sent to {cl['email']}"

def sync_stripe():
    """Pull recent Stripe payments into the payments table (dedup by stripe id)."""
    import integrations
    r = integrations.stripe_recent_payments(50)
    if not r.get("ok"): return r.get("reason", "stripe error")
    seen = {p["stripe_payment_id"] for p in db.select("payments", {"select": "stripe_payment_id"})
            if p.get("stripe_payment_id")}
    added = 0
    for pi in r["data"]:
        if pi.get("status") != "succeeded" or pi["id"] in seen: continue
        db.insert("payments", {"amount": pi["amount"] / 100.0, "method": "Stripe",
                  "stripe_payment_id": pi["id"], "type": "Partial",
                  "date": __import__("datetime").date.today().isoformat(),
                  "notes": (pi.get("description") or "Stripe payment")}, return_row=False)
        added += 1
    return f"synced {added} new Stripe payment(s)"

def draft_files_email(client_id):
    """Create a Gmail DRAFT to the client containing shareable Drive links. Never sends."""
    import json, drive_lib
    cl = db.select("clients", {"id": f"eq.{client_id}", "select": "*"})
    if not cl: return "client not found"
    cl = cl[0]
    if not cl.get("email"): return "client has no email on file"
    files = json.loads(cl.get("drive_files_json") or "[]")
    if not files: return "no Drive files cached — sync first"
    links = []
    for f in files:
        meta = drive_lib.share_link(f["id"])      # ensure link-viewable
        links.append(f"• {f['name']}: {meta.get('webViewLink', f.get('link',''))}")
    first = (cl["name"] or "there").split()[0]
    body = (f"Hi {first}!\n\nHere are your wedding video files:\n\n" + "\n".join(links) +
            "\n\nLet me know if you have any trouble accessing them!\n\nBest,\nLuke")
    draft_id = G.create_draft_reply(cl["email"], "Your Take One Visuals files", body, None)
    db.insert("messages", {"client_id": client_id, "channel": "email", "to_address": cl["email"],
              "subject": "Your Take One Visuals files", "body": body, "template_used": "files",
              "status": "approved", "gmail_draft_id": draft_id}, return_row=False)
    return f"Gmail draft with {len(files)} file link(s) created for {cl['email']}"

def main():
    cmds = db.select("command_queue", {"status": "eq.pending", "select": "*",
                                       "order": "created_at"})
    print(f"{len(cmds)} pending command(s).")
    for c in cmds:
        cmd = c["command"].strip()
        try:
            if cmd.startswith("push_draft:"):
                res = push_draft(int(cmd.split(":", 1)[1]))
                db.update("command_queue", {"id": f"eq.{c['id']}"},
                          {"status": "done", "result": res})
                print(" ✓", cmd, "->", res); db.log("command", res)
            elif cmd.startswith("discard:"):
                db.update("messages", {"id": f"eq.{int(cmd.split(':',1)[1])}"}, {"status": "discarded"})
                db.update("command_queue", {"id": f"eq.{c['id']}"}, {"status": "done", "result": "discarded"})
                print(" ✓", cmd)
            elif cmd.startswith("set_root:"):
                import drive_sync; drive_sync.set_root(cmd.split(":", 1)[1])
                db.update("command_queue", {"id": f"eq.{c['id']}"}, {"status": "done", "result": "root set"})
                print(" ✓", cmd)
            elif cmd.startswith("sync_drive:"):
                import drive_sync; arg = cmd.split(":", 1)[1]
                root = drive_sync.get_root()
                if not root:
                    raise RuntimeError("no Drive root folder set yet")
                if arg == "all":
                    for cl in db.select("clients", {"select": "id,name"}): drive_sync.sync_client(cl, root)
                    res = "synced all clients"
                else:
                    cl = db.select("clients", {"id": f"eq.{int(arg)}", "select": "id,name"})[0]
                    n = drive_sync.sync_client(cl, root); res = f"{cl['name']}: {n} files"
                db.update("command_queue", {"id": f"eq.{c['id']}"}, {"status": "done", "result": res})
                print(" ✓", cmd, "->", res)
            elif cmd.startswith("update_draft:"):
                mid = int(cmd.split(":", 1)[1])
                m = db.select("messages", {"id": f"eq.{mid}", "select": "*"})[0]
                if m.get("gmail_draft_id"):
                    G.update_draft(m["gmail_draft_id"], m["to_address"], m.get("subject", ""),
                                   m["body"], m.get("gmail_thread_id"))
                    res = "gmail draft updated"
                else:
                    res = push_draft(mid)   # no gmail draft yet -> create one
                db.update("command_queue", {"id": f"eq.{c['id']}"}, {"status": "done", "result": res})
                print(" ✓", cmd, "->", res)
            elif cmd.startswith("create_invoice:"):
                _, cid, amount, ptype = cmd.split(":", 3)
                res = create_invoice(int(cid), float(amount), ptype)
                db.update("command_queue", {"id": f"eq.{c['id']}"}, {"status": "done", "result": res})
                print(" ✓", cmd, "->", res)
            elif cmd.startswith("draft_followup:"):
                res = draft_followup(int(cmd.split(":", 1)[1]))
                db.update("command_queue", {"id": f"eq.{c['id']}"}, {"status": "done", "result": res})
                print(" ✓", cmd, "->", res)
            elif cmd == "sync_stripe":
                res = sync_stripe()
                db.update("command_queue", {"id": f"eq.{c['id']}"}, {"status": "done", "result": res})
                print(" ✓", cmd, "->", res)
            elif cmd == "sync_calendar":
                import calendar_sync; calendar_sync.main()
                db.update("command_queue", {"id": f"eq.{c['id']}"}, {"status": "done", "result": "calendar synced"})
                print(" ✓", cmd)
            elif cmd.startswith("gen_contract:"):
                import generate_contract as gc
                cl = db.select("clients", {"id": f"eq.{int(cmd.split(':',1)[1])}", "select": "*"})[0]
                p = gc.gen(cl); res = f"contract written: {p.name}"
                db.update("command_queue", {"id": f"eq.{c['id']}"}, {"status": "done", "result": res})
                print(" ✓", cmd, "->", res)
            elif cmd.startswith("send_files:"):
                res = draft_files_email(int(cmd.split(":", 1)[1]))
                db.update("command_queue", {"id": f"eq.{c['id']}"}, {"status": "done", "result": res})
                print(" ✓", cmd, "->", res); db.log("command", res)
            else:
                # natural-language command -> flag for the AI; the poller won't touch it again
                db.update("command_queue", {"id": f"eq.{c['id']}"}, {"status": "needs_ai"})
                print(" …NL command flagged for AI:", cmd[:60])
        except Exception as e:
            db.update("command_queue", {"id": f"eq.{c['id']}"},
                      {"status": "error", "result": str(e)[:300]})
            print(" ✗", cmd, "->", e)

if __name__ == "__main__":
    main()
