# Certificate Dispatch Portal

Automated certificate generation and email dispatch for workshop participants.

## Project Structure

```
certificate-dispatch/
├── app.py
├── requirements.txt
├── Procfile
├── render.yaml
├── .gitignore
├── README.md
└── templates/
    └── index.html
```

## Deploy on Render (Free) — Recommended

1. Push this folder to a GitHub repo
2. Go to https://render.com → New → Web Service
3. Connect your GitHub repo
4. Render auto-detects the `render.yaml` — click **Deploy**
5. Your app will be live at `https://your-app.onrender.com`

> ⚠️ Free tier sleeps after 15 min of inactivity. First request after sleep takes ~30s.

---

## Deploy on Railway (Free — $5 credit/month)

1. Push to GitHub
2. Go to https://railway.app → New Project → Deploy from GitHub
3. Select your repo → it auto-detects Python
4. Done — live URL provided instantly

---

## Deploy on Fly.io (Free)

```bash
# Install flyctl
curl -L https://fly.io/install.sh | sh

# Login and launch
fly auth login
fly launch    # follow prompts
fly deploy
```

---

## Run Locally

```bash
pip install -r requirements.txt
python app.py
# Open http://localhost:5000
```

## Gmail Setup

To send emails you need a Gmail **App Password** (not your regular password):
1. Enable 2FA on your Google account
2. Go to https://myaccount.google.com/apppasswords
3. Generate a password for "Mail"
4. Use that 16-character password in the app
