import streamlit as st

from views.shared import book_package_form, create_trip_form, trips_overview, hub_queue_section


def render(sb, user):
    hub = user["home_hub"]
    st.title(f"🏬 {hub} Hub dashboard")
    st.caption(f"Signed in as {user['full_name']}")

    tabs = st.tabs(["Queue", "Book Package", "Dispatch Trip", "Trips"])

    with tabs[0]:
        riders = sb.table("profiles").select("*").eq("role", "Rider").eq("home_hub", hub).execute().data
        hub_queue_section(sb, hub, riders)
    with tabs[1]:
        book_package_form(sb, created_by_id=user["id"], default_origin=hub)
    with tabs[2]:
        create_trip_form(sb, created_by_id=user["id"], default_origin=hub)
    with tabs[3]:
        trips_overview(sb)
