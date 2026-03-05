from flask import Flask, render_template, request, jsonify
import pandas as pd
from reportlab.pdfgen import canvas
from pypdf import PdfReader, PdfWriter
import smtplib, io, time, logging, threading, uuid
from email.message import EmailMessage

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# In-memory job store  {job_id: {"status", "results", "total", "done"}}
jobs = {}


# ── Certificate & email helpers ────────────────────────────────────────────

def create_certificate_bytes(name, template_bytes):
    overlay_buffer = io.BytesIO()
    c = canvas.Canvas(overlay_buffer)
    c.setFont("Helvetica-Bold", 30)
    c.drawCentredString(400, 300, name)
    c.save()
    overlay_buffer.seek(0)

    template = PdfReader(io.BytesIO(template_bytes))
    overlay  = PdfReader(overlay_buffer)
    writer   = PdfWriter()
    page = template.pages[0]
    page.merge_page(overlay.pages[0])
    writer.add_page(page)

    out = io.BytesIO()
    writer.write(out)
    out.seek(0)
    return out.read()


def send_email(sender_email, app_password, receiver_email, name, pdf_bytes, subject):
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

    # Try port 587 (STARTTLS) first — more reliable on cloud hosts
    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(sender_email, app_password)
            smtp.send_message(msg)
    except Exception:
        # Fallback to SSL 465
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
            smtp.login(sender_email, app_password)
            smtp.send_message(msg)


# ── Background worker ──────────────────────────────────────────────────────

def process_job(job_id, rows, template_bytes, sender_email, app_password, subject, name_col):
    job = jobs[job_id]
    job["status"] = "running"

    for _, row in rows.iterrows():
        name  = str(row[name_col]).strip()
        email = str(row["email"]).strip()
        try:
            pdf_bytes = create_certificate_bytes(name, template_bytes)
            send_email(sender_email, app_password, email, name, pdf_bytes, subject)
            job["results"].append({"name": name, "email": email, "status": "sent"})
            logger.info(f"✓ Sent → {name} <{email}>")
        except Exception as e:
            job["results"].append({"name": name, "email": email,
                                   "status": "failed", "error": str(e)})
            logger.error(f"✗ Failed → {name}: {e}")

        job["done"] += 1
        time.sleep(0.8)   # 0.8s gap — safe for Gmail, faster than before

    job["status"] = "complete"
    logger.info(f"Job {job_id} complete — {job['done']}/{job['total']}")


# ── Routes ─────────────────────────────────────────────────────────────────

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/send", methods=["POST"])
def send():
    try:
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

        # Create job and start background thread
        job_id = str(uuid.uuid4())
        jobs[job_id] = {
            "status":  "queued",
            "total":   len(df),
            "done":    0,
            "results": []
        }

        thread = threading.Thread(
            target=process_job,
            args=(job_id, df, template_bytes, sender_email, app_password, subject, name_col),
            daemon=True
        )
        thread.start()

        logger.info(f"Job {job_id} started for {len(df)} recipients")
        return jsonify({"job_id": job_id, "total": len(df)})

    except Exception as e:
        logger.exception(f"Error in /send: {e}")
        return jsonify({"error": f"Server error: {str(e)}"}), 500


@app.route("/status/<job_id>")
def status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify({
        "status":  job["status"],
        "total":   job["total"],
        "done":    job["done"],
        "results": job["results"]
    })


if __name__ == "__main__":
    app.run(debug=True)
