"""
Branded invoice PDF generation using ReportLab.
"""

import io
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas
from reportlab.lib.utils import simpleSplit

FOREST = HexColor("#3F5D48")
FOREST_DARK = HexColor("#2E4636")
CREAM = HexColor("#FAF6EF")
INK = HexColor("#2B2A26")
INK_SOFT = HexColor("#6B6A63")
BORDER = HexColor("#E2DCCC")


def money(pence, symbol="£"):
    return f"{symbol}{pence / 100:,.2f}"


def build_invoice_pdf(invoice, commission, client, settings):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    margin = 20 * mm
    symbol = settings.get("currency_symbol", "£")

    # Header band
    c.setFillColor(FOREST)
    c.rect(0, height - 45 * mm, width, 45 * mm, fill=1, stroke=0)

    c.setFillColor(HexColor("#FFFFFF"))
    c.setFont("Helvetica-Bold", 22)
    c.drawString(margin, height - 22 * mm, settings.get("business_name", "Esther Sims Studio"))
    c.setFont("Helvetica", 10)
    c.drawString(margin, height - 29 * mm, settings.get("business_email", ""))
    c.drawString(margin, height - 34 * mm, settings.get("business_location", ""))
    c.drawString(margin, height - 39 * mm, settings.get("website_url", ""))

    c.setFont("Helvetica-Bold", 18)
    c.drawRightString(width - margin, height - 22 * mm, "INVOICE")
    c.setFont("Helvetica", 11)
    c.drawRightString(width - margin, height - 29 * mm, invoice["invoice_number"])
    c.setFont("Helvetica", 9)
    c.drawRightString(width - margin, height - 35 * mm, f"Issued: {invoice['issued_date']}")
    if invoice["due_date"]:
        c.drawRightString(width - margin, height - 40 * mm, f"Due: {invoice['due_date']}")

    y = height - 60 * mm

    # Bill to
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(margin, y, "Billed to")
    y -= 6 * mm
    c.setFont("Helvetica", 10)
    c.drawString(margin, y, client["name"] or "")
    if client["email"]:
        y -= 5 * mm
        c.drawString(margin, y, client["email"])
    if client["address"]:
        y -= 5 * mm
        for line in simpleSplit(client["address"], "Helvetica", 10, 80 * mm):
            c.drawString(margin, y, line)
            y -= 5 * mm

    # Commission summary box (right column)
    box_x = width / 2 + 5 * mm
    box_y = height - 66 * mm
    c.setFillColor(INK_SOFT)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(box_x, box_y, "Commission")
    c.setFont("Helvetica", 10)
    c.setFillColor(INK)
    c.drawString(box_x, box_y - 6 * mm, commission["type"] or "")
    if commission["size"]:
        c.drawString(box_x, box_y - 11 * mm, f"Size: {commission['size']}")

    y = min(y, box_y - 11 * mm) - 15 * mm

    # Line items table header
    table_top = y
    c.setFillColor(FOREST)
    c.rect(margin, table_top, width - 2 * margin, 9 * mm, fill=1, stroke=0)
    c.setFillColor(HexColor("#FFFFFF"))
    c.setFont("Helvetica-Bold", 10)
    c.drawString(margin + 3 * mm, table_top + 3 * mm, "Description")
    c.drawRightString(width - margin - 3 * mm, table_top + 3 * mm, "Amount")

    row_y = table_top - 10 * mm
    c.setFillColor(INK)
    c.setFont("Helvetica", 10)
    desc = f"{commission['type']} — {invoice['kind']}"
    for line in simpleSplit(desc, "Helvetica", 10, width - 2 * margin - 40 * mm):
        c.drawString(margin + 3 * mm, row_y, line)
        row_y -= 5 * mm
    c.drawRightString(width - margin - 3 * mm, table_top - 10 * mm, money(invoice["amount_pence"], symbol))

    c.setStrokeColor(BORDER)
    c.line(margin, row_y - 3 * mm, width - margin, row_y - 3 * mm)

    total_y = row_y - 14 * mm
    c.setFont("Helvetica-Bold", 13)
    c.setFillColor(FOREST_DARK)
    c.drawRightString(width - margin - 3 * mm, total_y, f"Total due: {money(invoice['amount_pence'], symbol)}")

    # Payment instructions
    pay_y = total_y - 18 * mm
    c.setFillColor(INK_SOFT)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(margin, pay_y, "Payment instructions")
    c.setFont("Helvetica", 9.5)
    c.setFillColor(INK)
    pay_y -= 5.5 * mm
    for line in simpleSplit(settings.get("payment_instructions", ""), "Helvetica", 9.5, width - 2 * margin):
        c.drawString(margin, pay_y, line)
        pay_y -= 5 * mm

    # Footer
    c.setFillColor(INK_SOFT)
    c.setFont("Helvetica-Oblique", 9)
    c.drawCentredString(width / 2, 15 * mm, "Thank you for commissioning original artwork — it means a great deal.")

    c.showPage()
    c.save()
    buf.seek(0)
    return buf
