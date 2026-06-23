"""Stripe + Dropbox Sign + Twilio — ready-to-activate.
Each reads keys from TOV Studio/SECRETS.local.txt. If a key is blank, the function
returns a clear 'not configured' result instead of failing. Nothing here sends money
or contracts without Luke first adding keys AND triggering the action.
"""
import requests
from pathlib import Path
import keypaths

SECRETS = Path(keypaths.SECRETS)

def load_secrets():
    d = {}
    for line in SECRETS.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1); d[k.strip()] = v.strip()
    return d

# ---------------- STRIPE ----------------
def stripe_create_invoice(client_email, amount, description, send=False):
    """Create a Stripe invoice (draft by default). Set send=True to finalize+email."""
    s = load_secrets(); key = s.get("STRIPE_SECRET_KEY")
    if not key: return {"ok": False, "reason": "Stripe not configured (add STRIPE_SECRET_KEY)"}
    H = {"Authorization": "Bearer " + key}
    cust = requests.post("https://api.stripe.com/v1/customers", headers=H,
                         data={"email": client_email}).json()
    requests.post("https://api.stripe.com/v1/invoiceitems", headers=H,
                  data={"customer": cust["id"], "amount": int(amount*100),
                        "currency": "usd", "description": description})
    inv = requests.post("https://api.stripe.com/v1/invoices", headers=H,
                        data={"customer": cust["id"], "collection_method": "send_invoice",
                              "days_until_due": 30, "auto_advance": "true" if send else "false"}).json()
    if send:
        inv = requests.post(f"https://api.stripe.com/v1/invoices/{inv['id']}/send", headers=H).json()
    return {"ok": True, "invoice_id": inv.get("id"), "url": inv.get("hosted_invoice_url"),
            "status": inv.get("status")}

def stripe_recent_payments(limit=20):
    s = load_secrets(); key = s.get("STRIPE_SECRET_KEY")
    if not key: return {"ok": False, "reason": "Stripe not configured"}
    r = requests.get("https://api.stripe.com/v1/payment_intents",
                     headers={"Authorization": "Bearer " + key}, params={"limit": limit})
    return {"ok": True, "data": r.json().get("data", [])}

# ---------------- DROPBOX SIGN (e-signature) ----------------
def dropboxsign_send(signer_email, signer_name, file_path, title="Wedding Videography Contract"):
    s = load_secrets(); key = s.get("ESIGN_API_KEY")
    if not key: return {"ok": False, "reason": "E-sign not configured (add ESIGN_API_KEY)"}
    with open(file_path, "rb") as f:
        r = requests.post("https://api.hellosign.com/v3/signature_request/send",
            auth=(key, ""),
            data={"title": title, "subject": "Your Take One Visuals contract",
                  "signers[0][email_address]": signer_email, "signers[0][name]": signer_name,
                  "test_mode": "1"},
            files={"file[0]": f})
    j = r.json()
    sr = j.get("signature_request", {})
    return {"ok": r.ok, "request_id": sr.get("signature_request_id"), "raw": j if not r.ok else None}

def dropboxsign_status(request_id):
    s = load_secrets(); key = s.get("ESIGN_API_KEY")
    if not key: return {"ok": False, "reason": "E-sign not configured"}
    r = requests.get(f"https://api.hellosign.com/v3/signature_request/{request_id}", auth=(key, ""))
    sr = r.json().get("signature_request", {})
    return {"ok": True, "is_complete": sr.get("is_complete"), "signatures": sr.get("signatures")}

# ---------------- TWILIO (SMS to secondary contacts) ----------------
def twilio_send_sms(to_number, body):
    s = load_secrets()
    sid, tok, frm = s.get("TWILIO_ACCOUNT_SID"), s.get("TWILIO_AUTH_TOKEN"), s.get("TWILIO_PHONE_NUMBER")
    if not (sid and tok and frm): return {"ok": False, "reason": "Twilio not configured"}
    r = requests.post(f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
                      auth=(sid, tok), data={"To": to_number, "From": frm, "Body": body})
    return {"ok": r.ok, "sid": r.json().get("sid") if r.ok else None, "raw": r.json() if not r.ok else None}
