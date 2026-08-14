"""Compatibility mailer for the frozen USA v5.5 reference module.
The new architecture uses notifications/email_client.py; this shim only makes the
reference implementation importable for parity tests and rollback.
"""
from notifications.email_client import send_email
