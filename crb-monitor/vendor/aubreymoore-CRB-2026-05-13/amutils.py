import logging
from logging.handlers import RotatingFileHandler
import sys
import fire
import os
import xdoctest
import tomllib

##########

def setup_logging(log_filename="app.log", max_bytes=5_000_000, backup_count=3):
    """
    Sets up a logger with a custom format, timestamps, and file rotation.
    
    :param log_filename: Path to the log file.
    :param max_bytes: Maximum size of a log file before it rotates (5MB default).
    :param backup_count: Number of historical log files to retain (3 default).
    :return: Configured logger instance.
    
    Example:
        >>> log = setup_logging(log_filename="test.log", max_bytes=1024, backup_count=2)
        >>> # Write various log levels
        >>> log.info("Application started successfully.")
        >>> log.warning("This is a warning message.")
        >>> log.error("An error occurred during processing.")

        >>> # Simulate a loop to show file rotation in action
        >>> for i in range(50):
        ...    log.info(f"Generating log line entry number {i} to trigger rotation.")
        >>> log.debug("This is a DEBUG message.")
        >>> log.info("This is an INFO message.")
        >>> log.warning("This is a WARNING message.")
        >>> log.error("This is an ERROR message.")
        >>> log.critical("This is a CRITICAL message.")    
            
        >>> log.warning('Remember to clean up by deleting all test.log* files (rm test.log*)')
    """
    # 1. Initialize the logger
    logger = logging.getLogger(log_filename)
    logger.setLevel(logging.DEBUG)
    
    # Clear existing handlers to prevent duplicate logs if re-initialized
    if logger.hasHandlers():
        logger.handlers.clear()

    # 2. Define the log format and timestamp style
    # %(asctime)s inserts the timestamp
    log_format = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 3. Create the Rotating File Handler
    file_handler = RotatingFileHandler(
        log_filename, 
        maxBytes=max_bytes, 
        backupCount=backup_count,
        encoding="utf-8"
    )
    file_handler.setFormatter(log_format)
    file_handler.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)

    # 4. Create a Console Handler (Optional: so you can see logs in terminal)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_format)
    console_handler.setLevel(logging.DEBUG)
    logger.addHandler(console_handler)

    return logger

##########

def dict_from_toml(toml_path: str) -> dict:
    """  
    Extracts data from a toml file and returns them in a dictionary
    
    Example:
        >>> dict_from_toml('config.toml')
    """
    with open(toml_path, "rb") as f:
        return tomllib.load(f) 
    
##########  

def main(): 
    # If '--test' is passed in the terminal arguments, run doctest instead of CLI
    if "--test" in sys.argv:
        sys.argv.remove("--test")  # Clean up arguments for doctest
        xdoctest.doctest_module(__file__)
        print("xdoctest completed.")
    else:
        os.environ["PAGER"] = "cat" # disables output in full page format
        fire.Fire({
            'setup_logging': setup_logging,
            'dict_from_toml': dict_from_toml 
        })

##########

if __name__ == '__main__':
    main()