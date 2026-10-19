"""
Single shared Supabase client. st.cache_resource means this only runs
once per app instance, not on every script rerun (Streamlit reruns the
whole script on every interaction, so this cache matters a lot).
"""

import streamlit as st
from supabase import create_client, Client


@st.cache_resource
def get_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


HUBS = ["BWP", "Multan", "Lahore", "Lodhran", "RYK"]
