from . import base

DEBUG = True

if not base.ALLOWED_HOSTS:
    ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
