import logging

def main():
    logging.info("Starting the application...")
    # load config
    # initialize database
    # execute main logic

if __name__ == "__main__":
    logging.basicConfig(filename='logs/app.log', level=logging.INFO)
    main()
    logging.info("Application finished successfully.")