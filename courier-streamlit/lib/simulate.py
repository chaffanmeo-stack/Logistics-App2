"""
Simulated GPS / IoT movement for Trips.

No real hardware — a Trip's position is always *calculated* from how
much time has passed since it started, not stored. This means it's
always correct and "live" the moment it's read, with zero background
jobs needed (which free hosting doesn't offer anyway).

sync_trip_progress() is the piece that makes the whole system feel
automatic: call it whenever a Trip is viewed (Owner/Hub dashboards),
and it will:
  1. Figure out, from elapsed time, which hub(s) the trip has reached
     since we last checked.
  2. Drop off any packages destined for a newly-reached hub.
  3. Pick up any waiting ("Booked") packages at that hub whose
     destination is further along this same trip's route.
  4. Save the trip's new progress so we don't redo this next time.
"""

from datetime import datetime, timezone

HUB_COORDS = {
    "Lahore": (31.5497, 74.3436),
    "Multan": (30.1575, 71.5249),
    "Lodhran": (29.5406, 71.6327),
    "BWP": (29.3956, 71.6833),
    "RYK": (28.4202, 70.2952),
}


def _now():
    return datetime.now(timezone.utc)


def trip_path(trip: dict) -> list[str]:
    """Full ordered list of hubs this trip visits, origin included."""
    return [trip["origin_hub"]] + list(trip["route"])


def compute_trip_position(trip: dict) -> dict:
    """Pure calculation, no DB writes. Returns current leg index,
    progress within that leg (0-1), lat/lon, and whether it's finished."""
    path = trip_path(trip)
    total_legs = len(path) - 1

    started_at = trip["started_at"]
    if isinstance(started_at, str):
        started_at = datetime.fromisoformat(started_at.replace("Z", "+00:00"))

    elapsed_minutes = (_now() - started_at).total_seconds() / 60.0
    minutes_per_leg = trip["minutes_per_leg"]

    raw_leg = elapsed_minutes / minutes_per_leg if minutes_per_leg > 0 else total_legs
    current_leg = min(int(raw_leg), total_legs - 1) if total_legs > 0 else 0
    is_complete = raw_leg >= total_legs

    if is_complete:
        lat, lon = HUB_COORDS[path[-1]]
        progress = 1.0
    else:
        progress = raw_leg - current_leg
        a_hub, b_hub = path[current_leg], path[current_leg + 1]
        a_lat, a_lon = HUB_COORDS[a_hub]
        b_lat, b_lon = HUB_COORDS[b_hub]
        lat = a_lat + (b_lat - a_lat) * progress
        lon = a_lon + (b_lon - a_lon) * progress

    return {
        "current_leg": current_leg,
        "progress_in_leg": progress,
        "lat": lat,
        "lon": lon,
        "is_complete": is_complete,
        "path": path,
        "current_hub_label": path[current_leg] if progress < 1 else path[current_leg + 1] if not is_complete else path[-1],
    }


def sync_trip_progress(sb, trip: dict) -> None:
    """Call this whenever a trip is displayed. Advances packages past
    each hub the trip has (virtually) reached since the last check."""
    if trip["status"] != "In Progress":
        return

    pos = compute_trip_position(trip)
    path = pos["path"]
    stored_leg = trip["current_leg_index"]
    reached_leg = pos["current_leg"] if not pos["is_complete"] else len(path) - 1

    # Walk forward one hub at a time from where we last checked,
    # so nothing gets skipped even if the app wasn't opened for a while.
    leg = stored_leg
    while leg < reached_leg or (pos["is_complete"] and leg < len(path) - 1):
        leg += 1
        hub = path[leg]
        is_final_hub = leg == len(path) - 1

        # 1. Drop off packages on this trip destined for this hub
        sb.table("packages").update(
            {"status": "Reached Hub", "current_hub": hub, "trip_id": None}
        ).eq("trip_id", trip["id"]).eq("destination_hub", hub).execute()

        # 2. Pick up waiting packages at this hub headed further down the route
        if not is_final_hub:
            remaining_route = path[leg + 1:]
            waiting = (
                sb.table("packages")
                .select("id, destination_hub")
                .eq("current_hub", hub)
                .eq("status", "Booked")
                .execute()
            ).data
            pickup_ids = [p["id"] for p in waiting if p["destination_hub"] in remaining_route]
            if pickup_ids:
                sb.table("packages").update(
                    {"status": "In Transit", "trip_id": trip["id"], "current_hub": None}
                ).in_("id", pickup_ids).execute()

    new_status = "Completed" if pos["is_complete"] else "In Progress"
    if leg != stored_leg or new_status != trip["status"]:
        sb.table("trips").update({"current_leg_index": leg, "status": new_status}).eq("id", trip["id"]).execute()
