"""Gunicorn configuration for the A2 ROS web dashboard."""
import multiprocessing
import os

bind = f"{os.getenv('APP_HOST', '127.0.0.1')}:{os.getenv('APP_PORT', '8000')}"
workers = int(os.getenv("WEB_CONCURRENCY", max(2, multiprocessing.cpu_count())))
threads = int(os.getenv("WEB_THREADS", "2"))
worker_class = "gthread"
timeout = 60
graceful_timeout = 30
keepalive = 5
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("GUNICORN_LOGLEVEL", "info")
proc_name = "a2ros-web"
