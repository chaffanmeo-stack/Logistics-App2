import streamlit as st

from lib.db import get_supabase
from views import login, owner, hub, rider, customer

st.set_page_config(page_title="RouteWise", page_icon="📦", layout="wide")

sb = get_supabase()

if "user" not in st.session_state:
    login.render(sb)
    st.stop()

user = st.session_state["user"]

with st.sidebar:
    st.write(f"**{user['full_name'] or user.get('phone') or user.get('email')}**")
    st.caption(user["role"])
    if st.button("Sign out"):
        del st.session_state["user"]
        st.rerun()

role = user["role"]
if role == "Owner":
    owner.render(sb, user)
elif role == "Hub":
    hub.render(sb, user)
elif role == "Rider":
    rider.render(sb, user)
elif role == "Customer":
    customer.render(sb, user)
else:
    st.error("Unknown role on this account.")
