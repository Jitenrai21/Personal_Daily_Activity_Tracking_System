"""Production settings.

Import core settings from base and override minimal values here.
"""

from .base import *

DEBUG = False

ALLOWED_HOSTS = [host for host in os.getenv("ALLOWED_HOSTS", "").split(",") if host]
