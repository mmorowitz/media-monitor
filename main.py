import os
import logging
import yaml
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from db import init_db, get_last_checked, update_last_checked
from reddit_client import RedditClient

load_dotenv()

def load_config(filename='config.yaml'):
    with open(filename, 'r') as file:
        return yaml.safe_load(file)

def main():
    logging.info("Starting the application...")
    config = load_config()
    #TODO should i merge config and env variables?
    logging.info("Loaded configuration")

    # initialize database
    db_conn = init_db()
    logging.info("Database initialized")
    
    # execute main logic
    if config.get("reddit", {}).get("enabled"):
        logging.info("Reddit integration is enabled.")

        # Initialize Reddit client and perform actions
        reddit_client = RedditClient(config["reddit"])
        last_checked = get_last_checked(db_conn, "reddit")
        if not last_checked:
            last_checked = datetime.now(timezone.utc) - timedelta(hours=72)
            logging.info("No previous check found, using last 72 hours as initial window.")
        logging.info(f"Last checked time for Reddit: {last_checked}")
        
        new_posts = reddit_client.get_new_posts_since(last_checked)
        logging.info(f"Found {len(new_posts)} new Reddit posts since last checked.")
        
        for post in new_posts:
            logging.info(f"New post: {post['title']} (ID: {post['id']})")


if __name__ == "__main__":
    logging.basicConfig(filename='logs/app.log', level=logging.INFO)
    main()
    logging.info("Application finished successfully.")