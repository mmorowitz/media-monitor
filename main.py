import os
import logging
import yaml
from dotenv import load_dotenv
from db import init_db, get_last_checked, update_last_checked

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
        



if __name__ == "__main__":
    logging.basicConfig(filename='logs/app.log', level=logging.INFO)
    main()
    logging.info("Application finished successfully.")