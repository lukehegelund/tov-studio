"""Supabase REST helper (service_role — bypasses RLS). Agent-side only."""
import json, requests
import keypaths

_k = json.load(open(keypaths.SUPABASE_KEYS))
URL, SR = _k["url"], _k["service_role"]
_H = {"apikey": SR, "Authorization": "Bearer " + SR, "Content-Type": "application/json"}

def select(table, params=None):
    r = requests.get(f"{URL}/rest/v1/{table}", headers=_H, params=params or {"select": "*"})
    r.raise_for_status()
    return r.json()

def insert(table, row, return_row=True):
    h = dict(_H); h["Prefer"] = "return=representation" if return_row else "return=minimal"
    r = requests.post(f"{URL}/rest/v1/{table}", headers=h, json=row)
    r.raise_for_status()
    return r.json()[0] if return_row and r.text else None

def update(table, match, patch):
    r = requests.patch(f"{URL}/rest/v1/{table}", headers={**_H, "Prefer": "return=minimal"},
                       params=match, json=patch)
    r.raise_for_status()

def log(action, detail, level="info"):
    try: insert("agent_log", {"action": action, "detail": detail[:1000], "level": level}, return_row=False)
    except Exception: pass
