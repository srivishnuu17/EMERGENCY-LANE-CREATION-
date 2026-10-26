import json
import math
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

import streamlit as st
import streamlit.components.v1 as components
from supabase import create_client


st.set_page_config(
    page_title="AI Emergency Lane · Bengaluru",
    page_icon="🚑",
    layout="wide",
)

tracking_component = components.declare_component(
    "emergency_lane_tracking",
    path=str(Path(__file__).parent / "tracking_component"),
)

st.markdown(
    """
    <style>
    .stApp { background:#090e11; color:#edf4f5; }
    .block-container { max-width:1500px; padding-top:1.5rem; }
    h1,h2,h3,p,label { color:#edf4f5; }
    p, .stCaption { color:#91a6ad; }
    div[data-testid="stMetric"] {
      background:#121a1d; border:1px solid #293639;
      border-radius:10px; padding:16px;
    }
    div[data-testid="stMetricLabel"] { color:#91aab2; }
    div[data-testid="stMetricValue"] { color:#f2f7f7; }
    div.stButton > button {
      background:#62d6ae; color:#07120f; border:0;
      border-radius:6px; font-weight:700; min-height:42px;
    }
    .panel {
      background:#121a1d; border:1px solid #293639;
      border-radius:10px; padding:18px; margin-bottom:14px;
    }
    .kicker { color:#85a3ac; font-size:11px; letter-spacing:2px; }
    .muted { color:#91a6ad; font-size:12px; }
    </style>
    """,
    unsafe_allow_html=True,
)


def get_value(row, *keys, default="—"):
    """Return the first non-empty value among possible mission column names."""
    lowered = {str(key).lower(): value for key, value in row.items()}
    for key in keys:
        value = lowered.get(key.lower())
        if value not in (None, ""):
            return str(value)
    return default


def mission_route(mission):
    origin = str(mission.get("origin_label") or "—")
    destination = str(mission.get("destination_label") or "—")
    return f"{origin} → {destination}"


def valid_position(lng, lat):
    try:
        lng, lat = float(lng), float(lat)
        if math.isfinite(lng) and math.isfinite(lat) and -180 <= lng <= 180 and -90 <= lat <= 90:
            return [lng, lat]
    except (TypeError, ValueError):
        pass
    return None


def decode_polyline(value):
    """Decode the common Google encoded-polyline string into [lng, lat] pairs."""
    points, index, lat, lng = [], 0, 0, 0
    try:
        while index < len(value):
            deltas = []
            for _ in range(2):
                result, shift = 0, 0
                while True:
                    byte = ord(value[index]) - 63
                    index += 1
                    result |= (byte & 0x1f) << shift
                    shift += 5
                    if byte < 0x20:
                        break
                    if index >= len(value) or shift > 35:
                        return []
                deltas.append(~(result >> 1) if result & 1 else result >> 1)
            lat += deltas[0]
            lng += deltas[1]
            points.append([lng / 1e5, lat / 1e5])
    except (IndexError, TypeError):
        return []
    return points if len(points) >= 2 and all(valid_position(*p) for p in points) else []


def route_coordinates(value):
    """Accept GeoJSON LineString/Feature, coordinate arrays, or encoded polyline."""
    if not value:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return decode_polyline(value)
    if isinstance(value, dict):
        if value.get("type") == "Feature":
            value = value.get("geometry") or {}
        if value.get("type") == "LineString":
            value = value.get("coordinates", [])
        elif "coordinates" in value:
            value = value["coordinates"]
        elif "route_polyline" in value:
            return route_coordinates(value["route_polyline"])
    if isinstance(value, list) and value and isinstance(value[0], dict):
        value = [[p.get("lng", p.get("lon")), p.get("lat")] for p in value]
    if isinstance(value, list):
        points = [valid_position(*p[:2]) for p in value if isinstance(p, (list, tuple)) and len(p) >= 2]
        if len(points) >= 2 and all(points):
            return points
    return []


