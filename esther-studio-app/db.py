"""
Database layer for the Esther Sims Studio admin tool.

Uses plain sqlite3 (Python stdlib) so the app has zero heavyweight
dependencies. One connection per request, opened via Flask's `g` object.
"""

import sqlite3
import os
from datetime import datetime, date

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "instance", "esther_studio.db")

COMMISSION_STATUSES = [
    "Enquiry",
    "Deposit Requested",
    "Confirmed",
    "In Progress",
    "Awaiting Client Approval",
    "Ready to Ship",
    "Completed",
    "Cancelled",
]

# Statuses that count as "active" work on the dashboard
ACTIVE_STATUSES = [
    "Deposit Requested",
    "Confirmed",
    "In Progress",
    "Awaiting Client Approval",
    "Ready to Ship",
]

COMMISSION_TYPES = [
    "House Portrait",
    "Pet Portrait",
    "Couple/Family Portrait",
    "Other",
]

INVOICE_KINDS = ["Deposit", "Balance", "Full Payment"]
INVOICE_STATUSES = ["Draft", "Sent", "Paid", "Overdue", "Cancelled"]

DEFAULT_SETTINGS = {
    "business_name": "Esther Sims Studio",
    "business_email": "esthersimsstudio@gmail.com",
    "business_location": "Derby, UK",
    "invoice_prefix": "ESS",
    "next_invoice_seq": "1",
    "default_deposit_percent": "30",
    "currency_symbol": "£",
    "payment_instructions": "Bank transfer — sort code / account number to be added in Settings.",
    "logo_url": "https://cdn.prod.website-files.com/63ee391d6609d63fbc92b869/640f16c3a90a2d4d45e15ad9_nav-logo.svg",
    "website_url": "https://www.esthersimsstudio.co.uk/",
}

