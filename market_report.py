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
            model=model
