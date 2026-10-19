"""
Reusable pieces shared across role dashboards. Keeping these here once
instead of copy-pasting into owner.py/hub.py avoids the two copies
drifting apart as the app grows.
"""

from datetime import datetime, timezone

import streamlit as st
import pandas as pd

from lib.db import HUBS
from lib.security import hash_secret, generate_pin, generate_tracking_id, generate_delivery_code
from lib.pricing import calculate_fare
from lib.simulate import compute_trip_position, sync_trip_progress, HUB_COORDS

STATUS_EMOJI = {
    "Booked": "📦",
    "In Transit": "🚚",
    "Reached Hub": "🏬",
    "Out for Delivery": "🏍️",
    "Delivered": "✅",
    "Cancelled": "❌",
}


def _get_or_create_customer(sb, receiver_name: str, receiver_phone: str):
    existing = (
        sb.table("profiles")
        .select("*")
        .eq("phone", receiver_phone)
        .eq("role", "Customer")
        .limit(1)
        .execute()
    )
    if existing.data:
        return existing.data[0], None

    pin = generate_pin()
    created = (
        sb.table("profiles")
        .insert(
            {
                "role": "Customer",
                "full_name": receiver_name,
                "phone": receiver_phone,
                "pin_hash": hash_secret(pin),
            }
        )
        .execute()
    )
    return created.data[0], pin


