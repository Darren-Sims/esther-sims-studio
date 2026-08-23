# Esther Sims Studio — Admin

A small tool for running the day-to-day of the studio: commissions, deadlines,
invoices, and client emails, in one place.

## What it does

- **Commissions** — track every commission from enquiry through to completion,
  with client details, price, deposit, deadline, and a status pipeline
  (Enquiry → Deposit Requested → Confirmed → In Progress → Awaiting Client
  Approval → Ready to Ship → Completed).
- **Clients** — a simple address book, linked to their commissions.
- **Invoices** — generate a deposit or balance invoice for any commission,
  download it as a branded PDF, and track paid/unpaid status.
- **Email templates** — seven ready-made templates covering the whole
  commission lifecycle (enquiry reply, deposit request, confirmation,
  progress update, ready-for-approval, shipped, and a deadline reminder for
  yourself). Open a commission, pick a stage, and the client's details are
  filled in automatically — copy and paste into your own email client.
- **Dashboard** — upcoming deadlines and outstanding invoices at a glance.

Branding (colours, logo, typography) is pulled from esthersimsstudio.co.uk.

## Running it locally

Requires Python 3.10+.

```bash
pip install -r requirements.txt
python app.py
```

Then open http://localhost:5000 — the first visit walks you through creating
a login (this only happens once; there's just one account for the studio).

Data is stored in `instance/esther_studio.db` (a SQLite file). Back this
file up from time to time — e.g. copy it somewhere safe after a busy day of
admin, or set up automatic backups if this ends up hosted somewhere.

## Deploying it properly (so Esther can use it from anywhere)

This is a normal Flask app, so it will run on Render, Railway, Fly.io, PythonAnywhere,
or similar. The only two things to set as environment variables in production:

- `SECRET_KEY` — any long random string (keeps login sessions secure)
- `PORT` — usually set automatically by the host

The SQLite file works fine for a single freelancer's admin tool, but if you
deploy somewhere that wipes the disk between deploys (Render's free web
service tier does this), you'll want either a persistent disk add-on, or to
switch storage to a managed Postgres database — the schema in `db.py` is
plain SQL and would need only small changes to run on Postgres instead.

## Customising

- **Email templates** are editable in the app itself (Email templates → Edit) —
  no code changes needed.
- **Business details, invoice numbering, payment instructions** live under
  Settings.
- **Colours/fonts** are CSS variables at the top of `static/css/style.css`.
