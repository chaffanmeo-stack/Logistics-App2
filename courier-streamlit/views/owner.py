import streamlit as st
import pandas as pd

from lib.db import HUBS
from lib.security import hash_secret, generate_pin
from views.shared import book_package_form, create_trip_form, trips_overview, hub_queue_section


def _overview_tab(sb):
    packages = sb.table("packages").select("status, fare_pkr").execute().data
    total_packages = len(packages)
    total_revenue = sum(p["fare_pkr"] for p in packages)

    col1, col2 = st.columns(2)
    col1.metric("Total packages", total_packages)
    col2.metric("Total fare revenue", f"Rs {total_revenue:,.0f}")

    if packages:
        df = pd.DataFrame(packages)
        counts = df["status"].value_counts()
        st.bar_chart(counts)

    st.divider()
    st.subheader("Each hub right now")
    for hub in HUBS:
        waiting = (
            sb.table("packages")
            .select("id", count="exact")
            .eq("current_hub", hub)
            .in_("status", ["Booked", "Reached Hub"])
            .execute()
        )
        st.write(f"**{hub}** — {waiting.count or 0} package(s) waiting")


def _accounts_tab(sb):
    st.subheader("Create a Hub login")
    with st.form("create_hub_form", clear_on_submit=True):
        name = st.text_input("Hub staff name")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        hub = st.selectbox("Which hub is this login for?", HUBS)
        submitted = st.form_submit_button("Create Hub login", type="primary")
    if submitted:
        if not (name and email and password):
            st.error("Fill in all fields.")
        else:
            sb.table("profiles").insert(
                {
                    "role": "Hub",
                    "full_name": name,
                    "email": email.strip().lower(),
                    "password_hash": hash_secret(password),
                    "home_hub": hub,
                }
            ).execute()
            st.success(f"Hub login created for {hub}. Give them the email/password you entered.")

    st.divider()
    st.subheader("Create a Rider login")
    with st.form("create_rider_form", clear_on_submit=True):
        name = st.text_input("Rider name")
        phone = st.text_input("Phone number", placeholder="03XXXXXXXXX")
        hub = st.selectbox("Which hub does this rider work from?", HUBS, key="rider_hub")
        submitted = st.form_submit_button("Create Rider login", type="primary")
    if submitted:
        if not (name and phone):
            st.error("Fill in all fields.")
        else:
            pin = generate_pin()
            sb.table("profiles").insert(
                {
                    "role": "Rider",
                    "full_name": name,
                    "phone": phone,
                    "pin_hash": hash_secret(pin),
                    "home_hub": hub,
                }
            ).execute()
            st.success(f"Rider login created for {hub}. Their PIN is **{pin}** — give them the phone number + this PIN.")

    st.divider()
    st.subheader("Existing Hub & Rider accounts")
    accounts = sb.table("profiles").select("*").in_("role", ["Hub", "Rider"]).execute().data
    for acc in accounts:
        with st.container(border=True):
            identity = acc["email"] if acc["role"] == "Hub" else acc["phone"]
            st.write(f"**{acc['full_name']}** · {acc['role']} · {acc['home_hub']} · {identity}")
            if acc["role"] == "Rider" and acc.get("cod_collected", 0) > 0:
                st.write(f"Holding Rs {acc['cod_collected']} uncleared COD")
                if st.button("Clear COD (cash received)", key=f"clear_{acc['id']}"):
                    sb.table("cod_clearances").insert(
                        {
                            "rider_id": acc["id"],
                            "amount": acc["cod_collected"],
                            "cleared_by": st.session_state["user"]["id"],
                        }
                    ).execute()
                    sb.table("profiles").update({"cod_collected": 0}).eq("id", acc["id"]).execute()
                    st.success("Cleared.")
                    st.rerun()


def render(sb, user):
    st.title("🧭 Owner dashboard")
    st.caption(f"Signed in as {user['full_name']}")

    tabs = st.tabs(["Overview", "Book Package", "Dispatch Trip", "Trips", "Hub Queues", "Accounts"])

    with tabs[0]:
        _overview_tab(sb)
    with tabs[1]:
        book_package_form(sb, created_by_id=user["id"])
    with tabs[2]:
        create_trip_form(sb, created_by_id=user["id"])
    with tabs[3]:
        trips_overview(sb)
    with tabs[4]:
        hub_choice = st.selectbox("Pick a hub to view", HUBS, key="owner_hub_queue_pick")
        riders = sb.table("profiles").select("*").eq("role", "Rider").eq("home_hub", hub_choice).execute().data
        hub_queue_section(sb, hub_choice, riders)
    with tabs[5]:
        _accounts_tab(sb)
