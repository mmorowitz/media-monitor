import os
import logging
import yaml
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from db import init_db, get_last_checked, update_last_checked
from reddit_client import RedditClient
from youtube_client import YouTubeClient

logging.basicConfig(filename='logs/app.log', level=logging.INFO)

load_dotenv()

def load_config(filename='config.yaml'):
    with open(filename, 'r') as file:
        return yaml.safe_load(file)

def process_source(source_name, client_class, config, db_conn):
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

def main():
    logging.info("Starting the application...")
    config = load_config()
    logging.info("Loaded configuration")

    db_conn = init_db()
    logging.info("Database initialized")

    process_source("reddit", RedditClient, config, db_conn)
    process_source("youtube", YouTubeClient, config, db_conn)

    db_conn.close()


if __name__ == "__main__":
    main()
    logging.info("Application finished successfully.")