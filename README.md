# TOV Studio

Client command center for **Take One Visuals** — a self-owned alternative to Honeybook.

Live: https://lukehegelund.github.io/tov-studio/ (login required)

## What it is
A static dashboard (this repo) backed by a Supabase database and a local agent that watches Gmail
for wedding inquiries and drafts replies in Luke's voice. **The agent never sends** — it only prepares
drafts for Luke to approve and send himself.

- **Frontend:** plain HTML/JS, served by GitHub Pages, talks to Supabase directly.
- **Auth:** Supabase Auth + Row Level Security — the public anon key cannot read any data without login.
- **Agent:** Python scripts (in the private `TOV Studio/agent/` folder, not in this repo) run locally.

## Pages / tabs
- **Dashboard** — open leads, drafts awaiting approval, bookings, income, balance due
- **Leads** — full inquiry pipeline with status
- **Clients** — every client, package, payment, balance
- **Finances** — income, expenses, net

No build step. Edit `index.html` and push to deploy.
