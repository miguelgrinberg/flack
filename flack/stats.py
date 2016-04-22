from flask import current_app
from .utils import timestamp

# We use a list to calculate requests per second
request_stats = []


def add_request():
    t = timestamp()
    while len(request_stats) > 0 and \
            request_stats[0] < t - current_app.config['REQUEST_STATS_WINDOW']:
        del request_stats[0]
    request_stats.append(t)


def requests_per_second():
    return len(request_stats) / current_app.config['REQUEST_STATS_WINDOW']
