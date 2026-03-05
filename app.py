from flask import Flask, render_template, request, jsonify
import pandas as pd
from reportlab.pdfgen import canvas
from PyPDF2 import PdfReader, PdfWriter
import smtplib, io, time
from email.message import EmailMessage

app = Flask(__name__)


def create_certificate_bytes(name, template_bytes):
    """Generate a certificate PDF entirely in memory — no disk I/O."""

    # 1. Draw the name overlay on a blank canvas -> in-memory buffer
    overlay_buffer = io.BytesIO()
    c = canvas.Canvas(overlay_buffer)
    c.setFont("Helvetica-Bold", 30)
    c.drawCentredString(400, 300, name)   # <- adjust x,y to match your template
    c.save()
    overlay_buffer.seek(0)

    # 2. Merge overlay onto template
    template = PdfReader(io.BytesIO(template_bytes))
    overlay  = PdfReader(overlay_buffer)
    writer   = PdfWriter()

    page = template.pages[0]
    page.merge_page(overlay.pages[0])
    writer.add_page(page)

    # 3. Write merged PDF to another in-memory buffer
    output_buffer = io.BytesIO()
    writer.write(output_buffer)
    output_buffer.seek(0)
    return output_buffer.read()


def send_email(sender_email, app_password, receiver_email, name, pdf_bytes, subject):
    """Email a certificate PDF (bytes) to the recipient."""
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"]    = sender_email
    msg["To"]      = receiver_email

    msg.set_content(f"""Hello {name},

Thank you for attending the ReactCloud Sprint Workshop.

Please find your certificate of participation attached.

Best Regards,
C-TEC Event Team
KLE College of Engineering and Technology""")

    msg.add_attachment(pdf_bytes, maintype="application",
                       subtype="pdf", filename="certificate.pdf")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(sender_email, app_password)
        smtp.send_message(msg)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/send", methods=["POST"])
def send():
    csv_file     = request.files.get("csv_file")
    pdf_template = request.files.get("pdf_template")
    sender_email = request.form.get("sender_email", "").strip()
    app_password = request.form.get("app_password", "").strip()
    subject      = request.form.get("subject", "Your Certificate").strip()
    name_col     = request.form.get("name_col", "name").strip()

    if not csv_file or not pdf_template:
        return jsonify({"error": "Both CSV and PDF template are required."}), 400
    if not sender_email or not app_password:
        return jsonify({"error": "Sender email and app password are required."}), 400

    template_bytes = pdf_template.read()

    try:
        df = pd.read_csv(csv_file)
    except Exception as e:
        return jsonify({"error": f"Could not parse CSV: {str(e)}"}), 400

    if name_col not in df.columns or "email" not in df.columns:
        return jsonify({
            "error": f"CSV must have '{name_col}' and 'email' columns. "
                     f"Found: {list(df.columns)}"
        }), 400

    results = []

    for _, row in df.iterrows():
        name  = str(row[name_col]).strip()
        email = str(row["email"]).strip()

        try:
            pdf_bytes = create_certificate_bytes(name, template_bytes)
            send_email(sender_email, app_password, email, name, pdf_bytes, subject)
            results.append({"name": name, "email": email, "status": "sent"})
        except Exception as e:
            results.append({"name": name, "email": email,
                            "status": "failed", "error": str(e)})

        time.sleep(1.5)

    return jsonify({"results": results})


if __name__ == "__main__":
    app.run(debug=True)
