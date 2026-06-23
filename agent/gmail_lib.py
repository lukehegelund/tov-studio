"""Gmail helper for TOV Studio agent. READ + DRAFT ONLY. Never sends — by design."""
import json, base64, requests, re
from email.mime.text import MIMEText
import keypaths

API = "https://gmail.googleapis.com/gmail/v1/users/me"

def _access_token():
    t = json.load(open(keypaths.GMAIL_TOKEN))
    r = requests.post(t["token_uri"], data={
        "client_id": t["client_id"], "client_secret": t["client_secret"],
        "refresh_token": t["refresh_token"], "grant_type": "refresh_token"})
    r.raise_for_status()
    return r.json()["access_token"]

def _h():
    return {"Authorization": "Bearer " + _access_token()}

def search(query, max_results=25):
    r = requests.get(f"{API}/messages", headers=_h(),
                     params={"q": query, "maxResults": max_results})
    r.raise_for_status()
    return r.json().get("messages", [])

def get_message(msg_id):
    r = requests.get(f"{API}/messages/{msg_id}", headers=_h(), params={"format": "full"})
    r.raise_for_status()
    m = r.json()
    headers = {h["name"].lower(): h["value"] for h in m["payload"].get("headers", [])}
    body = _extract_body(m["payload"])
    return {
        "id": m["id"], "threadId": m["threadId"],
        "from": headers.get("from", ""), "to": headers.get("to", ""),
        "subject": headers.get("subject", ""), "date": headers.get("date", ""),
        "message_id_header": headers.get("message-id", ""),
        "snippet": m.get("snippet", ""), "body": body[:4000],
    }

def _extract_body(payload):
    if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
        return _b64(payload["body"]["data"])
    for p in payload.get("parts", []) or []:
        t = _extract_body(p)
        if t: return t
    if payload.get("body", {}).get("data"):
        return _b64(payload["body"]["data"])
    return ""

def _b64(data):
    try: return base64.urlsafe_b64decode(data + "==").decode("utf-8", "ignore")
    except Exception: return ""

def create_draft_reply(to_addr, subject, body, thread_id, in_reply_to=None):
    """Creates a DRAFT in Gmail (in-thread). Does NOT send."""
    msg = MIMEText(body)
    msg["To"] = to_addr
    msg["Subject"] = subject if subject.lower().startswith("re:") else "Re: " + subject
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        msg["References"] = in_reply_to
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    r = requests.post(f"{API}/drafts", headers={**_h(), "Content-Type": "application/json"},
                      json={"message": {"raw": raw, "threadId": thread_id}})
    r.raise_for_status()
    return r.json().get("id")

def update_draft(draft_id, to_addr, subject, body, thread_id, in_reply_to=None):
    """Update an existing Gmail DRAFT in place (keeps it a draft — never sends)."""
    msg = MIMEText(body)
    msg["To"] = to_addr
    msg["Subject"] = subject if subject.lower().startswith("re:") else "Re: " + subject
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to; msg["References"] = in_reply_to
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    r = requests.put(f"{API}/drafts/{draft_id}", headers={**_h(), "Content-Type": "application/json"},
                     json={"message": {"raw": raw, "threadId": thread_id}})
    r.raise_for_status()
    return r.json().get("id")

def thread_has_my_reply(thread_id, my_addr="lukehegelund@gmail.com"):
    """True if Luke already sent a message in this thread (so we skip drafting)."""
    r = requests.get(f"{API}/threads/{thread_id}", headers=_h(), params={"format": "metadata",
                     "metadataHeaders": "From"})
    if not r.ok: return False
    for m in r.json().get("messages", []):
        for h in m["payload"].get("headers", []):
            if h["name"].lower() == "from" and my_addr in h["value"].lower():
                return True
    return False

def thread_has_sent_reply(thread_id):
    """True if Luke has actually SENT a message in this thread (ignores our drafts)."""
    r = requests.get(f"{API}/threads/{thread_id}", headers=_h(),
                     params={"format": "metadata", "metadataHeaders": "From"})
    if not r.ok: return False
    for m in r.json().get("messages", []):
        labels = m.get("labelIds", [])
        if "SENT" in labels and "DRAFT" not in labels:
            return True
    return False

def delete_draft(draft_id):
    try:
        requests.delete(f"{API}/drafts/{draft_id}", headers=_h())
    except Exception:
        pass

def parse_from(from_header):
    """Return (name, email) from a From header."""
    m = re.match(r'\s*"?([^"<]*)"?\s*<?([^>]*)>?', from_header)
    name = (m.group(1) or "").strip() if m else ""
    email = (m.group(2) or "").strip() if m else from_header.strip()
    return name, email
