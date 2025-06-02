import os
import logging
from dotenv import load_dotenv

load_dotenv()

def main():
    logging.info("Starting the application...")
    
    # load config
    smtp_server = os.getenv('SMTP_SERVER')
    smtp_port = os.getenv('SMTP_PORT')
    smtp_user = os.getenv('SMTP_USER')
    smtp_password = os.getenv('SMTP_PASSWORD')

    # initialize database
    # execute main logic

if __name__ == "__main__":
    logging.basicConfig(filename='logs/app.log', level=logging.INFO)
    main()
    logging.info("Application finished successfully.")