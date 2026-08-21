"""Streamlit Cloud compatibility shim.

When Streamlit executes dashboard/app.py directly, dashboard/ can become the
first sys.path entry. In that layout ``from dashboard.data_access`` resolves to
this nested package. Re-export the real sibling module without duplicating
implementation.
"""
from data_access import *  # noqa: F401,F403