def mission_map_data(mission):
    route = route_coordinates(mission.get("route_polyline"))
    origin = valid_position(mission.get("origin_lng"), mission.get("origin_lat"))
    destination = valid_position(mission.get("destination_lng"), mission.get("destination_lat"))
    has_saved_route = bool(route)
    if route:
        origin = origin or route[0]
        destination = destination or route[-1]
    if not route and origin and destination:
        route = [origin, destination]
    ambulance = None
    for lng_key, lat_key in (("ambulance_lng", "ambulance_lat"), ("vehicle_lng", "vehicle_lat"), ("current_lng", "current_lat"), ("driver_lng", "driver_lat"), ("last_lng", "last_lat")):
        ambulance = valid_position(mission.get(lng_key), mission.get(lat_key))
        if ambulance:
            break
    return {"route": route, "has_saved_route": has_saved_route, "origin": origin, "destination": destination, "ambulance": ambulance}


def location_age_seconds(location):
    if not location or not location.get("captured_at"):
        return None
    try:
        captured = datetime.fromisoformat(str(location["captured_at"]).replace("Z", "+00:00"))
        if captured.tzinfo is None:
            captured = captured.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - captured).total_seconds())
    except (TypeError, ValueError):
        return None


def nearest_route_progress(route, position):
    """Return nearest distance and along-route distance in metres."""
    if len(route) < 2 or not position:
        return None
    earth = 6371000.0
    reference_lat = math.radians(position[1])

    def xy(point):
        return (earth * math.radians(point[0]) * math.cos(reference_lat), earth * math.radians(point[1]))

    px, py = xy(position)
    cumulative, best = 0.0, None
    for start, end in zip(route, route[1:]):
        ax, ay = xy(start)
        bx, by = xy(end)
        dx, dy = bx - ax, by - ay
        length = math.hypot(dx, dy)
        if not length:
            continue
        t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (length * length)))
        distance = math.hypot(px - (ax + t * dx), py - (ay + t * dy))
        if best is None or distance < best[0]:
            best = (distance, cumulative + t * length)
        cumulative += length
    return best


def junction_map_data(route, location, junctions):
    age = location_age_seconds(location)
    position = valid_position(location.get("longitude"), location.get("latitude")) if location else None
    progress = nearest_route_progress(route, position) if position else None
    try:
        accuracy = float(location.get("accuracy_m")) if location else math.inf
    except (TypeError, ValueError):
        accuracy = math.inf
    reliable = bool(route) and progress is not None and progress[0] <= 100 and age is not None and age <= 30 and math.isfinite(accuracy) and accuracy <= 50
    result = []
    for junction in junctions or []:
        point = valid_position(junction.get("longitude"), junction.get("latitude"))
        if not point:
            continue
        item = {"name": junction.get("name") or "Junction", "coordinates": point, "traffic_status": junction.get("status"), "progress": None}
        along = nearest_route_progress(route, point) if route else None
        if reliable and along and along[0] <= 40:
            delta = along[1] - progress[1]
            item["progress"] = "current" if abs(delta) <= 75 else ("upcoming" if delta > 0 else "passed")
        result.append(item)
    return result, reliable


