#!/usr/bin/env python3
"""AI command interpreter (Sonnet 4.6). Processes 'needs_ai' commands from the queue:
turns a natural-language instruction into either a structured action the poller runs,
or a direct answer. Only fires when there's a command waiting — no cost otherwise.
"""
import json, anthropic
import db, integrations

MODEL = "claude-sonnet-4-6"

STRUCTURED = """Available structured commands you can queue (the system executes them):
- gen_contract:<client_id>          generate a contract for a client
- create_invoice:<client_id>:<amount>:<type>   send a Stripe invoice (type=Deposit|Final|Partial)
- sync_drive:<client_id> | sync_drive:all      pull a client's Google Drive files
- send_files:<client_id>            draft an email to the client with their Drive file links
- draft_followup:<task_id>          draft a follow-up email for a milestone task
- push_draft:<message_id>           create a Gmail draft for a prepared reply
- sync_stripe                       pull recent Stripe payments into the books"""

SCHEMA = {"type": "object", "additionalProperties": False,
  "properties": {
    "action": {"type": "string", "enum": ["queue_command", "answer"]},
    "command": {"type": "string", "description": "structured command if action=queue_command, else empty"},
    "answer": {"type": "string", "description": "direct answer if action=answer, else empty"}},
  "required": ["action", "command", "answer"]}

def context():
    clients = db.select("clients", {"select": "id,name,status,total_contracted,total_paid,balance_due,package,wedding_date,email"})
    inq = db.select("inquiries", {"select": "id,name,status,wedding_date"})
    tasks = db.select("tasks", {"select": "id,title,status,due_date", "status": "neq.done"})
    return (f"CLIENTS:\n{json.dumps(clients, default=str)}\n\n"
            f"INQUIRIES:\n{json.dumps(inq, default=str)}\n\n"
            f"OPEN TASKS:\n{json.dumps(tasks, default=str)}")

def interpret(client, cmd_text):
    sys = ("You are the command interpreter for TOV Studio, Luke's wedding-videography CRM. "
           "Given Luke's instruction and the current data, EITHER map it to one structured command "
           "(resolving names to IDs from the data), OR answer his question directly and concisely "
           "using the data. Money is USD.\n\n" + STRUCTURED)
    r = client.messages.create(model=MODEL, max_tokens=600,
        system=sys,
        messages=[{"role": "user", "content": f"{context()}\n\nLuke's command: {cmd_text}"}],
        output_config={"format": {"type": "json_schema", "schema": SCHEMA}})
    txt = next(b.text for b in r.content if b.type == "text")
    return json.loads(txt)

def main():
    pending = db.select("command_queue", {"status": "eq.needs_ai", "select": "*", "order": "created_at"})
    if not pending:
        print("No AI commands waiting."); return
    key = integrations.load_secrets().get("ANTHROPIC_API_KEY")
    if not key:
        print("ANTHROPIC_API_KEY not set"); return
    ac = anthropic.Anthropic(api_key=key)
    for c in pending:
        try:
            out = interpret(ac, c["command"])
            if out["action"] == "queue_command" and out["command"]:
                db.insert("command_queue", {"command": out["command"]}, return_row=False)
                res = f"→ queued: {out['command']}"
            else:
                res = out.get("answer") or "(no answer)"
            db.update("command_queue", {"id": f"eq.{c['id']}"}, {"status": "done", "result": res[:1000]})
            db.log("ai_interpret", f"{c['command'][:50]} => {res[:80]}")
            print(f" ✓ {c['command'][:50]} => {res[:80]}")
        except Exception as e:
            db.update("command_queue", {"id": f"eq.{c['id']}"}, {"status": "error", "result": str(e)[:300]})
            print(f" ✗ {c['command'][:40]}: {e}")

if __name__ == "__main__":
    main()
