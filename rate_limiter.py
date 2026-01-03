import time
from collections import defaultdict
RATE_LIMIT = 5  # max requests
WINDOW = 60     # seconds

clients = defaultdict(list)


def is_allowed(ip: str) -> bool:
    now = time.time()
    requests = clients[ip]

    # remove old timestamps
    clients[ip] = [t for t in requests if now-t < WINDOW]

    if len(clients[ip]) >= RATE_LIMIT:
        return False

    clients[ip].append(now)
    return True