def render_tracking_map(mission, key, location=None, junctions=None, gps_enabled=False, polling=False, gps_message="", realtime=None):
    source = mission_map_data(mission) if mission else {"route": [], "has_saved_route": False, "origin": None, "destination": None}
    if source["has_saved_route"]:
        route_kind = "saved"
    elif source["origin"] and source["destination"]:
        route_kind = "endpoints"
    else:
        route_kind = "unavailable"
    ambulance = None
    if location:
        point = valid_position(location.get("longitude"), location.get("latitude"))
        if point:
            age = location_age_seconds(location)
            ambulance = {"coordinates": point, "captured_at": location.get("captured_at"), "accuracy_m": location.get("accuracy_m"), "stale": age is None or age > 30}
    usable_route = source["route"] if route_kind == "saved" else []
    junctions_for_map, junction_progress_available = junction_map_data(usable_route, location, junctions)
    payload = {"route": usable_route, "route_kind": route_kind, "origin": source["origin"], "destination": source["destination"], "ambulance": ambulance, "junctions": junctions_for_map, "junction_progress_available": junction_progress_available, "gps_enabled": gps_enabled, "gps_controls": gps_message != "", "gps_message": gps_message, "polling": polling, "realtime": realtime, "mission_name": (mission or {}).get("mission_code") or "Selected mission"}
    result = tracking_component(data=payload, key=key, default=None)
    if route_kind == "endpoints":
        st.info("Saved endpoints are shown without a connecting line. This mission has no road-route geometry; use Google Maps directions after the mission is active.")
    elif route_kind == "unavailable":
        st.warning("Route unavailable: this mission has no valid saved geometry or complete endpoint coordinates.")
    if junctions and not junction_progress_available:
        st.caption("Junctions are shown without passed/current/upcoming labels because a saved route and a fresh, accurate GPS fix are needed to determine progress.")
    if location:
        age = location_age_seconds(location)
        if age is None or age > 30:
            st.warning("The newest GPS location is stale or has an invalid timestamp. The marker is shown as stale.")
        else:
            st.caption(f"GPS updated {int(age)} seconds ago.")
    elif mission:
        st.info("Live ambulance position unavailable: no saved GPS location exists for this mission.")
    if mission:
        directions_url = google_maps_directions_url(mission, location)
        if directions_url:
            st.link_button("Open driving directions in Google Maps", directions_url, use_container_width=True)
            st.caption("Google Maps calculates road directions from the latest fresh GPS fix or the saved mission origin. This external link does not draw a route in the embedded map.")
    st.caption("Map data Â© OpenStreetMap contributors Â· Â© CARTO Â· MapLibre GL JS")
    return result


def render_mission_table(missions):
    rows = []
    for mission in missions:
        rows.append(
            {
                "Mission": mission.get("mission_code") or mission.get("id"),
                "Origin": mission.get("origin_label") or "—",
                "Destination": mission.get("destination_label") or "—",
                "Status": mission.get("status") or "—",
            }
        )
    st.dataframe(rows, hide_index=True, use_container_width=True)


ACTIVE_MISSION_STATUSES = {"active", "approved", "accepted", "assigned", "dispatched", "en route", "en_route", "in_progress", "in progress"}


def is_active_mission(mission):
    status = str(mission.get("status") or "").strip().lower()
    return status in ACTIVE_MISSION_STATUSES


def fetch_latest_location(supabase, mission_id, response_unit_id):
    if not mission_id or not response_unit_id:
        return None, None
    try:
        response = (supabase.table("current_locations")
            .select("latitude, longitude, captured_at, accuracy_m")
            .eq("mission_id", mission_id)
            .eq("response_unit_id", response_unit_id)
            .order("captured_at", desc=True)
            .limit(1)
            .execute())
        rows = response.data or []
        return (rows[0] if rows else None), None
    except Exception as error:
        return None, error


def fetch_junctions(supabase):
    try:
        response = (supabase.table("junctions")
            .select("id, name, latitude, longitude, status, updated_at")
            .execute())
        return response.data or [], None
    except Exception as error:
        return [], error


