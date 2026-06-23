"""Google Drive access for TOV Studio (service account).
Luke shares ONE folder with claude-worker@claude-automation-488200.iam.gserviceaccount.com,
then the agent can find/move/organize/share files in it — unattended.

Auto-matching: each client gets a subfolder named after them under the shared root.
'Send' = produce a shareable link the agent puts into a Gmail DRAFT (never auto-sent).
"""
import requests
from pathlib import Path
from google.oauth2 import service_account
from google.auth.transport.requests import Request

import keypaths
SA_FILE = Path(keypaths.SERVICE_ACCT)
SA_EMAIL = "claude-worker@claude-automation-488200.iam.gserviceaccount.com"
API = "https://www.googleapis.com/drive/v3"

def _token():
    creds = service_account.Credentials.from_service_account_file(
        str(SA_FILE), scopes=["https://www.googleapis.com/auth/drive"])
    creds.refresh(Request())
    return creds.token

def _h():
    return {"Authorization": "Bearer " + _token()}

def list_folder(folder_id):
    r = requests.get(f"{API}/files", headers=_h(), params={
        "q": f"'{folder_id}' in parents and trashed=false",
        "fields": "files(id,name,mimeType,size,modifiedTime,webViewLink)",
        "pageSize": 200})
    r.raise_for_status()
    return r.json().get("files", [])

def find_subfolder(root_id, name):
    safe = name.replace("'", "\\'")
    r = requests.get(f"{API}/files", headers=_h(), params={
        "q": (f"'{root_id}' in parents and name='{safe}' and "
              "mimeType='application/vnd.google-apps.folder' and trashed=false"),
        "fields": "files(id,name)"})
    fs = r.json().get("files", [])
    return fs[0]["id"] if fs else None

def create_subfolder(root_id, name):
    r = requests.post(f"{API}/files", headers={**_h(), "Content-Type": "application/json"},
        json={"name": name, "mimeType": "application/vnd.google-apps.folder", "parents": [root_id]})
    r.raise_for_status()
    return r.json()["id"]

def ensure_client_folder(root_id, client_name):
    return find_subfolder(root_id, client_name) or create_subfolder(root_id, client_name)

def find_files_for_client(root_id, client_name):
    fid = find_subfolder(root_id, client_name)
    return {"folder_id": fid, "files": list_folder(fid) if fid else []}

def move_file(file_id, new_parent, old_parent=None):
    params = {"addParents": new_parent}
    if old_parent: params["removeParents"] = old_parent
    r = requests.patch(f"{API}/files/{file_id}", headers=_h(), params=params)
    r.raise_for_status(); return r.json()

def rename(file_id, new_name):
    r = requests.patch(f"{API}/files/{file_id}", headers={**_h(), "Content-Type": "application/json"},
                       json={"name": new_name})
    r.raise_for_status(); return r.json()

def share_link(file_id):
    """Make a file link-viewable and return its shareable URL."""
    requests.post(f"{API}/files/{file_id}/permissions", headers={**_h(), "Content-Type": "application/json"},
                  json={"role": "reader", "type": "anyone"})
    r = requests.get(f"{API}/files/{file_id}", headers=_h(), params={"fields": "webViewLink,name"})
    return r.json()

def root_meta(folder_id):
    r = requests.get(f"{API}/files/{folder_id}", headers=_h(),
                     params={"fields": "id,name,capabilities"})
    return r.json() if r.ok else {"error": r.text[:200]}
