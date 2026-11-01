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

# 2. Verfügbares Groq-Modell automatisch ermitteln
api_key = os.environ.get("GROQ_API_KEY", "").strip()
client = Groq(api_key=api_key)

available_models = [m.id for m in client.models.list().data]

# Bevorzugte Modelle der Reihe nach prüfen
preferred_models = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "llama3-8b-8192",
    "gemma2-9b-it",
    "mixtral-8x7b-32768"
]

chosen_model = next((m for m in preferred_models if m in available_models), available_models[0])
print(f"Verwende Modell: {chosen_model}")

prompt = f"""
Du bist ein erfahrener Börsenanalyst und Makroökonom.
Analysiere die folgenden internationalen Nachrichtenmeldungen und erstelle ein kompaktes Daily Market Briefing für Investoren auf Deutsch.

Fokussiere dich auf Ereignisse, die tatsächlichen Markteinfluss haben:
- Geldpolitik & Zinsen (Fed, EZB)
- Geopolitische Spannungen & Rohstoffpreise (Öl, Gas)
- Wichtige Tech- und Branchenmeldungen sowie Quartalszahlen

Strukturierung:
1. 🚨 TOP-MARKTBEWEGER (Die 2-3 wichtigsten Ereignisse)
2. 📊 MAKRO, ZINSEN & WÄHRUNGEN
3. 🏢 UNTERNEHMEN & BRANCHEN
4. 🧭 FAZIT FÜR DEN HANDELSTAG (Mögliche Marktstimmung: Risk-On / Risk-Off)

Halte die Punkte prägnant, fundiert und verzichte auf irrelevante Füllnachrichten.

Meldungen:
{raw_text}
"""

chat_completion = client.chat.completions.create(
    messages=[{"role": "user", "content": prompt}],
    model=chosen_model,
)
report_text = chat_completion.choices[0].message.content

# 3. An Telegram senden
tg_token = os.environ.get("TELEGRAM_BOT_TOKEN")
tg_chat_id = os.environ.get("TELEGRAM_CHAT_ID")
if tg_token and tg_chat_id:
    requests.post(
        f"https://api.telegram.org/bot{tg_token}/sendMessage",
        data={"chat_id": tg_chat_id, "text": report_text}
    )

# 4. Per E-Mail versenden
email_user = os.environ.get("EMAIL_USER")
email_pass = os.environ.get("EMAIL_PASS")
email_to = os.environ.get("EMAIL_RECEIVER")

if email_user and email_pass and email_to:
    msg = MIMEMultipart()
    msg["From"] = f"Market Bot <{email_user}>"
    msg["To"] = email_to
    msg["Subject"] = "Daily Market Briefing: Relevante Markteinflusse"
    msg.attach(MIMEText(report_text, "plain", "utf-8"))

    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login(email_user, email_pass)
    server.sendmail(email_user, email_to, msg.as_string())
    server.quit()
