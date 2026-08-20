from __future__ import annotations

import hmac
import os

import streamlit as st


def _get_secret(name: str) -> str | None:
    try:
        value = st.secrets.get(name)
        if value:
            return str(value)
    except Exception:
        pass
    value = os.getenv(name)
    return value if value else None


def require_dashboard_auth() -> None:
    """Require a shared dashboard password on every Streamlit page.

    The password is read from Streamlit secrets (preferred in cloud) or from an
    environment variable for local use. It is never stored in Git.
    """
    expected = _get_secret("DASHBOARD_PASSWORD")
    if not expected:
        st.error("DASHBOARD_PASSWORD non configurata nei Secrets.")
        st.stop()

    if st.session_state.get("dashboard_authenticated") is True:
        return

    st.subheader("Trading Lab | Accesso")
    with st.form("dashboard_login", clear_on_submit=True):
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Entra")

    if submitted:
        if hmac.compare_digest(password, expected):
            st.session_state["dashboard_authenticated"] = True
            st.rerun()
        st.error("Password non corretta.")

    st.stop()
