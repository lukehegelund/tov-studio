#!/usr/bin/env python3
"""Generate a wedding contract from a client record (HTML, print-to-PDF ready).
Uses Luke's real terms (from Contracts/Wedding Contract Template for Roxanne.docx)
and current pricing. Records a contracts row. Does NOT send anything.

Usage: python3 generate_contract.py <client_id>   |   --name "Krysta Beach"
"""
import sys, html, datetime
from pathlib import Path
import db, keypaths

OUT = Path(keypaths.CONTRACTS_DIR); OUT.mkdir(parents=True, exist_ok=True)

PACKAGES = {
  "Ceremony": (1500, ["Full ceremony video (uncut)", "Drone footage of the venue (weather/location permitting)",
                       "Fast delivery — most couples receive their video the same day"], "1–2 hours of coverage"),
  "Ceremony & Reception": (2500, ["Full ceremony video (uncut)",
                       "Wedding highlight film (2–5 minutes) featuring your vows and best reception moments",
                       "Drone footage (weather/location permitting)", "Fast delivery — often same day"], "4–5 hours of coverage"),
  "Full Day": (3500, ["Full ceremony video (uncut)", "Wedding highlight film (2–5 minutes)",
                       "Getting ready footage and full reception coverage",
                       "Drone footage (weather/location permitting)", "Fast delivery — often same day"], "Up to 10 hours of coverage"),
}

CLAUSES = """
<h3>5. Cancellation Policy</h3>
<p><b>By Client:</b> If the client cancels more than 7 days before the wedding date, the deposit is
non-refundable but no further payment is required. If the client cancels less than 7 days before, the
full amount is due.</p>
<p><b>By Videographer:</b> If the videographer cancels, the client receives a full refund including the
deposit. The videographer will make every effort to find a suitable replacement.</p>
<h3>6. Refund Policy</h3>
<p>If the videographer fails to deliver the agreed-upon services, the client may request a partial or full
refund based on the extent of the shortfall, up to the total amount paid. Requests must be made within 30
days of receiving the final deliverables; the videographer will respond within 14 days. Refunds are not
issued where the issue can be fixed through a revision.</p>
<h3>7. Copyright and Usage Rights</h3>
<p>The videographer retains rights to the footage and may use it for promotional purposes (website, social
media, advertising). The client has the right to use and edit the video as they see fit.</p>
<h3>8. Liability</h3>
<p>The Client agrees to indemnify and hold harmless Luke Hegelund and Take One Visuals, LLC from any claims,
damages, or liabilities arising from injuries or damages caused by the Videographer's equipment or actions,
or any other incidents arising from the Videographer's presence at the event.</p>
<h3>9. Client Responsibilities</h3>
<p>Provide access to the venue and any practical information requested by the videographer.</p>
"""

def gen(client):
    pkg = client.get("package") or "Full Day"
    pkg_key = next((k for k in PACKAGES if k.lower() in (pkg or "").lower()), "Full Day")
    total = float(client.get("total_contracted") or PACKAGES[pkg_key][0])
    deliverables, hours = PACKAGES[pkg_key][1], PACKAGES[pkg_key][2]
    deposit = 500 if total >= 2500 else 300
    final = total - deposit
    wd = client.get("wedding_date") or "__________"
    venue = html.escape(client.get("venue") or "__________")
    name = html.escape(client.get("name") or "__________")
    today = datetime.date.today().strftime("%B %d, %Y")
    deliv = "".join(f"<li>{html.escape(d)}</li>" for d in deliverables)
    doc = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Wedding Contract — {name}</title>
<style>
body{{font:14px/1.6 Georgia,serif;max-width:720px;margin:40px auto;padding:0 24px;color:#222}}
h1{{color:#1A5E3A;font-size:24px;border-bottom:2px solid #1A5E3A;padding-bottom:8px}}
h3{{color:#1A5E3A;margin-top:22px;font-size:16px}}
.box{{background:#f6f9f7;border:1px solid #d6e3da;border-radius:8px;padding:12px 16px;margin:10px 0}}
.sig{{margin-top:40px;display:flex;justify-content:space-between;gap:40px}}
.sig div{{flex:1;border-top:1px solid #222;padding-top:6px;font-size:12px;color:#555}}
table{{width:100%;border-collapse:collapse}} td{{padding:4px 0}}
@media print{{body{{margin:0}}}}
</style></head><body>
<h1>Wedding Videography Contract</h1>
<p style="color:#777">Prepared {today} · Take One Visuals, LLC</p>

<h3>1. Parties</h3>
<div class="box"><b>Videographer:</b> Take One Visuals, LLC — Luke Hegelund · 425-524-5565 · lukehegelund@gmail.com</div>
<div class="box"><b>Client:</b> {name}<br>
Point of Contact Phone: {html.escape(client.get('phone') or '__________')}<br>
Point of Contact Email: {html.escape(client.get('email') or '__________')}<br>
Home Address (for invoice): __________________________</div>

<h3>2. Event Details</h3>
<table><tr><td><b>Wedding Date</b></td><td>{wd}</td></tr>
<tr><td><b>Venue</b></td><td>{venue}</td></tr>
<tr><td><b>Venue Address</b></td><td>__________________________</td></tr></table>

<h3>3. Services Provided — {html.escape(pkg_key)} Package</h3>
<p style="color:#555">{hours}</p><ul>{deliv}</ul>

<h3>4. Payment Terms</h3>
<div class="box"><b>Total Cost: ${total:,.0f}</b><br>
Accepted Payment Methods: Cash, Check, Venmo, or card (online invoice)<br>
<b>Deposit:</b> ${deposit:,.0f} due upon signing (non-refundable)<br>
<b>Final Payment:</b> ${final:,.0f} due on or before the wedding date</div>
{CLAUSES}
<div class="sig"><div>Client signature &amp; date</div><div>Luke Hegelund — Take One Visuals, LLC</div></div>
</body></html>"""
    safe = "".join(c for c in (client.get("name") or "client") if c.isalnum() or c in " -_")
    path = OUT / f"{safe} — Wedding Contract (TOV Studio).html"
    path.write_text(doc, encoding="utf-8")
    db.insert("contracts", {"client_id": client["id"], "status": "Draft", "provider": "manual",
              "pdf_path": str(path), "amount": total, "notes": f"auto-generated {today}"}, return_row=False)
    db.update("clients", {"id": f"eq.{client['id']}"}, {"contract_status": "Draft"})
    return path

def main():
    args = sys.argv[1:]
    if "--name" in args:
        nm = args[args.index("--name")+1]
        rows = db.select("clients", {"name": f"ilike.*{nm}*", "select": "*"})
    else:
        rows = db.select("clients", {"id": f"eq.{int(args[0])}", "select": "*"})
    if not rows: print("client not found"); return
    p = gen(rows[0])
    print("Contract written:", p)

if __name__ == "__main__":
    main()
