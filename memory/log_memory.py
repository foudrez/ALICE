from datetime import datetime



def log_event(speaker, text):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {speaker}: {text}\n"
    
    # "a" means append. It will create the file if it doesn't exist, and add to the bottom if it does.
    with open("chat_log.txt", "a", encoding="utf-8") as file:
        file.write(log_entry)

