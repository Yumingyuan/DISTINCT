import logging
import os
import sys
from model.BrowserAPI import BrowserAPI

logger = logging.getLogger(__name__)

def main():
    verbosity = os.environ["VERBOSITY"]
    level = logging.getLevelName(verbosity) if verbosity else logging.DEBUG
    logging.basicConfig(stream=sys.stdout, level=level)
    logging.getLogger(__name__).setLevel(level)
    logging.getLogger('werkzeug').setLevel(level)
    logger.info(f"Log level: {level}")

    browser_api = BrowserAPI()
    browser_api.start()
    browser_api.join()

if __name__ == "__main__":
    main()
