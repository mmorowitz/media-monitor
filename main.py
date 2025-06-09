import os
import logging
from logging.handlers import RotatingFileHandler
import yaml
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from db import init_db, get_last_checked, update_last_checked
from reddit_client import RedditClient
from youtube_client import YouTubeClient
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

load_dotenv()

def load_config(filename='config.yaml'):
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

def send_test_email(smtp_cfg):
    msg = EmailMessage()
    msg["Subject"] = "Media Monitor Test Email"
    msg["From"] = smtp_cfg["from"]
    msg["To"] = ", ".join(smtp_cfg["to"])
    msg.set_content("This is a test email from your Media Monitor script.")

    try:
        with smtplib.SMTP_SSL(smtp_cfg["server"], smtp_cfg["port"]) as server:
            server.login(smtp_cfg["username"], smtp_cfg["password"])
            server.send_message(msg)
        logging.info("Test email sent successfully.")
    except Exception as e:
        logging.error(f"Failed to send test email: {e}")

def send_email(smtp_cfg, all_items):
    msg = EmailMessage()
    msg["Subject"] = "Media Monitor Report"
    msg["From"] = smtp_cfg["from"]
    msg["To"] = ", ".join(smtp_cfg["to"])

    if not all_items:
        body = "No new items found from any source."
    else:
        body = "New items found:\n\n"
        for source, items in all_items.items():
            body += f"{source.capitalize()}:\n"
            if items:
                for item in items:
                    body += f"- {item.get('title', 'No Title')} (ID: {item.get('id', 'N/A')})\n"
            else:
                body += "No new items.\n"
            body += "\n"

    msg.set_content(body)

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