def book_package_form(sb, created_by_id: str, default_origin: str | None = None):
    st.subheader("Book a package")
    with st.form("book_package_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        sender_name = col1.text_input("Sender name")
        receiver_name = col2.text_input("Receiver name")

        col3, col4 = st.columns(2)
        receiver_phone = col3.text_input("Receiver phone", placeholder="03XXXXXXXXX")
        receiver_email = col4.text_input("Receiver email (optional)")

        receiver_address = st.text_input("Receiver address (for last-mile delivery)")

        col5, col6 = st.columns(2)
        origin_hub = col5.selectbox("Origin hub", HUBS, index=HUBS.index(default_origin) if default_origin in HUBS else 0)
        destination_hub = col6.selectbox("Destination hub", HUBS, index=1 if default_origin != HUBS[1] else 2)

        col7, col8 = st.columns(2)
        weight_kg = col7.number_input("Actual weight (kg)", min_value=0.0, value=1.0, step=0.5)
        distance_km = col8.number_input("Distance (km)", min_value=0.0, value=50.0, step=5.0)

        cod_amount = st.number_input("Item value / COD to collect (Rs)", min_value=0.0, value=0.0, step=50.0)

        with st.expander("Dimensions (optional — for accurate volumetric fare)"):
            d1, d2, d3 = st.columns(3)
            length_cm = d1.number_input("Length (cm)", min_value=0.0, value=0.0)
            width_cm = d2.number_input("Width (cm)", min_value=0.0, value=0.0)
            height_cm = d3.number_input("Height (cm)", min_value=0.0, value=0.0)

        submitted = st.form_submit_button("Book package", type="primary")

    if not submitted:
        return

    if not (sender_name and receiver_name and receiver_phone):
        st.error("Sender name, receiver name, and receiver phone are required.")
        return
    if origin_hub == destination_hub:
        st.error("Origin and destination hub can't be the same.")
        return

    fare = calculate_fare(weight_kg, distance_km, length_cm, width_cm, height_cm)
    customer_profile, new_pin = _get_or_create_customer(sb, receiver_name, receiver_phone)
    tracking_id = generate_tracking_id()

    sb.table("packages").insert(
        {
            "tracking_id": tracking_id,
            "sender_name": sender_name,
            "receiver_name": receiver_name,
            "receiver_phone": receiver_phone,
            "receiver_email": receiver_email or None,
            "receiver_address": receiver_address or None,
            "origin_hub": origin_hub,
            "destination_hub": destination_hub,
            "current_hub": origin_hub,
            "status": "Booked",
            "weight_kg": weight_kg,
            "distance_km": distance_km,
            "length_cm": length_cm,
            "width_cm": width_cm,
            "height_cm": height_cm,
            "fare_pkr": fare,
            "cod_amount": cod_amount,
            "created_by": created_by_id,
        }
    ).execute()

    st.success(f"Booked! Tracking ID **{tracking_id}** — fare Rs {fare}")
    if new_pin:
        if receiver_email:
            st.info("New customer — PIN would be emailed (email sending not wired up in this phase). "
                     f"For now, share this PIN manually: **{new_pin}**")
        else:
            st.info(f"New customer — share this PIN with them so they can track: **{new_pin}**")


def create_trip_form(sb, created_by_id: str, default_origin: str | None = None):
    st.subheader("Dispatch a trip")
    with st.form("create_trip_form", clear_on_submit=True):
        origin_hub = st.selectbox(
            "Departing from", HUBS, index=HUBS.index(default_origin) if default_origin in HUBS else 0
        )
        route = st.multiselect(
            "Stops, in order (last one is the final destination)",
            [h for h in HUBS if h != origin_hub],
        )
        minutes_per_leg = st.slider(
            "Simulated travel time per hub-to-hub leg (minutes)", min_value=1, max_value=240, value=90
        )
        submitted = st.form_submit_button("Dispatch trip", type="primary")

    if not submitted:
        return
    if not route:
        st.error("Pick at least one stop.")
        return

    trip = (
        sb.table("trips")
        .insert(
            {
                "origin_hub": origin_hub,
                "route": route,
                "minutes_per_leg": minutes_per_leg,
                "created_by": created_by_id,
            }
        )
        .execute()
    ).data[0]

    # Attach any packages waiting at the origin hub whose destination is on this route
    waiting = (
        sb.table("packages")
        .select("id, destination_hub")
        .eq("current_hub", origin_hub)
        .eq("status", "Booked")
        .execute()
    ).data
    pickup_ids = [p["id"] for p in waiting if p["destination_hub"] in route]
    if pickup_ids:
        sb.table("packages").update(
            {"status": "In Transit", "trip_id": trip["id"], "current_hub": None}
        ).in_("id", pickup_ids).execute()

    st.success(f"Trip dispatched from {origin_hub} → {' → '.join(route)}. {len(pickup_ids)} package(s) attached.")


def trips_overview(sb, filter_hub: str | None = None):
    st.subheader("Trips in progress")
    query = sb.table("trips").select("*").eq("status", "In Progress")
    if filter_hub:
        query = query.eq("origin_hub", filter_hub)
    trips = query.execute().data

    if not trips:
        st.caption("No trips currently in progress.")
        return

    map_rows = []
    for trip in trips:
        sync_trip_progress(sb, trip)
        pos = compute_trip_position(trip)
        path_str = " → ".join(pos["path"])
        pct = int(((pos["current_leg"] + pos["progress_in_leg"]) / max(len(pos["path"]) - 1, 1)) * 100)
        st.write(f"**{path_str}** — {pct}% of the way, currently near **{pos['current_hub_label']}**")
        st.progress(min(max(pct, 0), 100) / 100)
        map_rows.append({"lat": pos["lat"], "lon": pos["lon"]})

    if map_rows:
        st.map(pd.DataFrame(map_rows), size=60)


def hub_queue_section(sb, hub_code: str, riders: list[dict]):
    st.subheader(f"{hub_code} hub queue")

    incoming = (
        sb.table("packages")
        .select("*")
        .eq("current_hub", hub_code)
        .in_("status", ["Booked", "Reached Hub"])
        .order("created_at")
        .execute()
    ).data

    if not incoming:
        st.caption("No packages currently at this hub.")
        return

    booked_here = [p for p in incoming if p["status"] == "Booked" and p["origin_hub"] == hub_code]
    reached_here = [p for p in incoming if p["status"] == "Reached Hub"]

    if booked_here:
        st.caption(f"Booked here, waiting for a trip: {len(booked_here)}")
        for p in booked_here:
            st.write(f"📦 {p['tracking_id']} → {p['destination_hub']} · {p['receiver_name']}")

    if reached_here:
        st.caption(f"Arrived — ready to assign to a rider: {len(reached_here)}")
        rider_options = {r["full_name"] or r["phone"]: r["id"] for r in riders}
        for p in reached_here:
            with st.container(border=True):
                st.write(f"🏬 **{p['tracking_id']}** → {p['receiver_name']} ({p['receiver_phone']})")
                if p.get("receiver_address"):
                    st.caption(p["receiver_address"])
                st.caption(f"COD to collect: Rs {p['cod_amount']}")
                if not rider_options:
                    st.warning("No riders set up for this hub yet.")
                    continue
                chosen = st.selectbox(
                    "Assign to rider", list(rider_options.keys()), key=f"rider_select_{p['id']}"
                )
                if st.button("Assign & dispatch for delivery", key=f"assign_btn_{p['id']}"):
                    code = generate_delivery_code()
                    sb.table("packages").update(
                        {
                            "status": "Out for Delivery",
                            "assigned_rider_id": rider_options[chosen],
                            "delivery_code": code,
                        }
                    ).eq("id", p["id"]).execute()
                    st.success(f"Assigned to {chosen}. Delivery code generated.")
                    st.rerun()


def rider_wallet_section(sb, rider: dict):
    st.subheader("My deliveries")

    assigned = (
        sb.table("packages")
        .select("*")
        .eq("assigned_rider_id", rider["id"])
        .eq("status", "Out for Delivery")
        .execute()
    ).data

    remaining_total = sum(p["cod_amount"] for p in assigned)

    col1, col2 = st.columns(2)
    col1.metric("Collected (uncleared)", f"Rs {rider.get('cod_collected', 0)}")
    col2.metric("Remaining to deliver", f"Rs {remaining_total}")

    if not assigned:
        st.caption("Nothing assigned to you right now.")
        return

    for p in assigned:
        with st.container(border=True):
            st.write(f"🏍️ **{p['tracking_id']}** → {p['receiver_name']} ({p['receiver_phone']})")
            if p.get("receiver_address"):
                st.caption(p["receiver_address"])
            st.caption(f"Collect on delivery: Rs {p['cod_amount']}")
            code_input = st.text_input("Delivery code from customer", key=f"code_{p['id']}", max_chars=4)
            if st.button("Confirm delivery", key=f"deliver_btn_{p['id']}"):
                if code_input == p["delivery_code"]:
                    sb.table("packages").update(
                        {"status": "Delivered", "delivered_at": datetime.now(timezone.utc).isoformat()}
                    ).eq("id", p["id"]).execute()
                    sb.table("profiles").update(
                        {"cod_collected": rider.get("cod_collected", 0) + p["cod_amount"]}
                    ).eq("id", rider["id"]).execute()
                    st.success("Delivered! Cash added to your collected total.")
                    st.rerun()
                else:
                    st.error("That code doesn't match. Ask the customer to check their tracking page.")


def customer_tracking_section(sb, customer: dict):
    st.subheader("My packages")

    packages = (
        sb.table("packages")
        .select("*")
        .eq("receiver_phone", customer["phone"])
        .order("created_at", desc=True)
        .execute()
    ).data

    if not packages:
        st.caption("No packages linked to this number yet.")
        return

    for p in packages:
        with st.container(border=True):
            emoji = STATUS_EMOJI.get(p["status"], "")
            st.write(f"{emoji} **{p['tracking_id']}** — {p['status']}")
            st.caption(f"{p['origin_hub']} → {p['destination_hub']} · from {p['sender_name']} · Rs {p['fare_pkr']}")

            if p["status"] == "Out for Delivery" and p.get("delivery_code"):
                st.info(f"Share this code with the rider when your package arrives: **{p['delivery_code']}**")

            if p["status"] == "In Transit" and p.get("trip_id"):
                trip = sb.table("trips").select("*").eq("id", p["trip_id"]).single().execute().data
                if trip:
                    sync_trip_progress(sb, trip)
                    pos = compute_trip_position(trip)
                    st.map(pd.DataFrame([{"lat": pos["lat"], "lon": pos["lon"]}]), size=60)
                    st.caption(f"Currently near {pos['current_hub_label']}")