def process_driver_event(event, supabase, response_unit, mission):
    if not isinstance(event, dict) or not event.get("event_id"):
        return
    if event["event_id"] == st.session_state.get("last_location_component_event"):
        return
    st.session_state.last_location_component_event = event["event_id"]
    kind = event.get("kind")
    if kind == "share_start":
        st.session_state.location_sharing = True
        st.session_state.location_sharing_mission_id = (mission or {}).get("id")
        st.session_state.location_sharing_status = "Waiting for browser GPS permission and a current location fix."
        return
    if kind == "share_stop":
        st.session_state.location_sharing = False
        st.session_state.location_sharing_mission_id = None
        st.session_state.location_sharing_status = "Location sharing is stopped."
        return
    if kind == "gps_error":
        st.session_state.location_sharing_status = event.get("message") or "GPS is unavailable."
        st.session_state.location_sharing = False
        st.session_state.location_sharing_mission_id = None
        return
    if kind != "gps":
        return
    if not st.session_state.get("location_sharing"):
        st.session_state.location_sharing_status = "GPS fix ignored because location sharing is off."
        return
    if not response_unit or not mission or not is_active_mission(mission):
        st.session_state.location_sharing_status = "GPS fix not saved: no assigned response unit and active mission are selected."
        return
    if st.session_state.get("location_sharing_mission_id") != mission.get("id"):
        st.session_state.location_sharing_status = "GPS fix not saved: the active mission changed. Stop and start sharing for the selected mission."
        st.session_state.location_sharing = False
        return
    point = valid_position(event.get("longitude"), event.get("latitude"))
    try:
        captured_ms = float(event.get("captured_at_ms"))
        captured = datetime.fromtimestamp(captured_ms / 1000, tz=timezone.utc)
        age = (datetime.now(timezone.utc) - captured).total_seconds()
    except (TypeError, ValueError, OverflowError, OSError):
        point, age, captured = None, None, None
    if not point or age is None or age < -15 or age > 120:
        st.session_state.location_sharing_status = "GPS fix ignored because its coordinates or captured time are invalid or stale."
        return
    payload = {
        "response_unit_id": response_unit["id"],
        "mission_id": mission["id"],
        "latitude": point[1],
        "longitude": point[0],
        "captured_at": captured.isoformat(),
    }
    try:
        accuracy = float(event.get("accuracy_m"))
        if math.isfinite(accuracy) and accuracy >= 0:
            payload["accuracy_m"] = accuracy
    except (TypeError, ValueError):
        pass
    try:
        supabase.table("current_locations").insert(payload).execute()
        st.session_state.location_sharing_status = f"GPS saved at {captured.astimezone().strftime('%H:%M:%S')} local time."
    except Exception as error:
        st.session_state.location_sharing_status = "GPS was received but Supabase rejected the write. Check current_locations RLS INSERT access for the assigned driver and response unit."
        st.session_state.location_sharing_error = str(error)


def google_maps_directions_url(mission, current_location=None):
    if not mission:
        return None
    current_age = location_age_seconds(current_location)
    live_origin = None
    if current_location and current_age is not None and current_age <= 60:
        live_origin = valid_position(current_location.get("longitude"), current_location.get("latitude"))
    saved_origin = valid_position(mission.get("origin_lng"), mission.get("origin_lat"))
    saved_destination = valid_position(mission.get("destination_lng"), mission.get("destination_lat"))
    origin = live_origin or saved_origin or str(mission.get("origin_label") or "").strip()
    destination = saved_destination or str(mission.get("destination_label") or "").strip()
    if not origin or not destination:
        return None
    params = {"api": "1", "origin": ",".join(map(str, origin)) if isinstance(origin, list) else origin,
              "destination": ",".join(map(str, destination)) if isinstance(destination, list) else destination,
              "travelmode": "driving", "dir_action": "navigate"}
    return "https://www.google.com/maps/dir/?" + urlencode(params)


