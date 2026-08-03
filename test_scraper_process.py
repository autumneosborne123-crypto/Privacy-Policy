from pinterest_dl import ApiScraper
import os
import time

print(f"Parent process PID: {os.getpid()}")
scraper = ApiScraper()
print("Scraper initialized.")
time.sleep(5)
