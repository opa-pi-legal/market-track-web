import multiprocessing

bind = "0.0.0.0:8000"
workers = multiprocessing.cpu_count() * 2 + 1
timeout = 60
loglevel = "info"
accesslog = "-"
errorlog = "-"

wsgi_app = "market_track.wsgi:application"