def render_control_room(missions, supabase):
    st.markdown(
        "<p style='letter-spacing:3px;color:#62d6ae'>◆ AI EMERGENCY LANE · BENGALURU</p>",
        unsafe_allow_html=True,
    )
    st.title("Emergency response system")
    st.caption("Police Control Room · live missions visible to your account")

    st.markdown(
        "<div class='panel'><span class='kicker'>MISSION OVERVIEW</span></div>",
        unsafe_allow_html=True,
    )
    one, two, three, four = st.columns(4)
    one.metric("Missions visible", len(missions))
    active = sum(
        get_value(m, "status", "mission_status", default="").lower()
        in {"active", "approved", "accepted", "en route", "in_progress", "in progress"}
        for m in missions
    )
    two.metric("Active missions", active)
    three.metric(
        "Missions with origin",
        sum(1 for m in missions if str(m.get("origin_label") or "").strip()),
    )
    four.metric("Status values", len({str(m.get("status") or "") for m in missions if m.get("status")}))

    left, right = st.columns([1.8, 1])
    selected_index = 0
    if missions:
        selected_index = st.selectbox(
            "Selected mission for map",
            options=range(len(missions)),
            format_func=lambda index: f"{missions[index].get('mission_code') or missions[index].get('id')} · {mission_route(missions[index])}",
            key="selected_mission_index",
        )
    selected_mission = missions[selected_index] if missions else None
    latest_location, location_error = (None, None)
    junctions, junction_error = ([], None)
    if selected_mission and selected_mission.get("response_unit_id"):
        latest_location, location_error = fetch_latest_location(supabase, selected_mission.get("id"), selected_mission.get("response_unit_id"))
    junctions, junction_error = fetch_junctions(supabase)
    with left:
        st.markdown(
            "<div class='panel'><span class='kicker'>CORRIDOR PROGRESS · DATABASE MISSIONS</span></div>",
            unsafe_allow_html=True,
        )
        if missions:
            featured = selected_mission
            st.markdown(
                f"<div class='panel'><span class='kicker'>PROPOSED CORRIDOR</span>"
                f"<span style='float:right;color:#62d6ae'>{featured.get('status') or '—'}</span>"
                f"<h3>{mission_route(featured)}</h3></div>",
                unsafe_allow_html=True,
            )
            render_mission_table(missions)
        else:
            st.info("No missions are currently available to your account.")
        st.markdown("<div class='panel'><span class='kicker'>MISSION MAP</span></div>", unsafe_allow_html=True)
        realtime = None
        if selected_mission and selected_mission.get("response_unit_id") and st.session_state.get("supabase_access_token"):
            realtime = {
                "url": st.secrets["SUPABASE_URL"],
                "key": st.secrets["SUPABASE_PUBLISHABLE_KEY"],
                "access_token": st.session_state.supabase_access_token,
                "mission_id": str(selected_mission["id"]),
            }
        render_tracking_map(selected_mission, "control_map", latest_location, junctions, polling=True, realtime=realtime)
        st.caption("Control Room locations update from Supabase Realtime when the project publication and read policy allow it; otherwise the map polls every 8 seconds.")
        if location_error:
            st.warning("Could not read current_locations. Check the authenticated Control Room SELECT policy for this mission and response unit.")
        if junction_error:
            st.warning("Could not read junctions. Check the authenticated SELECT policy on the junctions table.")
    with right:
        st.markdown(
            "<div class='panel'><span class='kicker'>MISSION DETAILS</span><h3>Database status</h3>"
            "<small>Mission data is filtered by your Supabase access policies.</small></div>",
            unsafe_allow_html=True,
        )
        if missions:
            featured = selected_mission
            st.markdown(
                f"<div class='panel'><span class='muted'>MISSION</span><h3>{featured.get('mission_code') or featured.get('id')}</h3>"
                f"<b>{mission_route(featured)}</b><br><small>{featured.get('status') or '—'}</small></div>",
                unsafe_allow_html=True,
            )
            if str(featured.get("status") or "").strip().lower() == "proposed":
                if st.button("Approve selected mission", key="approve_selected_mission"):
                    try:
                        update = (supabase.table("missions")
                            .update({"status": "approved"})
                            .eq("id", featured["id"])
                            .select("id, status")
                            .single()
                            .execute())
                        if update.data:
                            st.success("Mission approved. The assigned driver can now start GPS sharing.")
                            st.rerun()
                        else:
                            st.error("Mission activation returned no updated row. Check the existing missions_update_control RLS policy.")
                    except Exception as error:
                        st.error("Could not activate the mission. Check the existing Control Room missions UPDATE policy.")
                        st.caption(str(error))


