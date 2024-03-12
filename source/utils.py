import sys

class Logger:
    def __init__(self, filepath, terminal=sys.stdout):
        self.terminal = terminal
        self.log = open(filepath, "a", encoding="utf-8")

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)

    def flush(self):
        # Flush both the terminal and the log file to ensure
        # that all messages are up-to-date
        self.terminal.flush()
        self.log.flush()