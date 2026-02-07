import logging

logging.basicConfig(
    filename="production.log",
    level=logging.INFO
)

def log_calculation(result):
    logging.info(str(result))
