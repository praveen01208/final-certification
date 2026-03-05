from flask import Flask, render_template, request, jsonify
import pandas as pd
from reportlab.pdfgen import canvas
from pypdf import PdfReader, PdfWriter
import io, time, logging, threading, uuid, base64, requests, os

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)

jobs = {}

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


# ── Certificate generation (fully in-memory) ───────────────────────────────

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


# ── Brevo via direct HTTPS REST call (no SDK) ──────────────────────────────

def send_email_brevo(api_key, sender_email, sender_name,
                     receiver_email, name, pdf_bytes, subject):

    pdf_b64 = base64.b64encode(pdf_bytes).decode("utf-8")

    payload = {
        "sender": {"email": sender_email, "name": sender_name},
        "to": [{"email": receiver_email, "name": name}],
        "subject": subject,
        "textContent": f"""Hello {name},

Thank you for attending the ReactCloud Sprint Workshop.
Please find your certificate of participation attached.

Best Regards,
C-TEC Event Team
KLE College of Engineering and Technology""",
        "attachment": [{"content": pdf_b64, "name": "certificate.pdf"}]
    }

    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "api-key": api_key
    }

    response = requests.post(BREVO_API_URL, json=payload,
                             headers=headers, timeout=30)

    if response.status_code not in (200, 201):
        raise Exception(f"Brevo {response.status_code}: {response.text}")


# ── Background worker ──────────────────────────────────────────────────────

def process_job(job_id, rows, template_bytes,
                api_key, sender_email, sender_name,
                subject, name_col):

    job = jobs[job_id]
    job["status"] = "running"

    for _, row in rows.iterrows():
        name  = str(row[name_col]).strip()
        email = str(row["email"]).strip()
        try:
            pdf_bytes = create_certificate_bytes(name, template_bytes)
            send_email_brevo(api_key, sender_email, sender_name,
                             email, name, pdf_bytes, subject)
            job["results"].append({"name": name, "email": email, "status": "sent"})
            logger.info(f"✓ Sent → {name} <{email}>")
        except Exception as e:
            job["results"].append({"name": name, "email": email,
                                   "status": "failed", "error": str(e)})
            logger.error(f"✗ {name}: {e}")

        job["done"] += 1
        time.sleep(0.3)

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
        pdf_tpl      = request.files.get("pdf_template")
        api_key      = request.form.get("api_key", "").strip() or os.environ.get("BREVO_API_KEY", "")
        sender_email = request.form.get("sender_email", "").strip()
        sender_name  = request.form.get("sender_name", "C-TEC Team").strip()
        subject      = request.form.get("subject", "Your Certificate").strip()
        name_col     = request.form.get("name_col", "name").strip()

        if not csv_file or not pdf_tpl:
            return jsonify({"error": "Both CSV and PDF template are required."}), 400
        if not api_key or not sender_email:
            return jsonify({"error": "Brevo API key and sender email are required."}), 400

        template_bytes = pdf_tpl.read()

        try:
            df = pd.read_csv(csv_file)
        except Exception as e:
            return jsonify({"error": f"Could not parse CSV: {str(e)}"}), 400

        if name_col not in df.columns or "email" not in df.columns:
            return jsonify({
                "error": f"CSV must have '{name_col}' and 'email' columns. "
                         f"Found: {list(df.columns)}"
            }), 400

        job_id = str(uuid.uuid4())
        jobs[job_id] = {"status": "queued", "total": len(df), "done": 0, "results": []}

        threading.Thread(
            target=process_job,
            args=(job_id, df, template_bytes,
                  api_key, sender_email, sender_name,
                  subject, name_col),
            daemon=True
        ).start()

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
