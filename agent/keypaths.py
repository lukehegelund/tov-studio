"""Resolve credential/file paths so the agent works in BOTH locations:
 - interactive (this folder under ~/Documents) -> falls back to the canonical HQ paths
 - relocated runtime (~/.tov-studio, where macOS lets launchd run) -> uses local copies
A file is used from THIS folder if present, else from the original Documents location.
"""
import os
HERE = os.path.dirname(os.path.abspath(__file__))
_HQ = "/Users/danhegelund/Documents/Claude/HQ"
_SECRETS_DOC = "/Users/danhegelund/Documents/Claude/TOV Studio/SECRETS.local.txt"
_CONTRACTS_DOC = "/Users/danhegelund/Documents/Claude/Take One Visuals/Contracts"

def _p(name, fallback):
    local = os.path.join(HERE, name)
    return local if os.path.exists(local) else fallback

RELOCATED   = os.path.exists(os.path.join(HERE, "tov_supabase_keys.json"))
SUPABASE_KEYS = _p("tov_supabase_keys.json", os.path.join(_HQ, "tov_supabase_keys.json"))
GMAIL_TOKEN   = _p("gmail_token.json",        os.path.join(_HQ, "gmail_token.json"))
SERVICE_ACCT  = _p("service_account.json",    os.path.join(_HQ, "service_account.json"))
SECRETS       = _p("SECRETS.local.txt",       _SECRETS_DOC)
CONTRACTS_DIR = os.path.join(HERE, "contracts") if RELOCATED else _CONTRACTS_DOC
