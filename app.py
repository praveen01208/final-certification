from flask import Flask, render_template, request, jsonify
import pandas as pd
from reportlab.pdfgen import canvas
from PyPDF2 import PdfReader, PdfWriter
import os, time, smtplib, io
from email.message import EmailMessage
from werkzeug.utils import secure_filename

app = Flask(__name__)

OUTPUT_FOLDER = "generated"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)


def create_certificate(name, template_bytes, output_path):
    """Overlay the participant name onto the PDF template."""
    packet_path = f"temp_{secure_filename(name)}.pdf"

    c = canvas.Canvas(packet_path)
    c.setFont("Helvetica-Bold", 30)
    # Adjust x, y to match your template's <<Name>> position
    c.drawCentredString(400, 300, name)
    c.save()

    template = PdfReader(io.BytesIO(template_bytes))
    overlay  = PdfReader(packet_path)
    writer   = PdfWriter()

    page = template.pages[0]
    page.merge_page(overlay.pages[0])
    writer.add_page(page)

    with open(output_path, "wb") as f:
        writer.write(f)

    os.remove(packet_path)


def send_email(sender_email, app_password, receiver_email, name, file_path, subject):
    """Send a certificate PDF to a single recipient."""
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

    with open(file_path, "rb") as f:
        msg.add_attachment(f.read(), maintype="application",
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
        return jsonify({"error": f"Could not parse CSV: {e}"}), 400

    if name_col not in df.columns or "email" not in df.columns:
        return jsonify({"error": f"CSV must have '{name_col}' and 'email' columns."}), 400

    results = []

    for _, row in df.iterrows():
        name  = str(row[name_col]).strip()
        email = str(row["email"]).strip()
        output_path = os.path.join(OUTPUT_FOLDER, f"{secure_filename(name)}.pdf")

        try:
            create_certificate(name, template_bytes, output_path)
            send_email(sender_email, app_password, email, name,
                       output_path, subject)
            results.append({"name": name, "email": email, "status": "sent"})
        except Exception as e:
            results.append({"name": name, "email": email,
                            "status": "failed", "error": str(e)})

        time.sleep(1.5)  # stay within Gmail rate limits

    return jsonify({"results": results})


if __name__ == "__main__":
    app.run(debug=True)