def render_driver(missions, supabase, user_id):
    st.markdown("<p class='kicker'>AMBULANCE DRIVER DASHBOARD</p>", unsafe_allow_html=True)
    st.header("Emergency corridor navigation")
    st.caption("Missions and response units are limited by your signed-in Supabase access.")

    queue, map_area, details = st.columns([0.9, 2.1, 0.9])
    response_units, unit_error = [], None
    try:
        response = (supabase.table("response_units")
            .select("id, driver_id, unit_code, call_sign, availability")
            .eq("driver_id", user_id)
            .execute())
        response_units = response.data or []
    except Exception as error:
        unit_error = error

    with queue:
        st.markdown("<div class='panel'><span class='kicker'>ASSIGNED RESPONSE UNIT</span></div>", unsafe_allow_html=True)
        response_unit = None
        if unit_error:
            st.error("Could not load your response unit. Check the authenticated SELECT policy on response_units.")
        elif not response_units:
            st.warning("No response unit is assigned to this signed-in driver. Location sharing is unavailable.")
        elif len(response_units) == 1:
            response_unit = response_units[0]
            st.markdown(f"**{response_unit.get('call_sign') or response_unit.get('unit_code') or response_unit['id']}** · {response_unit.get('availability') or 'availability unknown'}")
        else:
            unit_index = st.selectbox("Your response unit", range(len(response_units)), format_func=lambda i: response_units[i].get("call_sign") or response_units[i].get("unit_code") or response_units[i]["id"], key="driver_response_unit_index", disabled=bool(st.session_state.get("location_sharing")))
            response_unit = response_units[unit_index]

        assigned_missions = [m for m in missions if response_unit and str(m.get("response_unit_id")) == str(response_unit.get("id"))]
        st.markdown("<div class='panel'><span class='kicker'>ASSIGNED MISSIONS</span></div>", unsafe_allow_html=True)
        selected_mission = None
        if assigned_missions:
            selected_index = st.selectbox(
                "Selected mission",
                options=range(len(assigned_missions)),
                format_func=lambda i: f"{assigned_missions[i].get('mission_code') or assigned_missions[i].get('id')} · {mission_route(assigned_missions[i])}",
                key="driver_active_mission_index",
                disabled=bool(st.session_state.get("location_sharing")),
            )
            selected_mission = assigned_missions[selected_index]
            for i, mission in enumerate(assigned_missions):
                label = "SELECTED MISSION" if i == selected_index else "ASSIGNED"
                st.markdown(f"<div class='panel'><span style='color:#62d6ae'>{label}</span><h3>{mission.get('mission_code') or mission.get('id')}</h3><b>{mission_route(mission)}</b><br><small>{mission.get('status') or '—'}</small></div>", unsafe_allow_html=True)
        else:
            st.info("No mission is assigned to this response unit.")

    active = bool(selected_mission and is_active_mission(selected_mission))
    can_share = bool(response_unit and active and not unit_error)
    if can_share:
        gps_message = f"Share actual browser GPS with {response_unit.get('call_sign') or response_unit.get('unit_code') or 'this response unit'} for the selected active mission."
    elif not response_unit:
        gps_message = "Location sharing unavailable: no assigned response unit is available."
    elif not selected_mission:
        gps_message = "Location sharing unavailable: select an assigned mission first."
    else:
        gps_message = f"Mission status is '{selected_mission.get('status') or 'unknown'}'. Ask the Control Room to activate it before sharing GPS."

    latest_location, location_error = (None, None)
    if selected_mission and response_unit:
        latest_location, location_error = fetch_latest_location(supabase, selected_mission.get("id"), response_unit.get("id"))
    with map_area:
        st.markdown("<div class='panel'><span class='kicker'>BENGALURU LIVE MAP</span></div>", unsafe_allow_html=True)
        event = render_tracking_map(selected_mission, "driver_tracking_map", latest_location, gps_enabled=can_share, polling=True, gps_message=gps_message)
        process_driver_event(event, supabase, response_unit, selected_mission)
        if selected_mission and not active:
            status = str(selected_mission.get("status") or "unknown")
            st.warning(f"This mission is '{status}', not active. Location sharing is disabled until the Control Room activates it; the driver role cannot change mission status under the current access rules.")
        status_message = st.session_state.get("location_sharing_status")
        if status_message:
            if st.session_state.get("location_sharing_error"):
                st.error(status_message)
                st.caption(st.session_state.location_sharing_error)
                st.session_state.pop("location_sharing_error", None)
            elif "not saved" in status_message.lower() or "ignored" in status_message.lower():
                st.warning(status_message)
            else:
                st.caption(status_message)
        if st.session_state.get("location_sharing") and active:
            st.caption("Location sharing is on. The Google Maps button above will use the most recent GPS position after the next dashboard refresh.")
        if location_error:
            st.warning("Could not read current_locations. Check the authenticated SELECT policy for your assigned response unit and mission.")

    with details:
        if selected_mission:
            st.metric("Mission", selected_mission.get("mission_code") or selected_mission.get("id"))
            st.metric("Status", selected_mission.get("status") or "—")
            st.markdown("<div class='panel'><span class='kicker'>GPS SHARING</span><p>Use Start location sharing to grant browser permission and send real GPS fixes. Stop sharing at any time.</p></div>", unsafe_allow_html=True)
        else:
            st.metric("Missions", "0")


