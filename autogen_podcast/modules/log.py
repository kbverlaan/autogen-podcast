import sys
import datetime
import os

class DualOutput:
    def __init__(self, filename, stdout):
        self.log_file = open(filename, 'w')
        self.stdout = stdout

    def write(self, data):
        self.log_file.write(data)
        self.stdout.write(data)
        self.flush()

    def flush(self):
        self.log_file.flush()

    def close(self):
        self.log_file.close()

def setup_logging():
    # Set up logging to file
    log_directory = "/Users/kbverlaan/GitProjects/autogen-podcast/logs"
    log_filename = datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + ".log"
    log_path = f"{log_directory}/{log_filename}"

    # Ensure the directory exists
    os.makedirs(log_directory, exist_ok=True)

    # Redirect stdout to our custom class
    sys.stdout = DualOutput(log_path, sys.stdout)
    
    # Optionally, if you want to capture stderr as well:
    sys.stderr = sys.stdout