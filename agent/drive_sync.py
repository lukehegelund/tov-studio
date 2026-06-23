#!/usr/bin/env python3
"""Sync a client's Google Drive files into the DB cache so the dashboard can show them.
Matches each client to a subfolder (named after them) under the shared root folder.

Usage: python3 drive_sync.py <client_id>   |   --all   |   --set-root <folder_url_or_id>
"""
import sys, json, re
import db

def get_root():
    rows = db.select("settings", {"key": "eq.drive_root_folder_id", "select": "value"})
    return rows[0]["value"] if rows and rows[0]["value"] else None

def folder_id_from(s):
    m = re.search(r"/folders/([A-Za-z0-9_-]+)", s) or re.search(r"[?&]id=([A-Za-z0-9_-]+)", s)
    return m.group(1) if m else s.strip()

def set_root(url):
    import drive_lib
    fid = folder_id_from(url)
    meta = drive_lib.root_meta(fid)
    if meta.get("error") or not meta.get("id"):
        print("Could not access that folder. Did you share it with the service account?")
        print("  share with:", drive_lib.SA_EMAIL); return
    db.update("settings", {"key": "eq.drive_root_folder_id"}, {"value": fid})
    db.update("settings", {"key": "eq.drive_root_folder_name"}, {"value": meta.get("name", "")})
    print(f"Root folder linked: {meta.get('name')} ({fid})")

def sync_client(client, root):
    import drive_lib
    res = drive_lib.find_files_for_client(root, client["name"])
    files = [{"name": f["name"], "link": f.get("webViewLink"), "type": f.get("mimeType", ""),
              "id": f["id"]} for f in res["files"]]
    db.update("clients", {"id": f"eq.{client['id']}"},
              {"drive_files_json": json.dumps(files),
               "drive_folder_id": res["folder_id"] or None})
    print(f"  {client['name']}: {len(files)} file(s)" + ("" if res["folder_id"] else " (no folder yet)"))
    return len(files)

def main():
    a = sys.argv[1:]
    if a and a[0] == "--set-root":
        set_root(a[1]); return
    root = get_root()
    if not root:
        print("No Drive root folder set. Run: drive_sync.py --set-root <folder link>"); return
    if a and a[0] == "--all":
        for c in db.select("clients", {"select": "id,name"}):
            sync_client(c, root)
    elif a:
        rows = db.select("clients", {"id": f"eq.{int(a[0])}", "select": "id,name"})
        if rows: sync_client(rows[0], root)
    else:
        print("usage: drive_sync.py <client_id> | --all | --set-root <url>")

if __name__ == "__main__":
    main()