def main():
    st.markdown(
        "<p style='letter-spacing:3px;color:#62d6ae'>◆ AI EMERGENCY LANE · BENGALURU</p>",
        unsafe_allow_html=True,
    )
    st.title("Emergency response system")

    try:
        supabase_url = st.secrets["SUPABASE_URL"]
        publishable_key = st.secrets["SUPABASE_PUBLISHABLE_KEY"]
        supabase = create_client(supabase_url, publishable_key)
    except Exception as error:
        st.error(f"Supabase settings could not be loaded. Check .streamlit/secrets.toml. Details: {error}")
        st.stop()

    if st.session_state.get("supabase_access_token") and st.session_state.get("supabase_refresh_token"):
        try:
            supabase.auth.set_session(
                st.session_state.supabase_access_token,
                st.session_state.supabase_refresh_token,
            )
        except Exception:
            st.session_state.pop("supabase_access_token", None)
            st.session_state.pop("supabase_refresh_token", None)
            st.session_state.pop("supabase_user_id", None)
            st.session_state.pop("location_sharing", None)
            st.session_state.pop("location_sharing_mission_id", None)

    if not st.session_state.get("supabase_user_id"):
        st.caption("Sign in with your account to open its role dashboard.")
        with st.form("supabase_login"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign in")
        if submitted:
            if not email.strip() or not password:
                st.error("Enter both your email and password.")
                st.stop()
            try:
                result = supabase.auth.sign_in_with_password(
                    {"email": email.strip(), "password": password}
                )
                if not result.user or not result.session:
                    st.error("Sign-in did not return a user session. Check your credentials and try again.")
                    st.stop()
                st.session_state.supabase_access_token = result.session.access_token
                st.session_state.supabase_refresh_token = result.session.refresh_token
                st.session_state.supabase_user_id = result.user.id
                st.rerun()
            except Exception as error:
                st.error(f"Sign-in failed. Check your email and password. Details: {error}")
        st.stop()

    if st.button("Sign out"):
        try:
            supabase.auth.sign_out()
        except Exception:
            pass
        for key in ("supabase_access_token", "supabase_refresh_token", "supabase_user_id", "location_sharing", "location_sharing_mission_id", "location_sharing_status"):
            st.session_state.pop(key, None)
        st.rerun()

    try:
        profile_response = (
            supabase.table("profiles")
            .select("display_name, role")
            .eq("id", st.session_state.supabase_user_id)
            .single()
            .execute()
        )
        profile = profile_response.data
        if not profile:
            st.error("Your account has no profile row. Ask an administrator to configure your profile.")
            st.stop()
    except Exception as error:
        st.error(f"Could not load your profile. Check your account access and try again. Details: {error}")
        st.stop()

    role = str(profile.get("role", "")).strip().lower().replace("-", "_").replace(" ", "_")
    if role in {"police", "control_room", "police_control_room", "admin", "dispatcher"}:
        dashboard = "control"
    elif role in {"ambulance", "driver", "ambulance_driver"}:
        dashboard = "driver"
    else:
        st.error(f"Your profile role ({profile.get('role') or 'missing'}) is not configured for a dashboard.")
        st.stop()

    display_name = profile.get("display_name")
    if display_name:
        st.caption(f"Signed in as {display_name} · {profile['role']}")

    try:
        missions_response = (
            supabase.table("missions")
            .select("id, mission_code, origin_label, destination_label, origin_lat, origin_lng, destination_lat, destination_lng, route_polyline, response_unit_id, status")
            .execute()
        )
        missions = missions_response.data or []
    except Exception as error:
        st.error(f"Could not load missions from Supabase. Check your database connection and RLS access. Details: {error}")
        st.stop()

    if dashboard == "control":
        render_control_room(missions, supabase)
    else:
        render_driver(missions, supabase, st.session_state.supabase_user_id)

    st.divider()
    st.caption("Demonstration interface · mission visibility follows Supabase row-level security policies")


main()