DEFAULT_EMAIL_TEMPLATES = [
    dict(
        key="enquiry_response",
        name="1. Enquiry response",
        subject="Re: Your commission enquiry — {{business_name}}",
        body=(
            "Hi {{client_first_name}},\n\n"
            "Thank you so much for getting in touch about a {{commission_type}} — I'd love to help bring this to life.\n\n"
            "To get things moving, could you send over:\n"
            "  - A few clear reference photos\n"
            "  - Your preferred size (A5, 8x10\" or A4)\n"
            "  - Any dates or occasions I should be aware of\n\n"
            "Once I have those I'll confirm pricing and an estimated timeline, and we can get your commission booked in.\n\n"
            "Speak soon,\n{{artist_name}}\n{{business_name}}"
        ),
    ),
    dict(
        key="deposit_request",
        name="2. Deposit request",
        subject="Next steps for your {{commission_type}} — {{business_name}}",
        body=(
            "Hi {{client_first_name}},\n\n"
            "Thank you for confirming your {{commission_type}}! Here's a quick summary:\n\n"
            "  Size: {{size}}\n"
            "  Total price: {{price}}\n"
            "  Deposit due now: {{deposit_amount}}\n"
            "  Estimated completion: {{deadline}}\n\n"
            "To secure your place in my commission schedule, I ask for a {{deposit_percent}}% deposit "
            "({{deposit_amount}}) up front, with the remaining {{balance_amount}} due once your portrait is "
            "ready. {{payment_instructions}}\n\n"
            "As soon as the deposit lands I'll pop you in the schedule and let you know your start date.\n\n"
            "Thank you!\n{{artist_name}}\n{{business_name}}"
        ),
    ),
    dict(
        key="commission_confirmed",
        name="3. Commission confirmed",
        subject="You're booked in! — {{business_name}}",
        body=(
            "Hi {{client_first_name}},\n\n"
            "Lovely — your deposit has landed and your {{commission_type}} is officially booked in.\n\n"
            "I'm aiming to have this finished by {{deadline}}. I'll send a progress update as I go, and you'll "
            "get to see the piece for approval before it's shipped.\n\n"
            "Thank you for commissioning me — I can't wait to get started!\n\n"
            "{{artist_name}}\n{{business_name}}"
        ),
    ),
    dict(
        key="progress_update",
        name="4. Progress update",
        subject="A little progress on your {{commission_type}}",
        body=(
            "Hi {{client_first_name}},\n\n"
            "Just a quick update — I've made a start on your {{commission_type}} and it's coming along "
            "beautifully. Still on track for {{deadline}}.\n\n"
            "I'll be back in touch once it's ready for your approval.\n\n"
            "{{artist_name}}\n{{business_name}}"
        ),
    ),
    dict(
        key="ready_for_approval",
        name="5. Ready for your approval",
        subject="Your {{commission_type}} is ready to view!",
        body=(
            "Hi {{client_first_name}},\n\n"
            "Exciting news — your {{commission_type}} is complete! I've attached photos so you can take a "
            "look before it's shipped.\n\n"
            "Please let me know if you're happy with it, or if you'd like any small adjustments.\n\n"
            "Once approved, the final balance of {{balance_amount}} is due before shipping. {{payment_instructions}}\n\n"
            "Looking forward to hearing what you think!\n{{artist_name}}\n{{business_name}}"
        ),
    ),
    dict(
        key="shipped_completed",
        name="6. Shipped / completed",
        subject="Your {{commission_type}} is on its way!",
        body=(
            "Hi {{client_first_name}},\n\n"
            "Your {{commission_type}} has been carefully packaged and posted today via tracked UK delivery.\n\n"
            "It's been an absolute pleasure working on this piece for you — thank you for commissioning me. "
            "I'd love to see a photo once it's up on your wall, and always appreciate a review or a share on "
            "Instagram if you're happy to!\n\n"
            "With thanks,\n{{artist_name}}\n{{business_name}}"
        ),
    ),
    dict(
        key="deadline_reminder",
        name="7. Deadline reminder (to yourself)",
        subject="Reminder: {{commission_type}} for {{client_name}} due {{deadline}}",
        body=(
            "Commission: {{commission_type}} for {{client_name}}\n"
            "Status: {{status}}\n"
            "Deadline: {{deadline}}\n\n"
            "Notes: {{internal_notes}}"
        ),
    ),
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    address TEXT,
    notes TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS commissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    type TEXT NOT NULL,
    size TEXT,
    description TEXT,
    price_pence INTEGER NOT NULL DEFAULT 0,
    deposit_pence INTEGER NOT NULL DEFAULT 0,
    deposit_paid_date TEXT,
    balance_paid_date TEXT,
    status TEXT NOT NULL DEFAULT 'Enquiry',
    deadline TEXT,
    reference_notes TEXT,
    internal_notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    commission_id INTEGER NOT NULL REFERENCES commissions(id) ON DELETE CASCADE,
    invoice_number TEXT UNIQUE NOT NULL,
    kind TEXT NOT NULL,
    amount_pence INTEGER NOT NULL,
    issued_date TEXT NOT NULL,
    due_date TEXT,
    paid_date TEXT,
    status TEXT NOT NULL DEFAULT 'Draft',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS email_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_connection()
    conn.executescript(SCHEMA)
    now = datetime.utcnow().isoformat()

    for k, v in DEFAULT_SETTINGS.items():
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v)
        )

    for tpl in DEFAULT_EMAIL_TEMPLATES:
        conn.execute(
            """INSERT OR IGNORE INTO email_templates (key, name, subject, body, updated_at)
               VALUES (?, ?, ?, ?, ?)""",
            (tpl["key"], tpl["name"], tpl["subject"], tpl["body"], now),
        )

    conn.commit()
    conn.close()


def get_settings(conn):
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    return {r["key"]: r["value"] for r in rows}


def set_setting(conn, key, value):
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    conn.commit()


def next_invoice_number(conn):
    settings = get_settings(conn)
    prefix = settings.get("invoice_prefix", "ESS")
    seq = int(settings.get("next_invoice_seq", "1"))
    year = date.today().year
    number = f"{prefix}-{year}-{seq:03d}"
    set_setting(conn, "next_invoice_seq", str(seq + 1))
    return number
