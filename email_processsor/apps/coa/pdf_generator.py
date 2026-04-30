from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
import tempfile
import os
from reportlab.lib.enums import TA_CENTER
import uuid


def generate_pdf(data):
    file_path = os.path.join(tempfile.gettempdir(), f"coa_{uuid.uuid4().hex[:8]}.pdf")

    doc = SimpleDocTemplate(file_path, pagesize=letter,
                            leftMargin=0.75*inch, rightMargin=0.75*inch,
                            topMargin=0.75*inch, bottomMargin=0.75*inch)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("title", parent=styles["Heading1"], alignment=TA_CENTER, fontSize=16)
    section_style = ParagraphStyle("section", parent=styles["Heading2"], fontSize=11, textColor=colors.darkblue)
    normal = styles["Normal"]

    elements = []

    # Title
    elements.append(Paragraph("Certificate of Analysis", title_style))
    elements.append(Spacer(1, 0.2*inch))

    # Company info
    elements.append(Paragraph("Supplier Information", section_style))
    company_data = [
        ["Company", data.get("company", "")],
        ["Address", data.get("address", "")],
        ["Phone", data.get("contact_phone", "")],
        ["Email", data.get("contact_email", "")],
    ]
    company_table = Table(company_data, colWidths=[1.5*inch, 5.5*inch])
    company_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    elements.append(company_table)
    elements.append(Spacer(1, 0.2*inch))

    # Product & lot details
    elements.append(Paragraph("Product & Lot Details", section_style))
    product_data = [
        ["Product Name", data.get("product_name", "")],
        ["Part Number", data.get("part_number", "")],
        ["Lot Number", data.get("lot_number", "")],
        ["Lot Quantity", data.get("lot_quantity", "")],
        ["Manufacture Date", data.get("manufacture_date", "")],
        ["Expiration Date", data.get("expiration_date", "")],
        ["Report Date", data.get("report_date", "")],
    ]
    product_table = Table(product_data, colWidths=[1.5*inch, 5.5*inch])
    product_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(product_table)
    elements.append(Spacer(1, 0.2*inch))

    # Test results table
    elements.append(Paragraph("Test Results", section_style))
    test_rows = [["Test", "Specification", "Result", "Method"]]
    for t in data.get("test_results", []):
        test_rows.append([
            t.get("test", ""),
            t.get("specification", ""),
            t.get("result", ""),
            t.get("method", ""),
        ])

    test_table = Table(test_rows, colWidths=[1.6*inch, 1.5*inch, 1.3*inch, 2.6*inch])
    test_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.darkblue),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    elements.append(test_table)
    elements.append(Spacer(1, 0.3*inch))

    # Approved by
    elements.append(Paragraph(f"Approved by: <b>{data.get('approved_by', '')}</b>", normal))

    doc.build(elements)
    return file_path
