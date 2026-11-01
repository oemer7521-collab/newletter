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
    for entry in feed.entries[:6]:
        collected_news.append(f"- {entry.title}: {entry.get('summary', '')}")

raw_text = "\n".join(collected_news)

# 2. Analyse durch Groq mit geschärftem Prompt & bestem Modell
api_key = os.environ.get("GROQ_API_KEY", "").strip()
client = Groq(api_key=api_key)

available_models = [m.id for m in client.models.list().data]

# Bevorzuge große 70B/Flaggschiff-Modelle für hohe sprachliche Präzision
priority_models = [
    "llama-3.3-70b-versatile",
    "llama-3.2-90b-vision-preview",
    "llama-3.1-70b-versatile",
    "mixtral-8x7b-32768",
    "llama-3.1-8b-instant"
]
chosen_model = next((m for m in priority_models if m in available_models), available_models[0])

system_prompt = (
    "Du bist leitender Chefanalyst und Makrostratege für institutionelle Investoren. "
    "Deine Aufgabe ist es, weltweite Wirtschaftsmeldungen zu filtern und in stilsicherem, "
    "prägnantem Finanzdeutsch (Börsenfachsprache) zusammenzufassen. "
    "Verzichte auf Floskeln oder Einleitungen. Antworte ausschließlich im vorgegebenen HTML-Snippet-Format."
)

user_prompt = f"""
Analysiere die folgenden Nachrichtenmeldungen und erstelle ein kompaktes Daily Market Briefing.
Formatiere deine Antwort direkt als HTML (nutze nur <p>, <ul>, <li>, <strong>, <span> - KEIN ```html Codeblock, kein <html> oder <body>).

Strukturvorgabe:

<div class="section-title">🚨 TOP-MARKTBEWEGER</div>
<ul class="news-list">
  <li><strong>[Schlagzeile]:</strong> [2-3 Sätze knallharte Marktanalyse und Konsequenzen]</li>
</ul>

<div class="section-title">📊 MAKRO, ZINSEN & WÄHRUNGEN</div>
<ul class="news-list">
  <li><strong>[Thema]:</strong> [Auswirkung auf Renditen, Währungen oder Zentralbankpolitik]</li>
</ul>

<div class="section-title">🏢 UNTERNEHMEN & KEY MOVERS</div>
<ul class="news-list">
  <li><strong>[Unternehmen/Branche]:</strong> [Relevanz für Quartalszahlen oder Kursentwicklung]</li>
</ul>

<div class="section-title">🧭 FAZIT & HANDELSSTIMMUNG</div>
<p><strong>Sentiment:</strong> <span class="sentiment">[Risk-On / Risk-Off / Abwartend]</span> - [1-2 Sätze Begründung zur Tageserwartung]</p>

Meldungen zur Analyse:
{raw_text}
"""

chat_completion = client.chat.completions.create(
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ],
    model=chosen_model,
    temperature=0.2,
)
analysis_html = chat_completion.choices[0].message.content.replace("```html", "").replace("```", "").strip()

# 3. Ansprechendes E-Mail HTML-Template zusammenbauen
full_email_html = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      line-height: 1.6;
      color: #1e293b;
      background-color: #f8fafc;
      margin: 0;
      padding: 24px;
    }}
    .container {{
      max-width: 650px;
      margin: 0 auto;
      background: #ffffff;
      border-radius: 12px;
      padding: 32px;
      box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -2px rgba(0, 0, 0, 0.05);
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
      color: #0f172a;
      letter-spacing: -0.5px;
    }}
    .header .subtitle {{
      margin: 4px 0 0 0;
      font-size: 13px;
      color: #64748b;
      text-transform: uppercase;
      font-weight: 600;
    }}
    .section-title {{
      font-size: 15px;
      font-weight: 700;
      color: #0f172a;
      margin-top: 24px;
      margin-bottom: 12px;
      padding-bottom: 4px;
      border-bottom: 1px solid #cbd5e1;
      letter-spacing: 0.3px;
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
      background: #e2e8f0;
      padding: 2px 8px;
      border-radius: 4px;
      font-weight: 600;
      color: #0f172a;
    }}
    .footer {{
      margin-top: 32px;
      padding-top: 16px;
      border-top: 1px solid #f1f5f9;
      font-size: 12px;
      color: #94a3b8;
      text-align: center;
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>Daily Market Briefing</h1>
      <div class="subtitle">Global Macro & Equity Intelligence</div>
    </div>
    {analysis_html}
    <div class="footer">
      Automatisch generiert via GitHub Actions & Groq Llama 3
    </div>
  </div>
</body>
</html>
"""

# 4. Telegram-Text (bereinigte Textfassung ohne HTML-Layout)
plain_summary = analysis_html.replace("<div class=\"section-title\">", "\n\n📌 ").replace("</div>", "")
plain_summary = plain_summary.replace("<li>", "• ").replace("</li>", "\n")
plain_summary = plain_summary.replace("<strong>", "*").replace("</strong>", "*")
for tag in ["<p>", "</p>", "<ul class=\"news-list\">", "</ul>", "<span class=\"sentiment\">", "</span>"]:
    plain_summary = plain_summary.replace(tag, "")

tg_token = os.environ.get("TELEGRAM_BOT_TOKEN")
tg_chat_id = os.environ.get("TELEGRAM_CHAT_ID")
if tg_token and tg_chat_id:
    requests.post(
        f"[https://api.telegram.org/bot](https://api.telegram.org/bot){tg_token}/sendMessage",
        data={"chat_id": tg_chat_id, "text": plain_summary.strip(), "parse_mode": "Markdown"}
    )

# 5. E-Mail als HTML versenden
email_user = os.environ.get("EMAIL_USER")
email_pass = os.environ.get("EMAIL_PASS")
email_to = os.environ.get("EMAIL_RECEIVER")

if email_user and email_pass and email_to:
    msg = MIMEMultipart("alternative")
    msg["From"] = f"Market Intelligence <{email_user}>"
    msg["To"] = email_to
    msg["Subject"] = "Daily Market Briefing: Relevante Markteinflüsse"

    # HTML-Part anhängen
    msg.attach(MIMEText(full_email_html, "html", "utf-8"))

    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login(email_user, email_pass)
    server.sendmail(email_user, email_to, msg.as_string())
    server.quit()
