"""
Esther Sims Studio — commission, invoicing & client-communication admin tool.

A small single-tenant Flask app: no signup flow beyond a one-time first-run
setup, session-based login, Postgres storage, ReportLab-generated PDF invoices,
and a library of editable email templates with merge-field substitution.
"""

import os
import re
import secrets
from datetime import datetime, date, timedelta
from functools import wraps

from dotenv import load_dotenv
from flask import (
    Flask, g, render_template, request, redirect, url_for, session,
    flash, send_file, abort
)
from werkzeug.security import generate_password_hash, check_password_hash

import db
from pdf import build_invoice_pdf

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))

db.init_db()


# ---------------------------------------------------------------- helpers --

def get_db():
    if "db" not in g:
        g.db = db.get_connection()
    return g.db


@app.teardown_appcontext
def close_db(exc):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def current_user():
    if "user_id" not in session:
        return None
    return get_db().execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


@app.before_request
def require_setup():
    # Force first-run setup if there's no user yet, except for the setup route itself
    if request.endpoint in ("setup", "static"):
        return
    has_user = get_db().execute("SELECT 1 FROM users LIMIT 1").fetchone()
    if not has_user:
        return redirect(url_for("setup"))


@app.context_processor
def inject_globals():
    conn = get_db()
    return dict(
        settings=db.get_settings(conn),
        current_user=current_user(),
        commission_statuses=db.COMMISSION_STATUSES,
        commission_types=db.COMMISSION_TYPES,
        today=date.today().isoformat(),
    )


@app.template_filter("money")
def money_filter(pence):
    settings = db.get_settings(get_db())
    symbol = settings.get("currency_symbol", "£")
    try:
        return f"{symbol}{(pence or 0) / 100:,.2f}"
    except (TypeError, ValueError):
        return f"{symbol}0.00"


@app.template_filter("prettydate")
def prettydate_filter(value):
    if not value:
        return ""
    try:
        d = datetime.strptime(value, "%Y-%m-%d").date()
        return d.strftime("%-d %b %Y")
    except ValueError:
        return value


def parse_money_to_pence(raw):
    if not raw:
        return 0
    cleaned = re.sub(r"[^0-9.]", "", str(raw))
    if not cleaned:
        return 0
    return round(float(cleaned) * 100)


def days_until(iso_date):
    if not iso_date:
        return None
    try:
        d = datetime.strptime(iso_date, "%Y-%m-%d").date()
    except ValueError:
        return None
    return (d - date.today()).days


app.jinja_env.filters["days_until"] = days_until


# ------------------------------------------------------------------ setup --

