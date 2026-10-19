import streamlit as st

from views.shared import rider_wallet_section


def render(sb, user):
    st.title("🏍️ Rider dashboard")
    st.caption(f"Signed in as {user['full_name']} · {user['home_hub']} hub")

    # Re-fetch fresh in case cod_collected changed since login
    fresh = sb.table("profiles").select("*").eq("id", user["id"]).single().execute().data
    rider_wallet_section(sb, fresh)
