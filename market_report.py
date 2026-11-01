import os
import smtplib
import feedparser
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from groq import Groq

# 1. RSS-Feeds abrufen
FEEDS = [
    "https://feeds.marketwatch.com/marketwatch/topstories",
    "https://www.investing.com/rss/news_25.rss",
    "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "http://feeds.bbci.co.uk/news/business/rss.xml"
]

collected_news = []
for feed_url in FEEDS:
    feed = feedparser.parse(feed_url)
    for entry in feed.entries[:6]:  # Die Top 6 je Quelle
        summary = entry.get('summary', '') or entry.get('description', '')
        collected_news.append(f"- {entry.title}: {summary}")

raw_text = "\n".join(collected_news)

# 2. Verbindung zu Groq & Live-Erkennung aktiver Modelle
api_key = os.environ.get("GROQ_API_KEY", "").strip()
client = Groq(api_key=api_key)

prompt = f"""
Du bist Senior-Makroanalyst und Portfoliostratege für institutionelle Anleger.
Analysiere die folgenden Wirtschaftsnachrichten und erstelle ein kompaktes Daily Market Briefing auf Deutsch unter Verwendung präziser Börsenfachsprache. Formuliere nüchtern, faktenbasiert und handlungsorientiert. Keine Füllsätze, keine Begrüßung.

Antworte AUSSCHLIESSLICH im folgenden HTML-Snippet-Format (kein ```html Codeblock, keine Markdown-Backticks):

<div class="section-title">🚨 TOP-MARKTBEWEGER</div>
<ul class="news-list">
  <li><strong>[Schlagzeile]:</strong> [2-3 Sätze knallharte Marktanalyse und Konsequenzen]</li>
</ul>

<div class="section-title">📊 MAKRO, ZINSEN & WÄHRUNGEN</div>
<ul class="news-list">
  <li><strong>[Thema]:</strong> [Auswirkung auf Renditen, Devisenmärkte oder Notenbankpolitik]</li>
</ul>

<div class="section-title">🏢 UNTERNEHMEN & KEY MOVERS</div>
<ul class="news-list">
  <li><strong>[Unternehmen/Sektor]:</strong> [Relevanz für Margen, Earnings oder operative Trends]</li>
</ul>

<div class="section-title">🧭 FAZIT & MARKTSTIMMUNG</div>
<p><strong>Sentiment:</strong> <span class="sentiment">[Risk-On / Risk-Off / Neutral]</span> - [1-2 Sätze Erwartung für die heutige Handelssitzung]</p>

Nachrichten:
{raw_text}
"""

all_api_models = [m.id for m in client.models.list().data if getattr(m, 'active', True)]
valid_models = [
    m for m in all_api_models
    if not any(x in m.lower() for x in ["guard", "whisper", "vision", "arabic", "orpheus", "tts", "embedding"])
]

print("Verfügbare Textmodelle auf Groq:", valid_models)

report_html = None
for model_name in valid_models:
    try:
        print(f"Versuche Generierung mit: {model_name}...")
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=model_name,
            temperature=0.2,
        )
        report_html = chat_completion.choices[0].message.content.replace("```html", "").replace("```", "").strip()
        print(f"Erfolgreich generiert mit: {model_name}")
        break
    except Exception as e:
        print(f"Modell {model_name} übersprungen: {e}")

if not report_html:
    raise RuntimeError("Keines der verfügbaren Modelle konnte für die Generierung genutzt werden.")

# 3. HTML-Template für E-Mail (Newsletter-Design)
full_email_html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      line-height: 1.6;
      color: #0f172a;
      background-color: #f1f5f9;
      margin: 0;
      padding: 24px;
    }}
    .container {{
      max-width: 640px;
      margin: 0 auto;
      background: #ffffff;
      border-radius: 8px;
      padding: 32px;
      border: 1px solid #e2e8f0;
    }}
    .header {{
      border-bottom: 2px solid #0f172a;
      padding-bottom: 16px;
      margin-bottom: 24px;
    }}
    .header h1 {{
      margin: 0;
      font-size: 22px;
      font-weight: 800;
      letter-spacing: -0.5px;
      color: #0f172a;
    }}
    .subtitle {{
      margin: 4px 0 0 0;
      font-size: 12px;
      font-weight: 600;
      letter-spacing: 0.5px;
      text-transform: uppercase;
      color: #64748b;
    }}
    .section-title {{
      font-size: 14px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      color: #1e293b;
      margin-top: 24px;
      margin-bottom: 12px;
      padding-bottom: 4px;
      border-bottom: 1px solid #cbd5e1;
    }}
    .news-list {{
      padding-left: 18px;
      margin: 0 0 16px 0;
    }}
    .news-list li {{
      margin-bottom: 10px;
      font-size: 14px;
      color: #334155;
    }}
    .news-list li strong {{
      color: #0f172a;
    }}
    .sentiment {{
      background: #0f172a;
      color: #ffffff !important;
      padding: 3px 8px;
      border-radius: 4px;
      font-weight: 600;
      font-size: 13px;
    }}
    .footer {{
      margin-top: 32px;
      padding-top: 16px;
      border-top: 1px solid #e2e8f0;
      font-size: 11px;
      color: #94a3b8;
      text-align: center;
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>DAILY MARKET BRIEFING</h1>
      <div class="subtitle">Global Macro & Equity Intelligence</div>
    </div>
    {report_html}
    <div class="footer">
      Serverless Briefing • Automatisierte Pipeline via GitHub Actions
    </div>
  </div>
</body>
</html>"""

# 4. Telegram-Benachrichtigung
plain_summary = report_html.replace("<div class=\"section-title\">", "\n\n📌 ").replace("</div>", "")
plain_summary = plain_summary.replace("<li>", "• ").replace("</li>", "\n")
plain_summary = plain_summary.replace("<strong>", "*").replace("</strong>", "*")
for tag in ["<p>", "</p>", "<ul class=\"news-list\">", "</ul>", "<span class=\"sentiment\">", "</span>"]:
    plain_summary = plain_summary.replace(tag, "")

raw_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
tg_chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

# Sichere Token-Filterung: Entfernt versehentliche URLs oder Präfixe
tg_token = raw_token.split("/")[-1].replace("bot", "").strip() if "http" in raw_token else raw_token

if tg_token and tg_chat_id:
    tg_url = f"[https://api.telegram.org/bot](https://api.telegram.org/bot){tg_token}/sendMessage"
    requests.post(
        tg_url,
        data={"chat_id": tg_chat_id, "text": plain_summary.strip(), "parse_mode": "Markdown"}
    )

# 5. E-Mail versenden (HTML + Text-Fallback)
email_user = os.environ.get("EMAIL_USER")
email_pass = os.environ.get("EMAIL_PASS")
email_to = os.environ.get("EMAIL_RECEIVER")

if email_user and email_pass and email_to:
    msg = MIMEMultipart("alternative")
    msg["From"] = f"Market Intelligence <{email_user}>"
    msg["To"] = email_to
    msg["Subject"] = "Daily Market Briefing: Global Macro & Equity"

    msg.attach(MIMEText(plain_summary.strip(), "plain", "utf-8"))
    msg.attach(MIMEText(full_email_html, "html", "utf-8"))

    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login(email_user, email_pass)
    server.sendmail(email_user, email_to, msg.as_string())
    server.quit()
