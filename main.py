import os
import logging
from logging.handlers import RotatingFileHandler
import yaml
from datetime import datetime, timedelta, timezone
from src.db import init_db, get_last_checked, update_last_checked
from src.reddit_client import RedditClient
from src.youtube_client import YouTubeClient
import smtplib
from email.message import EmailMessage

log_handler = RotatingFileHandler(
    'logs/app.log', maxBytes=5*1024*1024, backupCount=5  # 5 MB per file, keep 5 backups
)
log_handler.setLevel(logging.INFO)
log_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s:%(message)s'))

logging.basicConfig(
    handlers=[log_handler],
    level=logging.INFO
)

def load_config(filename='config/config.yaml'):
    with open(filename, 'r') as file:
        return yaml.safe_load(file)

def process_source(source_name, client_class, config, db_conn):
    items = []
    if config.get(source_name, {}).get("enabled"):
        logging.info(f"{source_name.capitalize()} integration is enabled.")
        client = client_class(config[source_name])
        last_checked = get_last_checked(db_conn, source_name)
        if last_checked:
            last_checked = datetime.fromisoformat(last_checked)
            if last_checked.tzinfo is None:
                last_checked = last_checked.replace(tzinfo=timezone.utc)
        else:
            last_checked = datetime.now(timezone.utc) - timedelta(hours=72)
            logging.info(f"No previous check found, using last 72 hours as initial window for {source_name}.")
        logging.info(f"Last checked time for {source_name.capitalize()}: {last_checked}")

        new_items = client.get_new_items_since(last_checked)
        item_type = f"{source_name.capitalize()} items"

        logging.info(f"Found {len(new_items)} new {item_type} since last checked.")
        for item in new_items:
            logging.debug(f"New {source_name} item: {item['title']} (ID: {item['id']})")

        update_last_checked(db_conn, source_name, datetime.now(timezone.utc))
        logging.info(f"Updated last checked time for {source_name.capitalize()} in the database.")
        items = new_items
    return items

def load_smtp_settings(config):
    smtp_cfg = config.get("smtp", {})
    if not smtp_cfg.get("enabled", False):
        logging.info("SMTP is not enabled in config.")
        return None
    return smtp_cfg

def send_email(smtp_cfg, all_items):
    msg = EmailMessage()
    msg["Subject"] = "Media Monitor Report"
    msg["From"] = smtp_cfg["from"]
    msg["To"] = ", ".join(smtp_cfg["to"])

    if not all_items:
        body = "No new items found from any source."
        html_body = "<p>No new items found from any source.</p>"
    else:
        body = "New items found:\n\n"
        html_body = "<h2>New items found:</h2>"
        for source, items in all_items.items():
            body += f"{source.capitalize()}:\n"
            html_body += f"<h3>{source.capitalize()}:</h3><ul>"
            if items:
                for item in items:
                    title = item.get('title', 'No Title')
                    url = item.get('url', '#')
                    body += f"- {title} (ID: {item.get('id', 'N/A')})\n"
                    html_body += f'<li><a href="{url}">{title}</a> (ID: {item.get("id", "N/A")})</li>'
            else:
                body += "No new items.\n"
                html_body += "<li>No new items.</li>"
            body += "\n"
            html_body += "</ul>"

    msg.set_content(body)
    msg.add_alternative(html_body, subtype='html')

    try:
        with smtplib.SMTP_SSL(smtp_cfg["server"], smtp_cfg["port"]) as server:
            server.login(smtp_cfg["username"], smtp_cfg["password"])
            server.send_message(msg)
        logging.info("Email sent successfully.")
    except Exception as e:
        logging.error(f"Failed to send email: {e}")

def main():
    logging.info("Starting the application...")
    config = load_config()
    logging.info("Loaded configuration")

    db_conn = init_db()
    logging.info("Database initialized")

    all_items = {}
    all_items["reddit"] = process_source("reddit", RedditClient, config, db_conn)
    all_items["youtube"] = process_source("youtube", YouTubeClient, config, db_conn)

    db_conn.close()

    smtp_cfg = load_smtp_settings(config)
    if smtp_cfg:
        send_email(smtp_cfg, all_items)

if __name__ == "__main__":
    main()
    logging.info("Application finished successfully.")