@app.route("/setup", methods=["GET", "POST"])
def setup():
    conn = get_db()
    has_user = conn.execute("SELECT 1 FROM users LIMIT 1").fetchone()
    if has_user:
        return redirect(url_for("login"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        if not name or not email or not password:
            flash("Please fill in every field.", "error")
        elif password != confirm:
            flash("Passwords don't match.", "error")
        elif len(password) < 8:
            flash("Password should be at least 8 characters.", "error")
        else:
            conn.execute(
                "INSERT INTO users (email, name, password_hash, created_at) VALUES (?, ?, ?, ?)",
                (email, name, generate_password_hash(password, method="pbkdf2:sha256"), datetime.utcnow().isoformat()),
            )
            conn.commit()
            flash("Account created — welcome!", "success")
            return redirect(url_for("login"))

    return render_template("setup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user():
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = get_db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session.permanent = True
            return redirect(request.args.get("next") or url_for("dashboard"))
        flash("Incorrect email or password.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if current_user():
        return redirect(url_for("dashboard"))

    recovery_code = os.environ.get("RECOVERY_CODE", "")

    if request.method == "POST":
        if not recovery_code:
            flash(
                "Password recovery isn't set up yet — RECOVERY_CODE needs to be "
                "configured on the server.",
                "error",
            )
            return render_template("forgot_password.html")

        submitted_code = request.form.get("recovery_code", "")
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        if not secrets.compare_digest(submitted_code, recovery_code):
            flash("Recovery code is incorrect.", "error")
        elif not email or not password:
            flash("Please fill in every field.", "error")
        elif password != confirm:
            flash("Passwords don't match.", "error")
        elif len(password) < 8:
            flash("Password should be at least 8 characters.", "error")
        else:
            conn = get_db()
            user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            if user:
                conn.execute(
                    "UPDATE users SET password_hash = ? WHERE id = ?",
                    (generate_password_hash(password, method="pbkdf2:sha256"), user["id"]),
                )
                conn.commit()
            flash("If that email matches an account, its password has been reset. You can log in now.", "success")
            return redirect(url_for("login"))

    return render_template("forgot_password.html")


# -------------------------------------------------------------- dashboard --

@app.route("/")
@login_required
def dashboard():
    conn = get_db()
    upcoming = conn.execute(
        """SELECT c.*, cl.name AS client_name FROM commissions c
           JOIN clients cl ON cl.id = c.client_id
           WHERE c.deadline IS NOT NULL AND c.deadline != ''
             AND c.status NOT IN ('Completed', 'Cancelled')
           ORDER BY c.deadline ASC"""
    ).fetchall()

    status_counts = conn.execute(
        "SELECT status, COUNT(*) AS n FROM commissions GROUP BY status"
    ).fetchall()

    outstanding_invoices = conn.execute(
        """SELECT i.*, c.type AS commission_type, cl.name AS client_name
           FROM invoices i
           JOIN commissions c ON c.id = i.commission_id
           JOIN clients cl ON cl.id = c.client_id
           WHERE i.status IN ('Draft', 'Sent', 'Overdue')
           ORDER BY i.due_date ASC"""
    ).fetchall()

    active_count = conn.execute(
        "SELECT COUNT(*) AS n FROM commissions WHERE status IN ({})".format(
            ",".join("?" for _ in db.ACTIVE_STATUSES)
        ),
        db.ACTIVE_STATUSES,
    ).fetchone()["n"]

    return render_template(
        "dashboard.html",
        upcoming=upcoming,
        status_counts=status_counts,
        outstanding_invoices=outstanding_invoices,
        active_count=active_count,
    )


# ----------------------------------------------------------------- clients --

@app.route("/clients")
@login_required
def clients_list():
    conn = get_db()
    q = request.args.get("q", "").strip()
    if q:
        rows = conn.execute(
            "SELECT * FROM clients WHERE name LIKE ? OR email LIKE ? ORDER BY name",
            (f"%{q}%", f"%{q}%"),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM clients ORDER BY name").fetchall()
    return render_template("clients_list.html", clients=rows, q=q)


@app.route("/clients/new", methods=["GET", "POST"])
@login_required
def client_new():
    if request.method == "POST":
        conn = get_db()
        cur = conn.execute(
            "INSERT INTO clients (name, email, phone, address, notes, created_at) VALUES (?, ?, ?, ?, ?, ?) RETURNING id",
            (
                request.form.get("name", "").strip(),
                request.form.get("email", "").strip(),
                request.form.get("phone", "").strip(),
                request.form.get("address", "").strip(),
                request.form.get("notes", "").strip(),
                datetime.utcnow().isoformat(),
            ),
        )
        client_id = cur.fetchone()["id"]
        conn.commit()
        flash("Client added.", "success")
        return redirect(url_for("client_detail", client_id=client_id))
    return render_template("client_form.html", client=None)


@app.route("/clients/<int:client_id>")
@login_required
def client_detail(client_id):
    conn = get_db()
    client = conn.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
    if not client:
        abort(404)
    commissions = conn.execute(
        "SELECT * FROM commissions WHERE client_id = ? ORDER BY created_at DESC", (client_id,)
    ).fetchall()
    return render_template("client_detail.html", client=client, commissions=commissions)


@app.route("/clients/<int:client_id>/edit", methods=["GET", "POST"])
@login_required
def client_edit(client_id):
    conn = get_db()
    client = conn.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
    if not client:
        abort(404)
    if request.method == "POST":
        conn.execute(
            "UPDATE clients SET name=?, email=?, phone=?, address=?, notes=? WHERE id=?",
            (
                request.form.get("name", "").strip(),
                request.form.get("email", "").strip(),
                request.form.get("phone", "").strip(),
                request.form.get("address", "").strip(),
                request.form.get("notes", "").strip(),
                client_id,
            ),
        )
        conn.commit()
        flash("Client updated.", "success")
        return redirect(url_for("client_detail", client_id=client_id))
    return render_template("client_form.html", client=client)


@app.route("/clients/<int:client_id>/delete", methods=["POST"])
@login_required
def client_delete(client_id):
    conn = get_db()
    conn.execute("DELETE FROM clients WHERE id = ?", (client_id,))
    conn.commit()
    flash("Client removed.", "success")
    return redirect(url_for("clients_list"))


# ------------------------------------------------------------- commissions --

@app.route("/commissions")
@login_required
def commissions_list():
    conn = get_db()
    status = request.args.get("status", "")
    base_q = """SELECT c.*, cl.name AS client_name FROM commissions c
                JOIN clients cl ON cl.id = c.client_id"""
    if status:
        rows = conn.execute(base_q + " WHERE c.status = ? ORDER BY c.deadline IS NULL, c.deadline ASC", (status,)).fetchall()
    else:
        rows = conn.execute(base_q + " ORDER BY c.deadline IS NULL, c.deadline ASC").fetchall()
    return render_template("commissions_list.html", commissions=rows, status=status)


@app.route("/commissions/new", methods=["GET", "POST"])
@login_required
def commission_new():
    conn = get_db()
    if request.method == "POST":
        client_id = request.form.get("client_id")
        if request.form.get("new_client_name"):
            cur = conn.execute(
                "INSERT INTO clients (name, email, phone, address, notes, created_at) VALUES (?, ?, ?, ?, '', ?) RETURNING id",
                (
                    request.form.get("new_client_name", "").strip(),
                    request.form.get("new_client_email", "").strip(),
                    request.form.get("new_client_phone", "").strip(),
                    request.form.get("new_client_address", "").strip(),
                    datetime.utcnow().isoformat(),
                ),
            )
            client_id = cur.fetchone()["id"]

        now = datetime.utcnow().isoformat()
        price_pence = parse_money_to_pence(request.form.get("price"))
        deposit_pence = parse_money_to_pence(request.form.get("deposit"))
        cur = conn.execute(
            """INSERT INTO commissions
               (client_id, type, size, description, price_pence, deposit_pence, status,
                deadline, reference_notes, internal_notes, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id""",
            (
                client_id,
                request.form.get("type"),
                request.form.get("size", "").strip(),
                request.form.get("description", "").strip(),
                price_pence,
                deposit_pence,
                request.form.get("status") or "Enquiry",
                request.form.get("deadline") or None,
                request.form.get("reference_notes", "").strip(),
                request.form.get("internal_notes", "").strip(),
                now, now,
            ),
        )
        commission_id = cur.fetchone()["id"]
        conn.commit()
        flash("Commission created.", "success")
        return redirect(url_for("commission_detail", commission_id=commission_id))

    clients = conn.execute("SELECT * FROM clients ORDER BY name").fetchall()
    preselect_client = request.args.get("client_id", type=int)
    return render_template("commission_form.html", commission=None, clients=clients, preselect_client=preselect_client)


@app.route("/commissions/<int:commission_id>")
@login_required
def commission_detail(commission_id):
    conn = get_db()
    commission = conn.execute("SELECT * FROM commissions WHERE id = ?", (commission_id,)).fetchone()
    if not commission:
        abort(404)
    client = conn.execute("SELECT * FROM clients WHERE id = ?", (commission["client_id"],)).fetchone()
    invoices = conn.execute(
        "SELECT * FROM invoices WHERE commission_id = ? ORDER BY created_at DESC", (commission_id,)
    ).fetchall()
    templates = conn.execute("SELECT key, name FROM email_templates ORDER BY id").fetchall()
    return render_template(
        "commission_detail.html", commission=commission, client=client, invoices=invoices, templates=templates
    )


@app.route("/commissions/<int:commission_id>/edit", methods=["GET", "POST"])
@login_required
def commission_edit(commission_id):
    conn = get_db()
    commission = conn.execute("SELECT * FROM commissions WHERE id = ?", (commission_id,)).fetchone()
    if not commission:
        abort(404)
    if request.method == "POST":
        price_pence = parse_money_to_pence(request.form.get("price"))
        deposit_pence = parse_money_to_pence(request.form.get("deposit"))
        conn.execute(
            """UPDATE commissions SET type=?, size=?, description=?, price_pence=?, deposit_pence=?,
               status=?, deadline=?, reference_notes=?, internal_notes=?, updated_at=? WHERE id=?""",
            (
                request.form.get("type"),
                request.form.get("size", "").strip(),
                request.form.get("description", "").strip(),
                price_pence,
                deposit_pence,
                request.form.get("status"),
                request.form.get("deadline") or None,
                request.form.get("reference_notes", "").strip(),
                request.form.get("internal_notes", "").strip(),
                datetime.utcnow().isoformat(),
                commission_id,
            ),
        )
        conn.commit()
        flash("Commission updated.", "success")
        return redirect(url_for("commission_detail", commission_id=commission_id))

    clients = conn.execute("SELECT * FROM clients ORDER BY name").fetchall()
    return render_template("commission_form.html", commission=commission, clients=clients, preselect_client=None)


@app.route("/commissions/<int:commission_id>/status", methods=["POST"])
@login_required
def commission_status(commission_id):
    conn = get_db()
    new_status = request.form.get("status")
    updates = {"status": new_status, "updated_at": datetime.utcnow().isoformat()}
    if new_status == "Confirmed":
        commission = conn.execute("SELECT deposit_paid_date FROM commissions WHERE id=?", (commission_id,)).fetchone()
        if commission and not commission["deposit_paid_date"]:
            updates["deposit_paid_date"] = date.today().isoformat()
    set_clause = ", ".join(f"{k}=?" for k in updates)
    conn.execute(f"UPDATE commissions SET {set_clause} WHERE id=?", (*updates.values(), commission_id))
    conn.commit()
    flash(f"Status updated to “{new_status}”.", "success")
    return redirect(url_for("commission_detail", commission_id=commission_id))


@app.route("/commissions/<int:commission_id>/delete", methods=["POST"])
@login_required
def commission_delete(commission_id):
    conn = get_db()
    conn.execute("DELETE FROM commissions WHERE id = ?", (commission_id,))
    conn.commit()
    flash("Commission deleted.", "success")
    return redirect(url_for("commissions_list"))


# ---------------------------------------------------------------- invoices --

@app.route("/invoices")
@login_required
def invoices_list():
    conn = get_db()
    rows = conn.execute(
        """SELECT i.*, c.type AS commission_type, cl.name AS client_name, cl.id AS client_id
           FROM invoices i
           JOIN commissions c ON c.id = i.commission_id
           JOIN clients cl ON cl.id = c.client_id
           ORDER BY i.issued_date DESC"""
    ).fetchall()
    return render_template("invoices_list.html", invoices=rows)


@app.route("/commissions/<int:commission_id>/invoices/new", methods=["GET", "POST"])
@login_required
def invoice_new(commission_id):
    conn = get_db()
    commission = conn.execute("SELECT * FROM commissions WHERE id = ?", (commission_id,)).fetchone()
    if not commission:
        abort(404)

    if request.method == "POST":
        kind = request.form.get("kind")
        amount_pence = parse_money_to_pence(request.form.get("amount"))
        invoice_number = db.next_invoice_number(conn)
        conn.execute(
            """INSERT INTO invoices (commission_id, invoice_number, kind, amount_pence, issued_date, due_date, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, 'Draft', ?)""",
            (
                commission_id, invoice_number, kind, amount_pence,
                request.form.get("issued_date") or date.today().isoformat(),
                request.form.get("due_date") or None,
                datetime.utcnow().isoformat(),
            ),
        )
        conn.commit()
        flash(f"Invoice {invoice_number} created.", "success")
        return redirect(url_for("commission_detail", commission_id=commission_id))

    default_kind = "Deposit" if not commission["deposit_paid_date"] else "Balance"
    default_amount = commission["deposit_pence"] if default_kind == "Deposit" else (
        commission["price_pence"] - commission["deposit_pence"]
    )
    return render_template(
        "invoice_form.html", commission=commission, default_kind=default_kind, default_amount=default_amount
    )


@app.route("/invoices/<int:invoice_id>")
@login_required
def invoice_detail(invoice_id):
    conn = get_db()
    invoice = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
    if not invoice:
        abort(404)
    commission = conn.execute("SELECT * FROM commissions WHERE id = ?", (invoice["commission_id"],)).fetchone()
    client = conn.execute("SELECT * FROM clients WHERE id = ?", (commission["client_id"],)).fetchone()
    return render_template("invoice_detail.html", invoice=invoice, commission=commission, client=client)


@app.route("/invoices/<int:invoice_id>/pdf")
@login_required
def invoice_pdf(invoice_id):
    conn = get_db()
    invoice = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
    if not invoice:
        abort(404)
    commission = conn.execute("SELECT * FROM commissions WHERE id = ?", (invoice["commission_id"],)).fetchone()
    client = conn.execute("SELECT * FROM clients WHERE id = ?", (commission["client_id"],)).fetchone()
    settings = db.get_settings(conn)
    buf = build_invoice_pdf(invoice, commission, client, settings)
    return send_file(
        buf, mimetype="application/pdf", as_attachment=True,
        download_name=f"{invoice['invoice_number']}.pdf",
    )


@app.route("/invoices/<int:invoice_id>/status", methods=["POST"])
@login_required
def invoice_status(invoice_id):
    conn = get_db()
    new_status = request.form.get("status")
    paid_date = date.today().isoformat() if new_status == "Paid" else None
    conn.execute(
        "UPDATE invoices SET status=?, paid_date=COALESCE(?, paid_date) WHERE id=?",
        (new_status, paid_date, invoice_id),
    )
    conn.commit()

    if new_status == "Paid":
        invoice = conn.execute("SELECT * FROM invoices WHERE id=?", (invoice_id,)).fetchone()
        if invoice["kind"] == "Deposit":
            conn.execute("UPDATE commissions SET deposit_paid_date=? WHERE id=?", (paid_date, invoice["commission_id"]))
        elif invoice["kind"] in ("Balance", "Full Payment"):
            conn.execute("UPDATE commissions SET balance_paid_date=? WHERE id=?", (paid_date, invoice["commission_id"]))
        conn.commit()

    flash(f"Invoice marked {new_status}.", "success")
    return redirect(request.referrer or url_for("invoices_list"))


# --------------------------------------------------------- email templates --

def merge_fields(text, commission, client, settings):
    price = money_filter(commission["price_pence"]) if commission else ""
    deposit = money_filter(commission["deposit_pence"]) if commission else ""
    balance = money_filter((commission["price_pence"] or 0) - (commission["deposit_pence"] or 0)) if commission else ""
    deposit_percent = "0"
    if commission and commission["price_pence"]:
        deposit_percent = str(round((commission["deposit_pence"] or 0) / commission["price_pence"] * 100))

    first_name = (client["name"].split()[0] if client and client["name"] else "") if client else ""

    replacements = {
        "business_name": settings.get("business_name", ""),
        "artist_name": settings.get("business_name", "").replace(" Studio", ""),
        "client_name": client["name"] if client else "",
        "client_first_name": first_name,
        "commission_type": commission["type"] if commission else "",
        "size": commission["size"] if commission else "",
        "price": price,
        "deposit_amount": deposit,
        "balance_amount": balance,
        "deposit_percent": deposit_percent,
        "deadline": prettydate_filter(commission["deadline"]) if commission and commission["deadline"] else "TBC",
        "status": commission["status"] if commission else "",
        "internal_notes": (commission["internal_notes"] if commission else "") or "",
        "payment_instructions": settings.get("payment_instructions", ""),
    }
    for k, v in replacements.items():
        text = text.replace("{{" + k + "}}", v or "")
    return text


@app.route("/emails")
@login_required
def emails_list():
    conn = get_db()
    templates = conn.execute("SELECT * FROM email_templates ORDER BY id").fetchall()
    return render_template("emails_list.html", templates=templates)


@app.route("/emails/<key>/edit", methods=["GET", "POST"])
@login_required
def email_template_edit(key):
    conn = get_db()
    tpl = conn.execute("SELECT * FROM email_templates WHERE key = ?", (key,)).fetchone()
    if not tpl:
        abort(404)
    if request.method == "POST":
        conn.execute(
            "UPDATE email_templates SET name=?, subject=?, body=?, updated_at=? WHERE key=?",
            (
                request.form.get("name", "").strip(),
                request.form.get("subject", "").strip(),
                request.form.get("body", ""),
                datetime.utcnow().isoformat(),
                key,
            ),
        )
        conn.commit()
        flash("Template saved.", "success")
        return redirect(url_for("emails_list"))
    return render_template("email_template_form.html", tpl=tpl)


@app.route("/commissions/<int:commission_id>/emails/<key>")
@login_required
def email_compose(commission_id, key):
    conn = get_db()
    commission = conn.execute("SELECT * FROM commissions WHERE id = ?", (commission_id,)).fetchone()
    if not commission:
        abort(404)
    client = conn.execute("SELECT * FROM clients WHERE id = ?", (commission["client_id"],)).fetchone()
    tpl = conn.execute("SELECT * FROM email_templates WHERE key = ?", (key,)).fetchone()
    if not tpl:
        abort(404)
    settings = db.get_settings(conn)
    subject = merge_fields(tpl["subject"], commission, client, settings)
    body = merge_fields(tpl["body"], commission, client, settings)
    return render_template(
        "email_compose.html", commission=commission, client=client, tpl=tpl, subject=subject, body=body
    )


# ---------------------------------------------------------------- settings --

@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings_page():
    conn = get_db()
    if request.method == "POST":
        for key in (
            "business_name", "business_email", "business_location", "invoice_prefix",
            "default_deposit_percent", "currency_symbol", "payment_instructions", "website_url",
        ):
            if key in request.form:
                db.set_setting(conn, key, request.form.get(key, "").strip())
        flash("Settings saved.", "success")
        return redirect(url_for("settings_page"))
    return render_template("settings.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG") == "1")