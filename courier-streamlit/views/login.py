import streamlit as st

from lib.security import verify_secret


def _try_login(sb, query_col: str, query_val: str, role_filter, secret_col: str, secret_val: str):
    q = sb.table("profiles").select("*").eq(query_col, query_val)
    if isinstance(role_filter, (list, tuple)):
        q = q.in_("role", list(role_filter))
    else:
        q = q.eq("role", role_filter)
    result = q.limit(1).execute()

    profile = result.data[0] if result.data else None
    if not profile or not profile.get(secret_col) or not verify_secret(secret_val, profile[secret_col]):
        return None
    return profile


def render(sb):
    st.title("📦 RouteWise")
    st.caption("Courier & Logistics Tracking")

    tab_customer, tab_staff = st.tabs(["Track a package", "Staff / Rider login"])

    with tab_customer:
        st.write("Enter the phone number your package was booked with.")
        with st.form("customer_login_form"):
            phone = st.text_input("Phone number", placeholder="03XXXXXXXXX")
            pin = st.text_input("6-digit PIN", type="password", max_chars=6)
            submitted = st.form_submit_button("View my packages", type="primary")
        if submitted:
            profile = _try_login(sb, "phone", phone, "Customer", "pin_hash", pin)
            if profile:
                st.session_state["user"] = profile
                st.rerun()
            else:
                st.error("That phone number and PIN don't match.")

    with tab_staff:
        mode = st.radio("I am a...", ["Owner / Hub", "Rider"], horizontal=True)

        if mode == "Owner / Hub":
            with st.form("staff_login_form"):
                email = st.text_input("Email")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Sign in", type="primary")
            if submitted:
                profile = _try_login(sb, "email", email, ["Owner", "Hub"], "password_hash", password)
                if profile:
                    st.session_state["user"] = profile
                    st.rerun()
                else:
                    st.error("Those details don't match our records.")
        else:
            with st.form("rider_login_form"):
                phone = st.text_input("Phone number", placeholder="03XXXXXXXXX")
                pin = st.text_input("6-digit PIN", type="password", max_chars=6)
                submitted = st.form_submit_button("Sign in", type="primary")
            if submitted:
                profile = _try_login(sb, "phone", phone, "Rider", "pin_hash", pin)
                if profile:
                    st.session_state["user"] = profile
                    st.rerun()
                else:
                    st.error("Those details don't match our records.")
