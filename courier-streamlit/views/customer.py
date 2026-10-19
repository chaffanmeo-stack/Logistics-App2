import streamlit as st

from views.shared import customer_tracking_section


def render(sb, user):
    st.title("📦 My packages")
    st.caption(user["phone"])
    customer_tracking_section(sb, user)
