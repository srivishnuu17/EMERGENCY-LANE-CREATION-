import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
from supabase import create_client

# Configure page
st.set_page_config(
    page_title="EMERGENCY LANE CREATOR · Bengaluru",
    page_icon="🚑",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Custom Global CSS
st.markdown(
    """
    <style>
    #MainMenu { visibility: hidden; }
    header { visibility: hidden; }
    footer { visibility: hidden; }
    .stDeployButton { display: none; }
    
    .stApp {
        background-color: #060b13 !important;
        color: #edf4f5 !important;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    .block-container {
        max-width: 100% !important;
        padding-top: 0.35rem !important;
        padding-bottom: 0.5rem !important;
        padding-left: 0.75rem !important;
        padding-right: 0.75rem !important;
    }
    div.stButton > button {
        border-radius: 8px !important;
        font-weight: 700 !important;
        font-size: 13px !important;
        height: 38px !important;
        transition: all 0.2s ease !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Initialize Supabase client
try:
    supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_PUBLISHABLE_KEY"])
except Exception as e:
    st.error(f"Supabase credentials error in .streamlit/secrets.toml: {e}")
    st.stop()

# Shared local state file for full-stack persistence
STATE_FILE = Path("bengaluru_live_state.json")

def load_live_state():
    default_state = {
        "city": "Bengaluru",
        "mission_code": "BLR-EM-4092",
        "status": "ACTIVE - CRITICAL",
        "unit_id": "KA-01-EM-4092",
        "destination": "Victoria Hospital (City Market)",
        "destination_key": "victoria",
        "eta_min": 4,
        "eta_sec": 12,
        "distance_km": 1.8,
        "progress_pct": 82,
        "speed_kph": 55,
        "speed_multiplier": 2,
        "is_paused": False,
        "active_route_id": 1,
        "last_updated": datetime.now(timezone.utc).isoformat()
    }
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r") as f:
                saved = json.load(f)
                default_state.update(saved)
        except Exception:
            pass
    return default_state

def save_live_state(state):
    state["last_updated"] = datetime.now(timezone.utc).isoformat()
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except Exception:
        pass

# Authentication session state
if "user_authenticated" not in st.session_state:
    st.session_state.user_authenticated = False
if "user_email" not in st.session_state:
    st.session_state.user_email = ""
if "user_role" not in st.session_state:
    st.session_state.user_role = ""

live_state = load_live_state()

# -------------------------------------------------------------------------------------------------
# STRICT SUPABASE AUTHENTICATION PAGE
# -------------------------------------------------------------------------------------------------
if not st.session_state.user_authenticated:
    st.markdown(
        """
        <div style="text-align:center; margin-top:40px;">
            <div style="font-size:42px; margin-bottom:6px;">🚑 ⚡ 🚓</div>
            <h1 style="font-size:26px; font-weight:900; letter-spacing:2px; color:#ffffff; margin-bottom:4px;">EMERGENCY LANE CREATOR</h1>
            <p style="color:#8da4be; font-size:13px; letter-spacing:1px;">BENGALURU METROPOLITAN TRAFFIC MANAGEMENT SYSTEM</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_center = st.columns([1, 1.2, 1])[1]
    with col_center:
        st.markdown(
            """
            <div style="background:#09121f; border:1px solid #1a2d45; border-radius:12px; padding:28px 24px; margin-top:20px; box-shadow:0 8px 30px rgba(0,0,0,0.6);">
                <div style="font-size:14px; font-weight:800; color:#00e676; letter-spacing:1px; margin-bottom:14px;">VERIFIED SUPABASE SIGN IN</div>
            """,
            unsafe_allow_html=True,
        )

        with st.form("strict_supabase_login"):
            email_input = st.text_input("Registered Email", placeholder="driver@bengaluru.gov.in")
            password_input = st.text_input("Password", type="password", placeholder="••••••••")
            role_choice = st.selectbox("Role Assignment", ["Ambulance Driver", "Police Control Room Officer"])
            sign_in_clicked = st.form_submit_button("Sign In with Supabase", use_container_width=True)

        if sign_in_clicked:
            if not email_input.strip() or not password_input:
                st.error("Please enter both your registered email and password.")
            else:
                try:
                    # STRICT AUTHENTICATION AGAINST SUPABASE
                    auth_result = supabase.auth.sign_in_with_password({
                        "email": email_input.strip(),
                        "password": password_input
                    })

                    if not auth_result.user or not auth_result.session:
                        st.error("❌ Authentication Failed: Invalid credentials returned by Supabase.")
                        st.stop()

                    user_id = auth_result.user.id
                    
                    # Query user role from Supabase profiles table
                    profile_query = supabase.table("profiles").select("role, display_name").eq("id", user_id).execute()
                    
                    if profile_query.data and len(profile_query.data) > 0 and profile_query.data[0].get("role"):
                        assigned_role = str(profile_query.data[0]["role"]).strip().lower()
                    else:
                        # Auto-assign selected role into Supabase profiles
                        assigned_role = "police" if "police" in role_choice.lower() else "driver"
                        try:
                            supabase.table("profiles").upsert({
                                "id": user_id,
                                "display_name": email_input.split("@")[0].title(),
                                "role": assigned_role
                            }).execute()
                        except Exception:
                            pass

                    # Enforce strict role assignment
                    if "police" in assigned_role or "control" in assigned_role:
                        st.session_state.user_role = "police"
                    else:
                        st.session_state.user_role = "driver"

                    st.session_state.user_authenticated = True
                    st.session_state.user_email = email_input.strip()
                    st.rerun()

                except Exception as err:
                    st.error(f"❌ Access Denied: {err}. Please verify your registered Supabase credentials.")
                    st.stop()

        st.markdown(
            """
                <hr style="border:0; border-top:1px solid #162438; margin:20px 0;">
                <div style="font-size:11px; font-weight:700; color:#8da4be; margin-bottom:8px; text-transform:uppercase;">Need an account?</div>
            """,
            unsafe_allow_html=True,
        )
        
        with st.expander("Register New Account in Supabase"):
            reg_email = st.text_input("New Email", key="reg_email")
            reg_password = st.text_input("New Password", type="password", key="reg_pass")
            reg_role = st.selectbox("Assign Role", ["Ambulance Driver", "Police Control Room"], key="reg_role")
            if st.button("Register in Supabase", use_container_width=True):
                if reg_email and reg_password:
                    try:
                        res = supabase.auth.sign_up({"email": reg_email.strip(), "password": reg_password})
                        if res.user:
                            assigned_r = "police" if "police" in reg_role.lower() else "driver"
                            supabase.table("profiles").upsert({
                                "id": res.user.id,
                                "display_name": reg_email.split("@")[0].title(),
                                "role": assigned_r
                            }).execute()
                            st.success(f"Registered successfully as {reg_role}! Please sign in above.")
                    except Exception as e:
                        st.error(f"Registration error: {e}")

        st.markdown("</div>", unsafe_allow_html=True)
    st.stop()


# -------------------------------------------------------------------------------------------------
# AUTHENTICATED TOP HEADER (STRICT ROLE LOCK)
# -------------------------------------------------------------------------------------------------
col_logo, col_role_info, col_logout = st.columns([1.3, 2.0, 0.9])

with col_logo:
    st.markdown(
        """
        <div style="display:flex; align-items:center; gap:10px; padding-top:4px;">
            <div style="font-size:22px;">⚡</div>
            <div>
                <span style="font-weight:900; font-size:15px; letter-spacing:1.5px; color:#fff;">EMERGENCY LANE CREATOR</span>
                <span style="background:rgba(0,230,118,0.15); color:#00e676; border:1px solid #00e676; border-radius:4px; font-size:9px; font-weight:800; padding:1px 6px; margin-left:6px; letter-spacing:1px;">BENGALURU</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col_role_info:
    is_driver = st.session_state.user_role == "driver"
    badge_color = "#ff3b30" if is_driver else "#0d6efd"
    role_text = "🚑 ASSIGNED ROLE: AMBULANCE DRIVER (ONLY)" if is_driver else "🚓 ASSIGNED ROLE: POLICE CONTROL ROOM (ONLY)"
    
    st.markdown(
        f"""
        <div style="display:flex; align-items:center; justify-content:center; gap:12px; padding-top:4px;">
            <div style="background:{badge_color}; color:#ffffff; padding:6px 18px; border-radius:6px; font-size:12px; font-weight:800; letter-spacing:1px; box-shadow:0 0 12px {badge_color}80;">
                {role_text}
            </div>
            <div style="color:#8ea3b8; font-size:12px;">👤 {st.session_state.user_email}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col_logout:
    sub_l1, sub_l2 = st.columns([1.2, 0.8])
    with sub_l1:
        st.markdown(
            """
            <div style="display:flex; align-items:center; justify-content:flex-end; gap:6px; padding-top:8px; font-size:11px; color:#00e676; font-weight:700;">
                <span style="display:inline-block; width:7px; height:7px; border-radius:50%; background:#00e676; box-shadow:0 0 6px #00e676;"></span>
                <span>SUPABASE ACTIVE</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with sub_l2:
        if st.button("Sign Out", use_container_width=True):
            st.session_state.user_authenticated = False
            st.session_state.user_email = ""
            st.session_state.user_role = ""
            st.rerun()


# -------------------------------------------------------------------------------------------------
# 1. AMBULANCE DRIVER DASHBOARD (With Working Open in Maps & Live Route Switching)
# -------------------------------------------------------------------------------------------------
def render_ambulance_driver_dashboard():
    user_email = st.session_state.get("user_email", "driver@bengalurutraffic.gov.in")
    gmaps_api_key = st.secrets.get("GOOGLE_MAPS_API_KEY", "")
    embed_url = f"https://www.google.com/maps/embed/v1/place?key={gmaps_api_key}&q=Bengaluru,Karnataka" if gmaps_api_key else "https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d248815.9102251064!2d77.4571585011391!3d12.987925087795608!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x3bae1670c9b44e6d%3A0xf8dfc3e8517e4fe0!2sBengaluru%2C%20Karnataka!5e0!3m2!1sen!2sin!4v1793118446274!5m2!1sen!2sin"
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1.0" />
      <title>EMERGENCY LANE CREATOR - Driver 3D Vision</title>
      <link href="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css" rel="stylesheet" />
      <script src="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js"></script>
      <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
          background-color: #070c14;
          color: #e6edf3;
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
          overflow-x: hidden;
          font-size: 13px;
        }}

        /* Top Bar */
        .topbar {{
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 8px 16px;
          background: #09121e;
          border-bottom: 1px solid #162438;
        }}
        .topbar-brand {{
          display: flex;
          align-items: center;
          gap: 10px;
          font-size: 15px;
          font-weight: 800;
          letter-spacing: 1.5px;
          color: #ffffff;
        }}
        .brand-icon {{
          width: 26px;
          height: 26px;
          background: linear-gradient(135deg, #ff3b30, #ff9500);
          border-radius: 6px;
          display: grid;
          place-items: center;
          font-size: 14px;
          box-shadow: 0 0 10px rgba(255, 59, 48, 0.5);
        }}
        .mission-status-pill {{
          display: inline-flex;
          align-items: center;
          gap: 6px;
          padding: 5px 16px;
          border-radius: 6px;
          border: 1.5px solid #ff3b30;
          background: rgba(255, 59, 48, 0.12);
          color: #ff5252;
          font-size: 12px;
          font-weight: 800;
          letter-spacing: 1px;
          box-shadow: 0 0 12px rgba(255, 59, 48, 0.25);
        }}
        .topbar-right {{
          display: flex;
          align-items: center;
          gap: 14px;
          color: #8da4be;
          font-size: 13px;
        }}
        .notification-icon {{
          position: relative;
          cursor: pointer;
          font-size: 16px;
          padding: 4px;
          border-radius: 6px;
        }}
        .notification-dot {{
          position: absolute;
          top: 1px;
          right: 1px;
          width: 7px;
          height: 7px;
          border-radius: 50%;
          background: #ff3b30;
          box-shadow: 0 0 6px #ff3b30;
        }}
        .avatar-circle {{
          width: 28px;
          height: 28px;
          border-radius: 50%;
          background: #19293e;
          border: 1.5px solid #00e676;
          display: grid;
          place-items: center;
          font-size: 13px;
          color: #fff;
          cursor: pointer;
        }}

        /* Main Workspace Layout */
        .workspace {{
          display: flex;
          height: 820px;
          background: #070c14;
        }}

        /* Left Rail */
        .nav-rail {{
          width: 50px;
          background: #08101a;
          border-right: 1px solid #142030;
          display: flex;
          flex-direction: column;
          align-items: center;
          padding: 12px 0;
          gap: 16px;
        }}
        .rail-btn {{
          width: 36px;
          height: 36px;
          border-radius: 8px;
          display: grid;
          place-items: center;
          color: #8da4be;
          cursor: pointer;
          transition: all 0.2s;
          font-size: 16px;
        }}
        .rail-btn:hover {{
          background: #111e30;
          color: #00e676;
          transform: scale(1.08);
        }}
        .rail-btn.active {{
          background: #ff3b30;
          color: #ffffff;
          box-shadow: 0 0 12px rgba(255, 59, 48, 0.5);
        }}

        /* Left Column */
        .left-col {{
          width: 280px;
          min-width: 280px;
          background: #08101a;
          border-right: 1px solid #142030;
          display: flex;
          flex-direction: column;
          padding: 14px 12px;
          gap: 12px;
          overflow-y: auto;
        }}
        .col-header {{
          font-size: 11px;
          font-weight: 800;
          letter-spacing: 1.5px;
          color: #8ea3b8;
          text-transform: uppercase;
          margin-bottom: 2px;
          display: flex;
          justify-content: space-between;
          align-items: center;
        }}

        /* Cards */
        .cards-list {{
          display: flex;
          flex-direction: column;
          gap: 7px;
        }}
        .junction-card {{
          border-radius: 8px;
          padding: 9px 12px;
          background: #0c1522;
          border: 1px solid #19273a;
          display: flex;
          align-items: flex-start;
          gap: 10px;
          cursor: pointer;
          transition: all 0.2s;
        }}
        .junction-card:hover {{
          transform: translateX(3px);
          filter: brightness(1.15);
        }}
        .junction-card.card-green {{
          background: rgba(0, 230, 118, 0.08);
          border: 1.5px solid #00e676;
          box-shadow: 0 0 10px rgba(0, 230, 118, 0.15);
        }}
        .junction-card.card-amber {{
          background: rgba(255, 159, 10, 0.08);
          border: 1.5px solid #ff9f0a;
          box-shadow: 0 0 10px rgba(255, 159, 10, 0.15);
        }}
        .card-light-icon {{
          width: 24px;
          height: 38px;
          background: #070d16;
          border: 1px solid #1d2f47;
          border-radius: 5px;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: space-around;
          padding: 3px 0;
          flex-shrink: 0;
        }}
        .light-dot {{
          width: 6px;
          height: 6px;
          border-radius: 50%;
          background: #1a2a3e;
        }}
        .light-dot.amber {{ background: #ff9f0a; box-shadow: 0 0 5px #ff9f0a; }}
        .light-dot.green {{ background: #00e676; box-shadow: 0 0 5px #00e676; }}

        .card-body {{ flex: 1; }}
        .card-title {{
          font-size: 12px;
          font-weight: 700;
          color: #ffffff;
          line-height: 1.2;
        }}
        .card-subtitle {{
          font-size: 10px;
          font-weight: 700;
          letter-spacing: 0.5px;
          margin-top: 3px;
        }}
        .card-green .card-subtitle {{ color: #00e676; }}
        .card-amber .card-subtitle {{ color: #ff9f0a; }}
        .card-default .card-subtitle {{ color: #8da4be; }}

        .card-status-dots {{
          display: flex;
          align-items: center;
          gap: 6px;
          margin-top: 4px;
          font-size: 9px;
          color: #7b91a7;
        }}
        .dots-row {{ display: flex; gap: 3px; }}
        .dots-row span {{ width: 5px; height: 5px; border-radius: 50%; }}
        .card-green .dots-row span {{ background: #00e676; }}
        .card-amber .dots-row span {{ background: #ff9f0a; }}
        .card-default .dots-row span {{ background: #3d5470; }}

        .card-badge-right {{ font-size: 14px; font-weight: 800; }}
        .card-green .card-badge-right {{ color: #00e676; }}
        .card-amber .card-badge-right {{ color: #ff9f0a; }}

        /* Trends */
        .trends-panel {{
          background: #0c1522;
          border: 1px solid #162438;
          border-radius: 8px;
          padding: 10px;
          margin-top: auto;
        }}
        .trends-chart {{ width: 100%; height: 95px; margin-top: 4px; }}

        /* Center Column */
        .center-col {{
          flex: 1;
          display: flex;
          flex-direction: column;
          background: #050a11;
          position: relative;
        }}

        /* Map Wrapper - Emergency Blue & Red Theme */
        .map-wrapper {{
          height: 640px;
          position: relative;
          background: #040914;
          overflow: hidden;
          border-radius: 8px;
          border: 2px solid #0051ff;
          box-shadow: 0 0 25px rgba(0, 81, 255, 0.45), inset 0 0 35px rgba(255, 0, 60, 0.25);
          animation: mapEmergencyAura 4s infinite alternate ease-in-out;
        }}
        @keyframes mapEmergencyAura {{
          0% {{
            border-color: #0066ff;
            box-shadow: 0 0 25px rgba(0, 102, 255, 0.55), inset 0 0 30px rgba(255, 0, 60, 0.3);
          }}
          50% {{
            border-color: #ff003f;
            box-shadow: 0 0 30px rgba(255, 0, 63, 0.6), inset 0 0 30px rgba(0, 102, 255, 0.3);
          }}
          100% {{
            border-color: #00d4ff;
            box-shadow: 0 0 25px rgba(0, 212, 255, 0.55), inset 0 0 30px rgba(255, 0, 60, 0.35);
          }}
        }}
        #tactical-map {{ width: 100%; height: 100%; background: #030812; }}
        /* Tactical Midnight-Navy Emergency Map Tile Filter */
        .osm-tile-dark {{
          filter: invert(100%) hue-rotate(195deg) saturate(240%) brightness(74%) contrast(145%) !important;
        }}

        /* Emergency Strobe Bar */
        .map-emergency-strobe-bar {{
          position: absolute;
          top: 0;
          left: 0;
          right: 0;
          height: 24px;
          background: rgba(4, 9, 18, 0.92);
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 0 14px;
          z-index: 999;
          border-bottom: 1px solid rgba(0, 140, 255, 0.4);
          pointer-events: none;
        }}
        .strobe-pill-left {{
          background: rgba(0, 140, 255, 0.22);
          border: 1px solid #00d4ff;
          color: #00e5ff;
          font-size: 9px;
          font-weight: 800;
          padding: 2px 8px;
          border-radius: 4px;
          box-shadow: 0 0 10px rgba(0, 212, 255, 0.6);
          animation: strobePulseBlue 0.8s infinite alternate;
        }}
        .strobe-pill-right {{
          background: rgba(255, 0, 60, 0.22);
          border: 1px solid #ff1744;
          color: #ff5252;
          font-size: 9px;
          font-weight: 800;
          padding: 2px 8px;
          border-radius: 4px;
          box-shadow: 0 0 10px rgba(255, 23, 68, 0.6);
          animation: strobePulseRed 0.8s infinite alternate;
        }}
        .strobe-center-badge {{
          font-size: 10px;
          font-weight: 900;
          letter-spacing: 1.5px;
          color: #ffffff;
          text-shadow: 0 0 8px rgba(0, 212, 255, 0.8), 0 0 14px rgba(255, 23, 68, 0.7);
        }}
        @keyframes strobePulseBlue {{
          0% {{ opacity: 0.4; box-shadow: 0 0 4px #0051ff; }}
          100% {{ opacity: 1; box-shadow: 0 0 16px #00e5ff, 0 0 24px #0051ff; }}
        }}
        @keyframes strobePulseRed {{
          0% {{ opacity: 1; box-shadow: 0 0 16px #ff1744, 0 0 24px #ff003f; }}
          100% {{ opacity: 0.4; box-shadow: 0 0 4px #990022; }}
        }}

        /* Floating Overlays */
        .map-overlay-top {{
          position: absolute;
          top: 32px;
          left: 16px;
          display: flex;
          gap: 8px;
          z-index: 1000;
        }}
        .map-pill-btn {{
          background: rgba(10, 18, 30, 0.92);
          backdrop-filter: blur(8px);
          border: 1px solid #1e334d;
          color: #e2ecf5;
          padding: 6px 12px;
          border-radius: 6px;
          font-size: 11px;
          font-weight: 700;
          display: flex;
          align-items: center;
          gap: 6px;
          cursor: pointer;
          box-shadow: 0 4px 12px rgba(0,0,0,0.5);
          transition: all 0.2s;
          text-decoration: none;
        }}
        .map-pill-btn:hover {{
          background: #13243a;
          border-color: #00e676;
          color: #ffffff;
        }}

        /* Open In Google Maps Button - Emergency Theme */
        .btn-open-gmaps {{
          background: linear-gradient(135deg, #0051ff 0%, #d50000 100%) !important;
          border: 1.5px solid #00d4ff !important;
          color: #ffffff !important;
          font-weight: 800 !important;
          box-shadow: 0 0 16px rgba(0, 102, 255, 0.7), 0 0 10px rgba(255, 0, 51, 0.5) !important;
          cursor: pointer !important;
          display: inline-flex !important;
          align-items: center !important;
          gap: 6px !important;
          text-decoration: none !important;
          transition: all 0.2s ease-in-out !important;
        }}
        .btn-open-gmaps:hover {{
          background: linear-gradient(135deg, #0066ff 0%, #ff1744 100%) !important;
          transform: scale(1.05) !important;
          box-shadow: 0 0 24px rgba(0, 102, 255, 0.85), 0 0 16px rgba(255, 23, 68, 0.75) !important;
          color: #ffffff !important;
        }}

        .map-overlay-right {{
          position: absolute;
          top: 14px;
          right: 16px;
          display: flex;
          flex-direction: column;
          gap: 6px;
          z-index: 1000;
        }}
        .map-tool-icon {{
          width: 32px;
          height: 32px;
          background: rgba(10, 18, 30, 0.92);
          backdrop-filter: blur(8px);
          border: 1px solid #1e334d;
          color: #e2ecf5;
          border-radius: 6px;
          display: grid;
          place-items: center;
          cursor: pointer;
          font-size: 14px;
        }}
        .map-tool-icon:hover {{
          background: #162a44;
          color: #00e676;
        }}

        /* Embed Container */
        #gmap-embed-view {{
          display: none;
          width: 100%;
          height: 100%;
          position: absolute;
          top: 0;
          left: 0;
          z-index: 500;
        }}

        /* Floating Directions Card in Map */
        .gmap-floating-card {{
          position: absolute;
          top: 60px;
          left: 16px;
          background: rgba(11, 20, 34, 0.95);
          border: 1px solid #1e334d;
          border-radius: 8px;
          padding: 10px 14px;
          z-index: 1000;
          display: flex;
          align-items: center;
          gap: 12px;
          box-shadow: 0 6px 20px rgba(0,0,0,0.6);
        }}

        /* Logs Panel */
        .logs-panel {{
          height: 180px;
          background: #09121e;
          border-top: 1px solid #162438;
          padding: 10px 16px;
          display: flex;
          flex-direction: column;
          gap: 6px;
        }}
        .logs-header {{
          display: flex;
          justify-content: space-between;
          align-items: center;
          font-size: 11px;
          font-weight: 800;
          letter-spacing: 1px;
          color: #8ea3b8;
        }}
        .logs-list {{
          overflow-y: auto;
          display: flex;
          flex-direction: column;
          gap: 5px;
          font-size: 11px;
          font-family: monospace;
        }}
        .log-row {{
          display: flex;
          align-items: center;
          gap: 8px;
          color: #b5c7d8;
        }}
        .log-bullet {{
          width: 6px;
          height: 6px;
          border-radius: 50%;
          background: #ff3b30;
          box-shadow: 0 0 6px #ff3b30;
        }}
        .log-time {{ color: #6f859d; font-weight: 700; }}
        .log-highlight {{ color: #00e676; font-weight: 700; }}

        /* Right Column */
        .right-col {{
          width: 290px;
          min-width: 290px;
          background: #08101a;
          border-left: 1px solid #142030;
          display: flex;
          flex-direction: column;
          padding: 14px 16px;
          gap: 14px;
          overflow-y: auto;
        }}
        .metric-block {{
          border-bottom: 1px solid #132030;
          padding-bottom: 10px;
        }}
        .metric-label {{
          font-size: 10px;
          font-weight: 800;
          letter-spacing: 1.5px;
          color: #8da4be;
          text-transform: uppercase;
          margin-bottom: 4px;
        }}
        .eta-value {{ display: flex; align-items: baseline; gap: 5px; }}
        .eta-num {{ font-size: 34px; font-weight: 900; color: #ffffff; line-height: 1; }}
        .eta-unit {{ font-size: 13px; font-weight: 700; color: #728aa3; margin-right: 6px; }}
        .dist-value {{ display: flex; align-items: baseline; gap: 6px; }}
        .dist-num {{ font-size: 30px; font-weight: 900; color: #ffffff; line-height: 1; }}

        /* Hospital Card */
        .hospital-card {{
          background: #0c1624;
          border: 1px solid #1a2c42;
          border-radius: 8px;
          padding: 10px 12px;
          display: flex;
          align-items: center;
          gap: 12px;
          cursor: pointer;
        }}
        .hospital-icon-box {{
          width: 38px;
          height: 38px;
          border-radius: 8px;
          background: rgba(255, 59, 48, 0.15);
          border: 1px solid #ff3b30;
          display: grid;
          place-items: center;
          font-size: 18px;
          color: #ff5252;
        }}
        .hospital-name {{ font-size: 12px; font-weight: 800; color: #ffffff; }}
        .hospital-cap {{ font-size: 10px; color: #8ea3b8; margin-top: 2px; }}

        /* Progress */
        .corridor-progress-box {{ display: flex; flex-direction: column; gap: 5px; }}
        .progress-header {{
          display: flex;
          justify-content: space-between;
          font-size: 10px;
          font-weight: 800;
          color: #8da4be;
          letter-spacing: 1px;
        }}
        .progress-pct {{ font-size: 13px; color: #ffffff; }}
        .progress-bar-bg {{
          height: 7px;
          background: #132236;
          border-radius: 4px;
          overflow: hidden;
        }}
        .progress-bar-fill {{
          height: 100%;
          width: 82%;
          background: linear-gradient(90deg, #ff3b30, #ff9f0a 40%, #00e676 100%);
          border-radius: 4px;
          box-shadow: 0 0 10px rgba(0, 230, 118, 0.5);
          transition: width 0.3s ease;
        }}
        .progress-legend {{ display: flex; gap: 8px; font-size: 9px; color: #7b91a7; margin-top: 2px; }}
        .legend-item {{ display: flex; align-items: center; gap: 3px; }}
        .legend-sq {{ width: 6px; height: 6px; border-radius: 1px; }}

        /* Traffic Status */
        .traffic-status-val {{ font-size: 13px; font-weight: 800; color: #ff9f0a; margin-bottom: 6px; }}
        .traffic-segmented-bar {{ display: flex; gap: 4px; height: 6px; }}
        .traffic-seg {{ flex: 1; border-radius: 3px; }}
        .seg-green {{ background: #00e676; box-shadow: 0 0 6px #00e676; }}
        .seg-orange {{ background: #ff9f0a; }}
        .seg-red {{ background: #ff3b30; }}
        .vehicle-status-val {{ font-size: 12px; font-weight: 800; color: #00e676; letter-spacing: 0.5px; }}

        /* Controls */
        .sim-btn-row {{ display: flex; gap: 6px; margin-top: auto; }}
        .sim-btn {{
          flex: 1;
          padding: 8px;
          background: #111d2e;
          border: 1px solid #1f3450;
          color: #c7d8e8;
          border-radius: 6px;
          font-size: 11px;
          font-weight: 700;
          cursor: pointer;
          text-align: center;
          transition: all 0.2s;
        }}
        .sim-btn:hover {{ background: #172a42; color: #ffffff; border-color: #00e676; }}

        /* MapLibre Canvas & 3D HUD Styles */
        .maplibregl-canvas {{ outline: none; }}
        .maplibregl-ctrl-attrib {{ display: none !important; }}
        .maplibregl-ctrl-bottom-right, .maplibregl-ctrl-bottom-left {{ display: none !important; }}

        /* Driver Windshield HUD Overlay */
        .driver-cockpit-hud {{
          position: absolute;
          top: 30px;
          left: 0;
          right: 0;
          bottom: 0;
          pointer-events: none;
          z-index: 500;
          display: flex;
          flex-direction: column;
          justify-content: space-between;
          padding: 8px 16px;
        }}
        .hud-top-reticle {{
          display: flex;
          justify-content: space-between;
          align-items: center;
        }}
        .hud-tag {{
          background: rgba(3, 8, 18, 0.85);
          backdrop-filter: blur(6px);
          border: 1px solid rgba(0, 229, 255, 0.4);
          color: #00e5ff;
          font-family: monospace;
          font-size: 10px;
          font-weight: 800;
          padding: 4px 10px;
          border-radius: 4px;
          letter-spacing: 1px;
          box-shadow: 0 0 10px rgba(0, 0, 0, 0.6);
        }}
        .hud-tag.center-tag {{
          border-color: rgba(255, 23, 68, 0.6);
          color: #ffffff;
          text-shadow: 0 0 8px #00e5ff, 0 0 12px #ff1744;
          background: rgba(6, 14, 28, 0.9);
        }}
        .hud-crosshair-center {{
          position: absolute;
          top: 48%;
          left: 50%;
          transform: translate(-50%, -50%);
          width: 50px;
          height: 50px;
          opacity: 0.35;
          pointer-events: none;
        }}
        .crosshair-h {{
          position: absolute;
          top: 50%;
          left: 0;
          right: 0;
          height: 1.5px;
          background: #00e5ff;
          box-shadow: 0 0 6px #00e5ff;
        }}
        .crosshair-v {{
          position: absolute;
          left: 50%;
          top: 0;
          bottom: 0;
          width: 1.5px;
          background: #ff1744;
          box-shadow: 0 0 6px #ff1744;
        }}

        /* 3D Ambulance Cockpit Marker with Projected Headlights */
        .ambulance-3d-wrapper {{
          position: relative;
          width: 54px;
          height: 54px;
          display: flex;
          align-items: center;
          justify-content: center;
          pointer-events: auto;
        }}
        .amb-headlight-cone {{
          position: absolute;
          bottom: 24px;
          left: 50%;
          transform: translateX(-50%);
          width: 120px;
          height: 180px;
          background: linear-gradient(to top, rgba(0, 229, 255, 0.5) 0%, rgba(255, 23, 68, 0.4) 40%, rgba(0, 229, 255, 0) 100%);
          clip-path: polygon(25% 100%, 75% 100%, 100% 0%, 0% 0%);
          filter: blur(3px);
          pointer-events: none;
          animation: headlightSirenStrobe 0.8s infinite alternate ease-in-out;
        }}
        @keyframes headlightSirenStrobe {{
          0% {{ opacity: 0.65; transform: translateX(-50%) scaleX(0.9); filter: drop-shadow(0 0 10px #0066ff); }}
          100% {{ opacity: 1; transform: translateX(-50%) scaleX(1.15); filter: drop-shadow(0 0 15px #ff1744); }}
        }}
        .ambulance-marker {{
          width: 44px;
          height: 44px;
          border-radius: 50%;
          background: radial-gradient(circle, #ffffff 38%, #050e1c 100%);
          border: 3px solid #ffffff;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 22px;
          position: relative;
          z-index: 2;
          animation: ambEmergencyDualSiren 0.75s infinite alternate ease-in-out;
        }}
        .amb-siren-left {{
          position: absolute;
          left: 4px;
          top: 6px;
          width: 8px;
          height: 8px;
          border-radius: 50%;
          background: #00d4ff;
          box-shadow: 0 0 10px #00d4ff;
          animation: strobePulseBlue 0.5s infinite alternate;
        }}
        .amb-siren-right {{
          position: absolute;
          right: 4px;
          top: 6px;
          width: 8px;
          height: 8px;
          border-radius: 50%;
          background: #ff1744;
          box-shadow: 0 0 10px #ff1744;
          animation: strobePulseRed 0.5s infinite alternate;
        }}
        @keyframes ambEmergencyDualSiren {{
          0% {{
            box-shadow: -12px 0 24px 6px #0066ff, 12px 0 24px 6px #ff0033, 0 0 35px rgba(0, 102, 255, 0.75);
            border-color: #00e5ff;
          }}
          50% {{
            box-shadow: 0 0 30px 8px #ffffff, 0 0 40px rgba(255, 255, 255, 0.85);
            border-color: #ffffff;
          }}
          100% {{
            box-shadow: -12px 0 24px 6px #ff0033, 12px 0 24px 6px #0066ff, 0 0 35px rgba(255, 0, 51, 0.75);
            border-color: #ff1744;
          }}
        }}

        .amb-roof-cross {{ font-size: 22px; z-index: 2; line-height: 1; display: flex; align-items: center; justify-content: center; }}
        .junction-div-icon {{ display: flex; flex-direction: column; align-items: center; white-space: nowrap; cursor: pointer; }}
        .pin-pill {{
          background: rgba(4, 12, 24, 0.94);
          border: 1.5px solid #00e5ff;
          color: #00e5ff;
          font-size: 10px;
          font-weight: 800;
          padding: 3px 8px;
          border-radius: 4px;
          box-shadow: 0 0 12px rgba(0, 229, 255, 0.6);
        }}
        .pin-pill.amber {{ border-color: #ff1744; color: #ff5252; box-shadow: 0 0 12px rgba(255, 23, 68, 0.6); }}
        .pin-dot {{ width: 8px; height: 8px; border-radius: 50%; background: #00e5ff; margin-top: 2px; box-shadow: 0 0 10px #00e5ff; }}
        .pin-dot.amber {{ background: #ff1744; box-shadow: 0 0 10px #ff1744; }}
        .pin-dot.amber {{ background: #ff9f0a; box-shadow: 0 0 8px #ff9f0a; }}

        /* Modals */
        .modal-dialog {{
          display: none;
          position: fixed;
          top: 70px;
          left: 360px;
          width: 400px;
          background: #091322;
          border: 1.5px solid #00e676;
          border-radius: 10px;
          box-shadow: 0 8px 35px rgba(0,0,0,0.9), 0 0 20px rgba(0, 230, 118, 0.35);
          z-index: 3000;
          padding: 16px;
        }}
        .modal-header {{
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 12px;
          font-weight: 800;
          font-size: 12px;
          color: #00e676;
          letter-spacing: 1px;
        }}
      </style>
    </head>
    <body>
      <div class="topbar">
        <div class="topbar-brand">
          <div class="brand-icon">⚡</div>
          <span>EMERGENCY LANE CREATOR</span>
        </div>
        <div class="mission-status-pill">
          <span>●</span> MISSION STATUS: ACTIVE - CRITICAL
        </div>
        <div class="topbar-right">
          <span id="gps-status-badge" style="color:#00e676; font-weight:700;">📶 GPS LOCK: 5G RTK</span>
          <div class="notification-icon" onclick="openNotificationsModal()" title="View Notifications">
            🔔<span class="notification-dot"></span>
          </div>
          <div class="avatar-circle" onclick="openProfileModal()" title="My Profile ({user_email})">
            🚑
          </div>
        </div>
      </div>

      <div class="workspace">
        <!-- Accessible Left Navigation Rail -->
        <div class="nav-rail">
          <div class="rail-btn" onclick="openDrawerMenu()" title="Main Menu">☰</div>
          <div class="rail-btn" onclick="resetMapView()" title="Home Overview">⌂</div>
          <div class="rail-btn active" onclick="openVehicleDiagnostics()" title="Emergency Vehicle Status">🚑</div>
          <div class="rail-btn" onclick="openRoutesModal()" title="Bengaluru Corridor Routes">🛣️</div>
          <div class="rail-btn" onclick="openAlertsModal()" title="Emergency Alerts & Incidents">⚠️</div>
          <div class="rail-btn" style="margin-top:auto;" onclick="openSettingsModal()" title="System Settings">⚙️</div>
        </div>

        <!-- Left Column: Dynamic Upcoming Cards -->
        <div class="left-col">
          <div class="col-header">
            <span>UPCOMING CARD</span>
            <span style="cursor:pointer;" onclick="openRoutesModal()">🛣️ CHANGE ROUTE</span>
          </div>

          <div class="cards-list" id="cards-container">
            <!-- Populated dynamically based on selected route -->
          </div>

          <!-- Traffic Density Trends -->
          <div class="trends-panel">
            <div class="col-header">
              <span>TRAFFIC DENSITY TRENDS</span>
              <span style="cursor:pointer;" onclick="openAlertsModal()">•••</span>
            </div>
            <svg class="trends-chart" viewBox="0 0 240 90">
              <defs>
                <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stop-color="#ff3b30" stop-opacity="0.45" />
                  <stop offset="100%" stop-color="#ff3b30" stop-opacity="0.0" />
                </linearGradient>
              </defs>
              <text x="5" y="15" fill="#4e6680" font-size="8">400</text>
              <line x1="25" y1="12" x2="235" y2="12" stroke="#162334" stroke-width="1" />
              <text x="5" y="38" fill="#4e6680" font-size="8">300</text>
              <line x1="25" y1="35" x2="235" y2="35" stroke="#162334" stroke-width="1" />
              <text x="5" y="60" fill="#4e6680" font-size="8">200</text>
              <line x1="25" y1="57" x2="235" y2="57" stroke="#162334" stroke-width="1" />
              <text x="5" y="80" fill="#4e6680" font-size="8">100</text>
              <line x1="25" y1="77" x2="235" y2="77" stroke="#162334" stroke-width="1" />
              <path d="M 30,75 Q 60,65 90,70 T 150,30 T 210,40 T 235,55 L 235,80 L 30,80 Z" fill="url(#areaGrad)" />
              <path d="M 30,75 Q 60,65 90,70 T 150,30 T 210,40 T 235,55" fill="none" stroke="#ff3b30" stroke-width="2.2" />
              <path d="M 30,80 Q 70,72 100,75 T 160,45 T 210,50 T 235,62" fill="none" stroke="#ff9f0a" stroke-width="1.6" stroke-dasharray="3,2" />
              <text x="30" y="89" fill="#58718a" font-size="7">Sun</text>
              <text x="70" y="89" fill="#58718a" font-size="7">Mon</text>
              <text x="110" y="89" fill="#58718a" font-size="7">Tue</text>
              <text x="150" y="89" fill="#58718a" font-size="7">Wed</text>
              <text x="190" y="89" fill="#58718a" font-size="7">Thu</text>
              <text x="225" y="89" fill="#58718a" font-size="7">Fri</text>
            </svg>
          </div>
        </div>

        <!-- Center Column: Tactical Map + Logs -->
        <div class="center-col">
          <!-- Floating Map Controls -->
          <div class="map-overlay-top">
            <a href="https://www.google.com/maps/dir/?api=1&origin=12.9767,77.5713&destination=12.9634,77.5739&travelmode=driving&dir_action=navigate" 
               target="_blank" 
               rel="noopener noreferrer" 
               class="map-pill-btn btn-open-gmaps" 
               id="top-open-gmaps-link" 
               onclick="openActiveRouteInGoogleMaps(event)" 
               title="Open Live Directions in Google Maps">
              <span style="font-size:13px;">↗</span> <b>Open in Google Maps</b>
            </a>
            <button class="map-pill-btn" onclick="toggleDriverVisionMode()" id="vision-mode-btn" style="border-color:#00e5ff; color:#00e5ff; font-weight:800; box-shadow:0 0 12px rgba(0,229,255,0.4);">👁️ Driver Eye View (3D)</button>
            <button class="map-pill-btn" onclick="toggleCameraModal()">📹 Traffic Camera ▾</button>
            <button class="map-pill-btn" onclick="toggleSensors()">⇲ Sensors</button>
            <button class="map-pill-btn" onclick="toggleSignalController()">🚦 Signals</button>
            <button class="map-pill-btn" onclick="toggleMapMode()" id="map-mode-btn" style="border-color:#ff9f0a; color:#ff9f0a;">🗺️ Google Maps</button>
          </div>

          <div class="map-overlay-right">
            <div class="map-tool-icon" onclick="resetMapView()" title="Driver Eye Lock">👁️</div>
            <div class="map-tool-icon" onclick="map.zoomIn()" title="Zoom In">+</div>
            <div class="map-tool-icon" onclick="map.zoomOut()" title="Zoom Out">−</div>
          </div>

          <!-- Tactical Map Viewport - Driver Eye Vision with 3D Buildings -->
          <div class="map-wrapper">
            <div class="map-emergency-strobe-bar">
              <div class="strobe-pill-left">🚨 BLUE SECTOR (CLEAR)</div>
              <div class="strobe-center-badge">⚡ DRIVER EYE COCKPIT · 3D CORRIDOR LOCK ⚡</div>
              <div class="strobe-pill-right">🚨 RED SECTOR (SIREN)</div>
            </div>

            <!-- Driver Windshield Telemetry HUD -->
            <div class="driver-cockpit-hud" id="driver-cockpit-hud">
              <div class="hud-top-reticle">
                <span class="hud-tag">HEADING: <span id="hud-bearing">045° NE</span></span>
                <span class="hud-tag center-tag">⚡ DRIVER EYE COCKPIT · 3D CORRIDOR ⚡</span>
                <span class="hud-tag">PITCH: 68° · ZOOM 17.5</span>
              </div>
              <div class="hud-crosshair-center">
                <div class="crosshair-h"></div>
                <div class="crosshair-v"></div>
              </div>
            </div>

            <div id="tactical-map"></div>

            <!-- User's Bengaluru Google Maps Embed View with Dedicated Open Link -->
            <div id="gmap-embed-view">
              <iframe id="gmap-iframe" src="{embed_url}" 
                      width="100%" height="100%" style="border:0; filter: invert(92%) hue-rotate(195deg) contrast(140%) brightness(82%) saturate(160%);" 
                      allowfullscreen="" loading="lazy" referrerpolicy="strict-origin-when-cross-origin"></iframe>
              <div class="gmap-floating-card">
                <div>
                  <div style="font-weight:800; font-size:12px; color:#fff;" id="gmap-card-route">Bengaluru Corridor Navigation</div>
                  <div style="font-size:10px; color:#00e5ff;">Live V2X Traffic Priority</div>
                </div>
                <a href="https://www.google.com/maps/dir/?api=1&origin=12.9767,77.5713&destination=12.9634,77.5739&travelmode=driving&dir_action=navigate" 
                   target="_blank" 
                   rel="noopener noreferrer" 
                   class="map-pill-btn btn-open-gmaps" 
                   id="embed-open-gmaps-link" 
                   onclick="openActiveRouteInGoogleMaps(event)" 
                   style="padding:6px 14px; font-size:11px;">
                  ↗ Open in Google Maps
                </a>
              </div>
            </div>
          </div>

          <!-- System Logs -->
          <div class="logs-panel">
            <div class="logs-header">
              <span>SYSTEM LOGS & ALERTS</span>
              <span style="cursor:pointer; color:#7892ac;" onclick="openAlertsModal()">Recent events ▾</span>
            </div>
            <div class="logs-list" id="logs-stream">
              <div class="log-row">
                <span class="log-bullet"></span>
                <span class="log-time">Sun 10:38 PM |</span>
                <span>EMERGENCY LANE CREATOR corridor verified for unit KA-01-EM-4092.</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Right Column -->
        <div class="right-col">
          <div class="metric-block">
            <div class="metric-label">ESTIMATED ARRIVAL (ETA)</div>
            <div class="eta-value">
              <span class="eta-num" id="eta-min">04</span>
              <span class="eta-unit">MIN</span>
              <span class="eta-num" id="eta-sec">12</span>
              <span class="eta-unit">SEC</span>
            </div>
          </div>

          <div class="metric-block">
            <div class="metric-label">REMAINING DISTANCE</div>
            <div class="dist-value">
              <span class="dist-num" id="dist-km">1.8</span>
              <span class="eta-unit">KM</span>
            </div>
          </div>

          <div class="metric-block">
            <div class="metric-label">HOSPITAL DESTINATION</div>
            <div class="hospital-card" onclick="openRoutesModal()">
              <div class="hospital-icon-box">🏥</div>
              <div>
                <div class="hospital-name" id="hud-hospital-name">CITY GENERAL HOSPITAL</div>
                <div class="hospital-cap" id="hud-hospital-cap">ER Capacity: 75% · Victoria Hospital Gate</div>
              </div>
            </div>
          </div>

          <div class="metric-block">
            <div class="corridor-progress-box">
              <div class="progress-header">
                <span>EMERGENCY CORRIDOR PROGRESS</span>
                <span class="progress-pct" id="prog-pct">82%</span>
              </div>
              <div class="progress-bar-bg">
                <div class="progress-bar-fill" id="prog-fill" style="width:82%;"></div>
              </div>
              <div class="progress-legend">
                <div class="legend-item"><span class="legend-sq" style="background:#ff3b30;"></span> Established</div>
                <div class="legend-item"><span class="legend-sq" style="background:#ff9f0a;"></span> Clear Path</div>
                <div class="legend-item"><span class="legend-sq" style="background:#00e676;"></span> Signals Synced</div>
              </div>
            </div>
          </div>

          <div class="metric-block">
            <div class="metric-label">CURRENT TRAFFIC STATUS</div>
            <div class="traffic-status-val">HEAVY (ROUTE CLEARED)</div>
            <div class="traffic-segmented-bar">
              <div class="traffic-seg seg-green"></div>
              <div class="traffic-seg seg-orange"></div>
              <div class="traffic-seg seg-red"></div>
            </div>
          </div>

          <div class="metric-block">
            <div class="metric-label">EMERGENCY VEHICLE STATUS</div>
            <div class="vehicle-status-val" id="veh-status">EN ROUTE - SPEED 55 KPH</div>
          </div>

          <div class="sim-btn-row">
            <button class="sim-btn" onclick="togglePlaySimulation()" id="play-sim-btn">❚❚ Pause</button>
            <button class="sim-btn" onclick="resetSimulation()">↻ Replay</button>
            <a href="https://www.google.com/maps/dir/?api=1&origin=12.9767,77.5713&destination=12.9634,77.5739&travelmode=driving&dir_action=navigate" 
               target="_blank" 
               rel="noopener noreferrer" 
               class="sim-btn btn-open-gmaps" 
               id="hud-maps-link" 
               onclick="openActiveRouteInGoogleMaps(event)" 
               style="color:#fff; text-decoration:none; display:inline-flex; align-items:center; justify-content:center;">
              ↗ Maps
            </a>
          </div>
        </div>
      </div>

      <!-- MODALS -->
      <!-- Notifications -->
      <div id="modal-notifications" class="modal-dialog">
        <div class="modal-header">
          <span>🔔 EMERGENCY NOTIFICATIONS</span>
          <span style="cursor:pointer; color:#8ea3b8;" onclick="closeModal('modal-notifications')">✕</span>
        </div>
        <div style="display:flex; flex-direction:column; gap:8px; font-size:11px;">
          <div style="background:#0e1c2e; padding:8px; border-radius:6px; border-left:3px solid #00d4ff;">
            <b>Signal Preempted:</b> Active route cleared for KA-01-EM-4092.
          </div>
          <div style="background:#0e1c2e; padding:10px; border-radius:6px; border-left:3px solid #ff1744;">
            <div style="font-size:11px; color:#8da4be; margin-bottom:6px;"><b>Live Navigation:</b> Use 'Open in Google Maps' for turn-by-turn driving.</div>
            <a href="https://www.google.com/maps/dir/?api=1&origin=12.9767,77.5713&destination=12.9634,77.5739&travelmode=driving&dir_action=navigate" 
               target="_blank" 
               rel="noopener noreferrer" 
               class="btn-open-gmaps" 
               id="notif-open-gmaps-link" 
               onclick="openActiveRouteInGoogleMaps(event)" 
               style="display:inline-flex; padding:6px 12px; font-size:11px; border-radius:4px; margin-top:4px;">
              📍 Launch Google Maps Navigation
            </a>
          </div>
        </div>
      </div>

      <!-- Profile -->
      <div id="modal-profile" class="modal-dialog">
        <div class="modal-header">
          <span>👤 AMBULANCE DRIVER PROFILE</span>
          <span style="cursor:pointer; color:#8ea3b8;" onclick="closeModal('modal-profile')">✕</span>
        </div>
        <div style="display:flex; flex-direction:column; gap:10px; font-size:12px;">
          <div><b>Account Email:</b> {user_email}</div>
          <div><b>Authorized Role:</b> <span style="color:#00d4ff;">Ambulance Driver (Exclusive)</span></div>
          <div><b>Active Vehicle:</b> KA-01-EM-4092</div>
          <div><b>City Base:</b> Bengaluru Central Emergency Response</div>
          <button class="sim-btn" onclick="window.parent.location.reload()" style="background:#ff3b30; color:#fff; border:none; padding:10px; margin-top:8px;">🚪 Sign Out</button>
        </div>
      </div>

      <!-- Main Menu -->
      <div id="modal-menu" class="modal-dialog">
        <div class="modal-header">
          <span>☰ MAIN MENU</span>
          <span style="cursor:pointer; color:#8ea3b8;" onclick="closeModal('modal-menu')">✕</span>
        </div>
        <div style="display:flex; flex-direction:column; gap:8px;">
          <button class="sim-btn" onclick="resetMapView(); closeModal('modal-menu');">🏠 Reset Bengaluru View</button>
          <button class="sim-btn" onclick="openRoutesModal(); closeModal('modal-menu');">🛣️ Change Corridor Route</button>
          <a href="https://www.google.com/maps/dir/?api=1&origin=12.9767,77.5713&destination=12.9634,77.5739&travelmode=driving&dir_action=navigate" 
             target="_blank" 
             rel="noopener noreferrer" 
             class="sim-btn" 
             id="modal-menu-open-gmaps-link" 
             onclick="openActiveRouteInGoogleMaps(event); closeModal('modal-menu');" 
             style="text-decoration:none; display:flex; align-items:center; justify-content:center; gap:8px;">
            ↗ Open Route in Google Maps
          </a>
          <button class="sim-btn" onclick="openSettingsModal(); closeModal('modal-menu');">⚙️ System Preferences</button>
        </div>
      </div>

      <!-- Route Selector (Working Live Route Switcher) -->
      <div id="modal-routes" class="modal-dialog">
        <div class="modal-header">
          <span>🛣️ SELECT BENGALURU CORRIDOR ROUTE</span>
          <span style="cursor:pointer; color:#8ea3b8;" onclick="closeModal('modal-routes')">✕</span>
        </div>
        <div style="display:flex; flex-direction:column; gap:10px; font-size:11px;">
          <div class="junction-card" id="route-card-1" onclick="applyRoute(1)" style="border-left:4px solid #00e676;">
            <div>
              <div style="font-weight:800; font-size:12px; color:#fff;">Route 1: Central Bengaluru Corridor</div>
              <div style="color:#8da4be; margin-top:2px;">Majestic Terminal → Victoria Hospital Gate (3.8 KM)</div>
              <div style="color:#00e676; font-size:10px; margin-top:4px;">Via Corporation Circle & Richmond Circle</div>
            </div>
          </div>
          <div class="junction-card" id="route-card-2" onclick="applyRoute(2)" style="border-left:4px solid #0d6efd;">
            <div>
              <div style="font-weight:800; font-size:12px; color:#fff;">Route 2: East Arterial Corridor</div>
              <div style="color:#8da4be; margin-top:2px;">Indiranagar 100ft Rd → Manipal Hospital HAL Rd (4.2 KM)</div>
              <div style="color:#00f0ff; font-size:10px; margin-top:4px;">Via Domlur Flyover & Kodihalli</div>
            </div>
          </div>
          <div class="junction-card" id="route-card-3" onclick="applyRoute(3)" style="border-left:4px solid #ff9f0a;">
            <div>
              <div style="font-weight:800; font-size:12px; color:#fff;">Route 3: Tech Zone Corridor</div>
              <div style="color:#8da4be; margin-top:2px;">Whitefield ITPL → Manipal Hospital Whitefield (3.1 KM)</div>
              <div style="color:#ff9f0a; font-size:10px; margin-top:4px;">Via Hope Farm & Channasandra Circle</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Vehicle Diagnostics -->
      <div id="modal-vehicle" class="modal-dialog">
        <div class="modal-header">
          <span>🚑 UNIT KA-01-EM-4092 TELEMETRY</span>
          <span style="cursor:pointer; color:#8ea3b8;" onclick="closeModal('modal-vehicle')">✕</span>
        </div>
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px; font-size:11px;">
          <div style="background:#0e1c2e; padding:8px; border-radius:6px;">Speed: <b style="color:#00e676;">55 KPH</b></div>
          <div style="background:#0e1c2e; padding:8px; border-radius:6px;">Fuel: <b style="color:#00e676;">92%</b></div>
          <div style="background:#0e1c2e; padding:8px; border-radius:6px;">V2X Beacon: <b style="color:#00e676;">ACTIVE</b></div>
          <div style="background:#0e1c2e; padding:8px; border-radius:6px;">GPS: <b style="color:#00e676;">5G RTK</b></div>
        </div>
      </div>

      <!-- Alerts -->
      <div id="modal-alerts" class="modal-dialog">
        <div class="modal-header">
          <span>⚠️ ACTIVE EMERGENCY ALERTS</span>
          <span style="cursor:pointer; color:#8ea3b8;" onclick="closeModal('modal-alerts')">✕</span>
        </div>
        <div style="display:flex; flex-direction:column; gap:8px; font-size:11px;">
          <div style="background:#24160d; padding:8px; border-radius:6px; border-left:3px solid #ff9f0a;">
            Traffic redirected from feeder roads to ensure uninterrupted corridor path.
          </div>
        </div>
      </div>

      <!-- Settings -->
      <div id="modal-settings" class="modal-dialog">
        <div class="modal-header">
          <span>⚙️ SYSTEM SETTINGS</span>
          <span style="cursor:pointer; color:#8ea3b8;" onclick="closeModal('modal-settings')">✕</span>
        </div>
        <div style="display:flex; flex-direction:column; gap:10px; font-size:11px;">
          <label><input type="checkbox" checked /> V2X Audible Warning Signals</label>
          <label><input type="checkbox" checked /> Real-time Supabase GPS Telemetry Ingestion</label>
        </div>
      </div>

      <script>
        // 3 Real Bengaluru Routes Data Definition
        const routesData = {{
          1: {{
            name: "Central Bengaluru Corridor (Majestic → Victoria Hospital)",
            hospital: "CITY GENERAL HOSPITAL",
            hospitalCap: "ER Capacity: 75% · Victoria Hospital Gate",
            distanceKm: 3.8,
            etaMin: "04",
            etaSec: "12",
            gmapsOrigin: "12.9767,77.5713",
            gmapsDest: "12.9634,77.5739",
            waypoints: [
              [12.9767, 77.5713], // Majestic Terminal
              [12.9785, 77.5750], // Seshadri Road
              [12.9750, 77.5815], // K.R. Circle
              [12.9692, 77.5872], // Hudson Circle
              [12.9667, 77.5890], // Corporation Circle
              [12.9645, 77.5935], // Mission Road
              [12.9620, 77.5986], // Richmond Circle
              [12.9628, 77.6045], // Hosur link
              [12.9634, 77.5739]  // Victoria Hospital Gate
            ],
            junctions: [
              {{ name: "Junction 1: Richmond Circle", lat: 12.9620, lng: 77.5986, status: "AI CONTROL ACTIVE", type: "green" }},
              {{ name: "Junction 2: Corporation Circle", lat: 12.9667, lng: 77.5890, status: "TRAFFIC REDIRECTED", type: "amber" }},
              {{ name: "Junction 3: Majestic / K.G. Rd", lat: 12.9767, lng: 77.5713, status: "TRAFFIC REDIRECTED", type: "default" }},
              {{ name: "Junction 4: Hudson Circle", lat: 12.9692, lng: 77.5872, status: "TRAFFIC REDIRECTED", type: "default" }},
              {{ name: "Junction 5: Victoria Hospital Gate", lat: 12.9634, lng: 77.5739, status: "AI CONTROL ACTIVE", type: "green" }}
            ]
          }},
          2: {{
            name: "East Arterial Corridor (Indiranagar → Manipal Hospital HAL)",
            hospital: "MANIPAL HOSPITAL BENGALURU",
            hospitalCap: "ER Capacity: 84% · Old Airport Road Trauma",
            distanceKm: 4.2,
            etaMin: "05",
            etaSec: "40",
            gmapsOrigin: "12.9784,77.6408",
            gmapsDest: "12.9582,77.6521",
            waypoints: [
              [12.9784, 77.6408], // Indiranagar Metro
              [12.9750, 77.6410], // CMH Road Jn
              [12.9680, 77.6415], // 100ft Road 12th Main
              [12.9625, 77.6420], // Domlur Flyover
              [12.9605, 77.6480], // Kodihalli Junction
              [12.9582, 77.6521]  // Manipal Hospital HAL Gate
            ],
            junctions: [
              {{ name: "Junction 1: Indiranagar 100ft Rd", lat: 12.9750, lng: 77.6410, status: "AI CONTROL ACTIVE", type: "green" }},
              {{ name: "Junction 2: BDA Complex Circle", lat: 12.9680, lng: 77.6415, status: "TRAFFIC REDIRECTED", type: "amber" }},
              {{ name: "Junction 3: Domlur Flyover", lat: 12.9625, lng: 77.6420, status: "AI CONTROL ACTIVE", type: "green" }},
              {{ name: "Junction 4: Kodihalli Junction", lat: 12.9605, lng: 77.6480, status: "TRAFFIC REDIRECTED", type: "default" }},
              {{ name: "Junction 5: Manipal Hospital Gate", lat: 12.9582, lng: 77.6521, status: "AI CONTROL ACTIVE", type: "green" }}
            ]
          }},
          3: {{
            name: "Tech Zone Corridor (Whitefield ITPL → Manipal Whitefield)",
            hospital: "MANIPAL HOSPITAL WHITEFIELD",
            hospitalCap: "ER Capacity: 65% · ITPL Road Trauma",
            distanceKm: 3.1,
            etaMin: "03",
            etaSec: "50",
            gmapsOrigin: "12.9863,77.7338",
            gmapsDest: "12.9719,77.7501",
            waypoints: [
              [12.9863, 77.7338], // ITPL Main Gate
              [12.9840, 77.7420], // Hope Farm Junction
              [12.9790, 77.7460], // Channasandra Circle
              [12.9740, 77.7485], // Varthur Main Road
              [12.9719, 77.7501]  // Manipal Hospital Whitefield Gate
            ],
            junctions: [
              {{ name: "Junction 1: ITPL Main Gate", lat: 12.9863, lng: 77.7338, status: "AI CONTROL ACTIVE", type: "green" }},
              {{ name: "Junction 2: Hope Farm Junction", lat: 12.9840, lng: 77.7420, status: "TRAFFIC REDIRECTED", type: "amber" }},
              {{ name: "Junction 3: Channasandra Circle", lat: 12.9790, lng: 77.7460, status: "TRAFFIC REDIRECTED", type: "default" }},
              {{ name: "Junction 4: Varthur Road Jn", lat: 12.9740, lng: 77.7485, status: "TRAFFIC REDIRECTED", type: "default" }},
              {{ name: "Junction 5: Manipal Hospital Gate", lat: 12.9719, lng: 77.7501, status: "AI CONTROL ACTIVE", type: "green" }}
            ]
          }}
        }};

        let activeRouteId = 1;
        let map = null;
        let mapLoaded = false;
        let ambulanceMarker = null;
        let ambMarkerEl = null;
        let junctionMarkers = [];
        let simProgress = 0.05;
        let simPlaying = true;
        let currentMapMode = 'tactical';
        let isDriverVision = true;
        let currentBearing = 45;

        // Spherical forward bearing calculation for driver cockpit orientation
        function calculateBearing(lat1, lon1, lat2, lon2) {{
          const dLon = (lon2 - lon1) * Math.PI / 180;
          const y = Math.sin(dLon) * Math.cos(lat2 * Math.PI / 180);
          const x = Math.cos(lat1 * Math.PI / 180) * Math.sin(lat2 * Math.PI / 180) -
                    Math.sin(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * Math.cos(dLon);
          let brng = Math.atan2(y, x) * 180 / Math.PI;
          return (brng + 360) % 360;
        }}

        function getCompassDir(b) {{
          const dirs = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
          return dirs[Math.round(b / 45) % 8];
        }}

        // Procedural 3D Urban Architecture along the emergency corridor
        function generateCorridor3DBuildings(waypoints) {{
          const features = [];
          const numSegs = waypoints.length - 1;
          const mPerLat = 110574;
          const mPerLng = 108480;

          for (let i = 0; i < numSegs; i++) {{
            const p1 = waypoints[i];
            const p2 = waypoints[i + 1];

            const dLatM = (p2[0] - p1[0]) * mPerLat;
            const dLngM = (p2[1] - p1[1]) * mPerLng;
            const segLen = Math.sqrt(dLatM * dLatM + dLngM * dLngM);
            if (segLen < 1) continue;

            const ux = dLngM / segLen;
            const uy = dLatM / segLen;
            // Perpendicular unit vector
            const nx = -uy;
            const ny = ux;

            // Generate 3D building pairs along this segment
            const steps = Math.max(3, Math.min(8, Math.floor(segLen / 45)));
            for (let s = 0; s < steps; s++) {{
              const t = (s + 0.5) / steps;
              const midLat = p1[0] + t * (p2[0] - p1[0]);
              const midLng = p1[1] + t * (p2[1] - p1[1]);

              // Seed pseudo-random heights & colors based on location
              const seed = Math.abs(Math.sin((i * 13 + s * 7) * 43.123));
              const height = 35 + Math.floor(seed * 85); // 35m to 120m skyscraper heights
              const widthM = 22 + Math.floor(seed * 12);
              const depthM = 24 + Math.floor(seed * 14);

              const colors = ['#081729', '#0d223f', '#122c50', '#163660', '#0a1d35'];
              const color = colors[Math.floor(seed * colors.length)];

              // Left side building (offset 24m to 48m from road centerline)
              const offsetLeftM = 24 + (seed * 8);
              const leftCenterLat = midLat + (ny * offsetLeftM) / mPerLat;
              const leftCenterLng = midLng + (nx * offsetLeftM) / mPerLng;
              features.push(createBuildingPolygon(leftCenterLat, leftCenterLng, widthM, depthM, ux, uy, nx, ny, height, color, mPerLat, mPerLng));

              // Right side building (offset -24m to -48m from road centerline)
              const offsetRightM = -24 - (seed * 8);
              const rightCenterLat = midLat + (ny * offsetRightM) / mPerLat;
              const rightCenterLng = midLng + (nx * offsetRightM) / mPerLng;
              features.push(createBuildingPolygon(rightCenterLat, rightCenterLng, widthM, depthM, ux, uy, nx, ny, Math.max(30, height - 15), color, mPerLat, mPerLng));
            }}
          }}

          // Special landmark: Destination Emergency Trauma Center (Tall Medical Tower)
          const destPt = waypoints[waypoints.length - 1];
          features.push(createBuildingPolygon(destPt[0] + 0.0003, destPt[1] + 0.0003, 50, 45, 1, 0, 0, 1, 95, '#0e2b4d', mPerLat, mPerLng));

          return {{
            'type': 'FeatureCollection',
            'features': features
          }};
        }}

        function createBuildingPolygon(cLat, cLng, wM, dM, ux, uy, nx, ny, height, color, mPerLat, mPerLng) {{
          const hw = wM / 2;
          const hd = dM / 2;
          // 4 corners rotated with road direction
          const cornersM = [
            [-hw, -hd],
            [hw, -hd],
            [hw, hd],
            [-hw, hd]
          ];
          const coords = cornersM.map(c => {{
            const offX = (c[0] * nx + c[1] * ux);
            const offY = (c[0] * ny + c[1] * uy);
            return [
              cLng + offX / mPerLng,
              cLat + offY / mPerLat
            ];
          }});
          coords.push(coords[0]); // Close polygon
          return {{
            'type': 'Feature',
            'properties': {{
              'height': height,
              'color': color
            }},
            'geometry': {{
              'type': 'Polygon',
              'coordinates': [coords]
            }}
          }};
        }}

        function initTacticalMap() {{
          const r = routesData[activeRouteId];
          const startPt = r.waypoints[0];
          const nextPt = r.waypoints[1];
          currentBearing = calculateBearing(startPt[0], startPt[1], nextPt[0], nextPt[1]);

          map = new maplibregl.Map({{
            container: 'tactical-map',
            style: {{
              version: 8,
              sources: {{
                'osm-raster': {{
                  type: 'raster',
                  tiles: [
                    'https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png'
                  ],
                  tileSize: 256,
                  attribution: '© OpenStreetMap contributors'
                }}
              }},
              layers: [{{
                id: 'osm-base',
                type: 'raster',
                source: 'osm-raster',
                minzoom: 0,
                maxzoom: 19,
                paint: {{
                  'raster-opacity': 0.85,
                  'raster-contrast': 0.25,
                  'raster-brightness-max': 0.55
                }}
              }}]
            }},
            center: [startPt[1], startPt[0]],
            zoom: 17.6,
            pitch: 68,
            bearing: currentBearing,
            antialias: true
          }});

          map.on('load', () => {{
            mapLoaded = true;

            // Remove 2D flat building outlines to emphasize 3D extrusions
            const style = map.getStyle();
            (style.layers || []).forEach(l => {{
              if (l.type === 'hillshade') map.removeLayer(l.id);
            }});

            // 1. Add Procedural 3D Corridor Buildings Source & Layer
            const buildingsData = generateCorridor3DBuildings(r.waypoints);
            map.addSource('corridor-3d-buildings', {{
              'type': 'geojson',
              'data': buildingsData
            }});

            map.addLayer({{
              'id': 'corridor-3d-buildings-layer',
              'type': 'fill-extrusion',
              'source': 'corridor-3d-buildings',
              'paint': {{
                'fill-extrusion-color': ['get', 'color'],
                'fill-extrusion-height': ['get', 'height'],
                'fill-extrusion-base': 0,
                'fill-extrusion-opacity': 0.92
              }}
            }});

            // 2. Add Route Polyline LineString Source
            const lineCoords = r.waypoints.map(p => [p[1], p[0]]);
            map.addSource('corridor-route', {{
              'type': 'geojson',
              'data': {{
                'type': 'Feature',
                'geometry': {{ 'type': 'LineString', 'coordinates': lineCoords }}
              }}
            }});

            // Multi-Layer Emergency Blue & Red Corridor Lines on Asphalt
            // Outer Emergency Siren Red Radiation Aura
            map.addLayer({{
              'id': 'route-layer-glow',
              'type': 'line',
              'source': 'corridor-route',
              'layout': {{ 'line-join': 'round', 'line-cap': 'round' }},
              'paint': {{
                'line-color': '#ff0033',
                'line-width': 28,
                'line-opacity': 0.45
              }}
            }});

            // Tactical Emergency Blue Corridor Boundary
            map.addLayer({{
              'id': 'route-layer-blue',
              'type': 'line',
              'source': 'corridor-route',
              'layout': {{ 'line-join': 'round', 'line-cap': 'round' }},
              'paint': {{
                'line-color': '#0066ff',
                'line-width': 16,
                'line-opacity': 0.88
              }}
            }});

            // High-Voltage Neon Cyan Guide
            map.addLayer({{
              'id': 'route-layer-cyan',
              'type': 'line',
              'source': 'corridor-route',
              'layout': {{ 'line-join': 'round', 'line-cap': 'round' }},
              'paint': {{
                'line-color': '#00e5ff',
                'line-width': 8,
                'line-opacity': 0.95
              }}
            }});

            // Emergency Siren Red Core Priority Lane
            map.addLayer({{
              'id': 'route-layer-red',
              'type': 'line',
              'source': 'corridor-route',
              'layout': {{ 'line-join': 'round', 'line-cap': 'round' }},
              'paint': {{
                'line-color': '#ff1744',
                'line-width': 4.5,
                'line-opacity': 1.0
              }}
            }});

            // High-Visibility Rapid Strobe Centerline
            map.addLayer({{
              'id': 'route-layer-strobe',
              'type': 'line',
              'source': 'corridor-route',
              'layout': {{ 'line-join': 'round', 'line-cap': 'round' }},
              'paint': {{
                'line-color': '#ffffff',
                'line-width': 2,
                'line-dasharray': [2, 3],
                'line-opacity': 0.95
              }}
            }});

            // 3. Dynamic Cleared Emergency Trail Source (Secured Blue behind vehicle)
            map.addSource('corridor-cleared', {{
              'type': 'geojson',
              'data': {{
                'type': 'Feature',
                'geometry': {{ 'type': 'LineString', 'coordinates': [lineCoords[0]] }}
              }}
            }});

            map.addLayer({{
              'id': 'route-layer-cleared',
              'type': 'line',
              'source': 'corridor-cleared',
              'layout': {{ 'line-join': 'round', 'line-cap': 'round' }},
              'paint': {{
                'line-color': '#00f0ff',
                'line-width': 12,
                'line-opacity': 0.92
              }}
            }});

            // 4. Create 3D Ambulance Marker with Projected Headlight Beams
            ambMarkerEl = document.createElement('div');
            ambMarkerEl.className = 'ambulance-3d-wrapper';
            ambMarkerEl.innerHTML = `
              <div class="amb-headlight-cone"></div>
              <div class="ambulance-marker">
                <div class="amb-siren-left"></div>
                <div class="amb-roof-cross">🚑</div>
                <div class="amb-siren-right"></div>
              </div>
            `;
            ambulanceMarker = new maplibregl.Marker({{ element: ambMarkerEl, rotationAlignment: 'map', pitchAlignment: 'map' }})
              .setLngLat([startPt[1], startPt[0]])
              .addTo(map);

            // 5. Add Junction Markers
            setupJunctionMarkers(r);

            startSimulationLoop();
          }});

          applyRoute(1);
        }}

        function setupJunctionMarkers(route) {{
          junctionMarkers.forEach(m => m.remove());
          junctionMarkers = [];

          route.junctions.forEach(j => {{
            const el = document.createElement('div');
            el.className = 'junction-div-icon';
            const isAmber = j.type === 'amber';
            el.innerHTML = `<div class="pin-pill ${{isAmber ? 'amber' : ''}}">🚦 ${{j.name}}</div><div class="pin-dot ${{isAmber ? 'amber' : ''}}"></div>`;
            el.onclick = () => focusJunction(j.lat, j.lng, j.name);

            const marker = new maplibregl.Marker({{ element: el, anchor: 'bottom' }})
              .setLngLat([j.lng, j.lat])
              .addTo(map);
            junctionMarkers.push(marker);
          }});
        }}

        // REDIRECT TO GOOGLE MAPS WITH TURN-BY-TURN DIRECTIONS
        function openActiveRouteInGoogleMaps(event) {{
          const r = routesData[activeRouteId];
          const url = `https://www.google.com/maps/dir/?api=1&origin=${{r.gmapsOrigin}}&destination=${{r.gmapsDest}}&travelmode=driving&dir_action=navigate`;
          if (event && event.currentTarget) {{
            event.currentTarget.href = url;
          }}
          try {{
            const win = window.open(url, '_blank', 'noopener,noreferrer');
            if (win) win.focus();
          }} catch (e) {{}}
          addLogEntry(`Opened Google Maps driving navigation for: ${{r.name}}`);
        }}

        // LIVE ROUTE SWITCHING: Redraws 3D buildings, corridor lines, markers, HUD
        function applyRoute(routeId) {{
          activeRouteId = routeId;
          const route = routesData[routeId];
          simProgress = 0.05;

          const startPt = route.waypoints[0];
          const nextPt = route.waypoints[1];
          currentBearing = calculateBearing(startPt[0], startPt[1], nextPt[0], nextPt[1]);

          if (mapLoaded && map) {{
            // Update 3D buildings for this corridor
            const buildingsData = generateCorridor3DBuildings(route.waypoints);
            const bSource = map.getSource('corridor-3d-buildings');
            if (bSource) bSource.setData(buildingsData);

            // Update route geometry
            const lineCoords = route.waypoints.map(p => [p[1], p[0]]);
            const rSource = map.getSource('corridor-route');
            if (rSource) rSource.setData({{ 'type': 'Feature', 'geometry': {{ 'type': 'LineString', 'coordinates': lineCoords }} }});

            const cSource = map.getSource('corridor-cleared');
            if (cSource) cSource.setData({{ 'type': 'Feature', 'geometry': {{ 'type': 'LineString', 'coordinates': [lineCoords[0]] }} }});

            if (ambulanceMarker) {{
              ambulanceMarker.setLngLat([startPt[1], startPt[0]]);
              ambulanceMarker.setRotation(currentBearing);
            }}

            setupJunctionMarkers(route);

            if (isDriverVision) {{
              map.easeTo({{
                center: [startPt[1], startPt[0]],
                zoom: 17.6,
                pitch: 68,
                bearing: currentBearing,
                duration: 600
              }});
            }} else {{
              resetMapView();
            }}
          }}

          // Sync Google Maps URLs across all Open in Google Maps buttons
          const gmapsUrl = `https://www.google.com/maps/dir/?api=1&origin=${{route.gmapsOrigin}}&destination=${{route.gmapsDest}}&travelmode=driving&dir_action=navigate`;
          ['top-open-gmaps-link', 'embed-open-gmaps-link', 'hud-maps-link', 'notif-open-gmaps-link', 'modal-menu-open-gmaps-link'].forEach(id => {{
            const el = document.getElementById(id);
            if (el) el.href = gmapsUrl;
          }});

          // Update Left Column Upcoming Cards HTML
          const container = document.getElementById('cards-container');
          container.innerHTML = route.junctions.map((j, i) => `
            <div class="junction-card ${{j.type === 'green' ? 'card-green' : (j.type === 'amber' ? 'card-amber' : '')}}" onclick="focusJunction(${{j.lat}}, ${{j.lng}}, '${{j.name}}')">
              <div class="card-light-icon">
                <div class="light-dot ${{j.type === 'amber' ? 'amber' : ''}}"></div>
                <div class="light-dot ${{j.type === 'green' ? 'green' : ''}}"></div>
                <div class="light-dot"></div>
              </div>
              <div class="card-body">
                <div class="card-title">${{j.name}}</div>
                <div class="card-subtitle">${{j.status}}</div>
                <div class="card-status-dots"><span>3D CORRIDOR</span><div class="dots-row"><span></span><span></span><span></span><span></span></div></div>
              </div>
              <div class="card-badge-right">${{j.type === 'green' ? '✓' : (j.type === 'amber' ? '!' : '')}}</div>
            </div>
          `).join('');

          // Update Right Column Hospital Destination & Telemetry
          document.getElementById('hud-hospital-name').textContent = route.hospital;
          document.getElementById('hud-hospital-cap').textContent = route.hospitalCap;
          document.getElementById('dist-km').textContent = route.distanceKm;
          document.getElementById('eta-min').textContent = route.etaMin;
          document.getElementById('eta-sec').textContent = route.etaSec;
          document.getElementById('gmap-card-route').textContent = route.name;

          closeModal('modal-routes');
          addLogEntry(`Corridor switched to: ${{route.name}} (Driver Eye 3D Vision Locked)`);
        }}

        function focusJunction(lat, lng, name) {{
          if (map) {{
            map.flyTo({{ center: [lng, lat], zoom: 17.5, pitch: 65, duration: 800 }});
            addLogEntry(`Inspecting ${{name}} — Signal preemption locked.`);
          }}
        }}

        function interpolatePosition(t) {{
          const route = routesData[activeRouteId].waypoints;
          const totalSegments = route.length - 1;
          const globalT = Math.max(0, Math.min(1, t)) * totalSegments;
          const index = Math.min(Math.floor(globalT), totalSegments - 1);
          const localT = globalT - index;
          const p1 = route[index];
          const p2 = route[index + 1];
          return [
            p1[0] + (p2[0] - p1[0]) * localT,
            p1[1] + (p2[1] - p1[1]) * localT
          ];
        }}

        function toggleDriverVisionMode() {{
          isDriverVision = !isDriverVision;
          const btn = document.getElementById('vision-mode-btn');
          const hud = document.getElementById('driver-cockpit-hud');
          if (isDriverVision) {{
            btn.textContent = '👁️ Driver Eye View (3D)';
            btn.style.borderColor = '#00e5ff';
            btn.style.color = '#00e5ff';
            if (hud) hud.style.display = 'flex';
            addLogEntry('Locked to Driver Cockpit Eye Vision (3D Buildings).');
          }} else {{
            btn.textContent = '🛰️ Tactical Drone View';
            btn.style.borderColor = '#ff9f0a';
            btn.style.color = '#ff9f0a';
            if (hud) hud.style.display = 'none';
            resetMapView();
            addLogEntry('Switched to Overhead Drone View.');
          }}
        }}

        function startSimulationLoop() {{
          setInterval(() => {{
            if (!simPlaying || !mapLoaded || !map) return;
            simProgress += 0.0016;
            if (simProgress > 0.98) simProgress = 0.05;

            const pos = interpolatePosition(simProgress);
            const nextPos = interpolatePosition(Math.min(0.999, simProgress + 0.008));
            currentBearing = calculateBearing(pos[0], pos[1], nextPos[0], nextPos[1]);

            // Update Ambulance Marker position and heading
            if (ambulanceMarker) {{
              ambulanceMarker.setLngLat([pos[1], pos[0]]);
              ambulanceMarker.setRotation(currentBearing);
            }}

            // DRIVER EYE VISION: Camera follows tightly behind ambulance looking down the corridor
            if (isDriverVision) {{
              map.easeTo({{
                center: [pos[1], pos[0]],
                zoom: 17.5,
                pitch: 68,
                bearing: currentBearing,
                duration: 180,
                easing: t => t
              }});

              const bRounded = Math.round(currentBearing);
              const bTag = document.getElementById('hud-bearing');
              if (bTag) bTag.textContent = bRounded + '° ' + getCompassDir(bRounded);
            }}

            // Update Cleared Blue Trail GeoJSON
            const routePts = routesData[activeRouteId].waypoints;
            const totalSegs = routePts.length - 1;
            const currentSeg = Math.min(Math.floor(simProgress * totalSegs), totalSegs - 1);
            const clearedCoords = [];
            for (let k = 0; k <= currentSeg; k++) {{
              clearedCoords.push([routePts[k][1], routePts[k][0]]);
            }}
            clearedCoords.push([pos[1], pos[0]]);

            const cSource = map.getSource('corridor-cleared');
            if (cSource) {{
              cSource.setData({{
                'type': 'Feature',
                'geometry': {{ 'type': 'LineString', 'coordinates': clearedCoords }}
              }});
            }}

            const r = routesData[activeRouteId];
            const remaining = ((1 - simProgress) * r.distanceKm).toFixed(1);
            document.getElementById('dist-km').textContent = remaining;

            const totalSec = Math.round((1 - simProgress) * 260);
            const m = Math.floor(totalSec / 60);
            const s = totalSec % 60;
            document.getElementById('eta-min').textContent = m.toString().padStart(2, '0');
            document.getElementById('eta-sec').textContent = s.toString().padStart(2, '0');

            const pct = Math.round(simProgress * 100);
            document.getElementById('prog-pct').textContent = pct + '%';
            document.getElementById('prog-fill').style.width = pct + '%';
          }}, 180);
        }}

        function addLogEntry(text) {{
          const container = document.getElementById('logs-stream');
          if (!container) return;
          const row = document.createElement('div');
          row.className = 'log-row';
          const nowStr = new Date().toLocaleTimeString('en-US', {{ hour: '2-digit', minute: '2-digit' }});
          row.innerHTML = `<span class="log-bullet"></span><span class="log-time">${{nowStr}} |</span><span>${{text}}</span>`;
          container.insertBefore(row, container.firstChild);
        }}

        // Modal Helpers
        function openModal(id) {{
          document.querySelectorAll('.modal-dialog').forEach(m => m.style.display = 'none');
          const m = document.getElementById(id);
          if (m) m.style.display = 'block';
        }}
        function closeModal(id) {{
          const m = document.getElementById(id);
          if (m) m.style.display = 'none';
        }}
        function openNotificationsModal() {{ openModal('modal-notifications'); }}
        function openProfileModal() {{ openModal('modal-profile'); }}
        function openDrawerMenu() {{ openModal('modal-menu'); }}
        function openVehicleDiagnostics() {{ openModal('modal-vehicle'); }}
        function openRoutesModal() {{ openModal('modal-routes'); }}
        function openAlertsModal() {{ openModal('modal-alerts'); }}
        function openSettingsModal() {{ openModal('modal-settings'); }}

        function toggleMapMode() {{
          const gmap = document.getElementById('gmap-embed-view');
          const btn = document.getElementById('map-mode-btn');
          if (currentMapMode === 'tactical') {{
            gmap.style.display = 'block';
            currentMapMode = 'gmap';
            btn.textContent = '🛰️ Tactical 3D View';
            addLogEntry('Switched to Google Maps View.');
          }} else {{
            gmap.style.display = 'none';
            currentMapMode = 'tactical';
            btn.textContent = '🗺️ Google Maps View';
            if (map) map.resize();
            addLogEntry('Switched to Driver 3D Vision.');
          }}
        }}

        function resetMapView() {{
          if (!map) return;
          const r = routesData[activeRouteId];
          const lineCoords = r.waypoints.map(p => [p[1], p[0]]);
          // Compute bounding box
          let minLng = 180, maxLng = -180, minLat = 90, maxLat = -90;
          lineCoords.forEach(c => {{
            if (c[0] < minLng) minLng = c[0];
            if (c[0] > maxLng) maxLng = c[0];
            if (c[1] < minLat) minLat = c[1];
            if (c[1] > maxLat) maxLat = c[1];
          }});
          map.fitBounds([[minLng, minLat], [maxLng, maxLat]], {{ padding: 60, pitch: 40, bearing: 0 }});
        }}

        function togglePlaySimulation() {{
          simPlaying = !simPlaying;
          document.getElementById('play-sim-btn').textContent = simPlaying ? '❚❚ Pause' : '▶ Play';
        }}
        function resetSimulation() {{
          simProgress = 0.05;
        }}

        window.onload = initTacticalMap;
      </script>
    </body>
    </html>
    """
    components.html(html_content, height=860, scrolling=False)


# -------------------------------------------------------------------------------------------------
# 2. POLICE CONTROL ROOM DASHBOARD (Exclusive for Police / Dispatchers)
# -------------------------------------------------------------------------------------------------
def render_police_control_room_dashboard():
    dest_key = live_state.get("destination_key", "victoria")
    user_email = st.session_state.get("user_email", "officer.blr_pcr@bengalurutraffic.gov.in")
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1.0" />
      <title>EMERGENCY LANE CREATOR - Police HQ</title>
      <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
      <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
      <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
          background-color: #0b1422;
          color: #e2ecf5;
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
          padding: 18px 24px;
          min-height: 800px;
        }}

        .header {{
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 24px;
        }}
        .header-title {{
          font-size: 26px;
          font-weight: 800;
          color: #ffffff;
          letter-spacing: 0.5px;
        }}
        .header-controls {{
          display: flex;
          align-items: center;
          gap: 12px;
        }}
        .action-circle-btn {{
          width: 38px;
          height: 38px;
          border-radius: 50%;
          background: #0d6efd;
          border: none;
          color: #ffffff;
          display: grid;
          place-items: center;
          font-size: 15px;
          cursor: pointer;
          box-shadow: 0 0 14px rgba(13, 110, 253, 0.4);
          transition: all 0.2s;
        }}
        .action-circle-btn:hover {{
          background: #0b5ed7;
          transform: scale(1.05);
        }}

        .pcr-gmaps-pill {{
          display: inline-flex;
          align-items: center;
          gap: 6px;
          padding: 8px 16px;
          border-radius: 6px;
          background: linear-gradient(135deg, #0051ff 0%, #d50000 100%);
          border: 1.5px solid #00d4ff;
          color: #ffffff;
          font-size: 12px;
          font-weight: 800;
          letter-spacing: 0.5px;
          text-decoration: none;
          box-shadow: 0 0 16px rgba(0, 102, 255, 0.6), 0 0 10px rgba(255, 0, 51, 0.5);
          cursor: pointer;
          transition: all 0.2s ease-in-out;
        }}
        .pcr-gmaps-pill:hover {{
          background: linear-gradient(135deg, #0066ff 0%, #ff1744 100%);
          transform: scale(1.05);
          box-shadow: 0 0 24px rgba(0, 102, 255, 0.8), 0 0 16px rgba(255, 23, 68, 0.7);
          color: #ffffff;
        }}

        /* Tactical Emergency Map Container for PCR */
        .pcr-map-card {{
          position: relative;
          border-radius: 10px;
          overflow: hidden;
          margin-bottom: 24px;
          border: 2px solid #0051ff;
          box-shadow: 0 0 25px rgba(0, 81, 255, 0.45), inset 0 0 35px rgba(255, 0, 60, 0.25);
          animation: mapEmergencyAura 4s infinite alternate ease-in-out;
        }}
        .osm-tile-dark {{
          filter: invert(100%) hue-rotate(195deg) saturate(240%) brightness(74%) contrast(145%) !important;
        }}
        .ambulance-marker {{
          width: 42px;
          height: 42px;
          border-radius: 50%;
          background: radial-gradient(circle, #ffffff 35%, #050e1c 100%);
          border: 3px solid #ffffff;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 18px;
          position: relative;
          animation: ambEmergencyDualSiren 0.75s infinite alternate ease-in-out;
        }}
        .amb-siren-left {{
          position: absolute;
          left: 4px;
          top: 5px;
          width: 7px;
          height: 7px;
          border-radius: 50%;
          background: #00d4ff;
          box-shadow: 0 0 8px #00d4ff;
        }}
        .amb-siren-right {{
          position: absolute;
          right: 4px;
          top: 5px;
          width: 7px;
          height: 7px;
          border-radius: 50%;
          background: #ff1744;
          box-shadow: 0 0 8px #ff1744;
        }}
        @keyframes ambEmergencyDualSiren {{
          0% {{
            box-shadow: -10px 0 20px 5px #0066ff, 10px 0 20px 5px #ff0033, 0 0 30px rgba(0, 102, 255, 0.75);
            border-color: #00e5ff;
          }}
          50% {{
            box-shadow: 0 0 25px 6px #ffffff, 0 0 35px rgba(255, 255, 255, 0.85);
            border-color: #ffffff;
          }}
          100% {{
            box-shadow: -10px 0 20px 5px #ff0033, 10px 0 20px 5px #0066ff, 0 0 30px rgba(255, 0, 51, 0.75);
            border-color: #ff1744;
          }}
        }}
        .map-emergency-strobe-bar {{
          height: 24px;
          background: rgba(4, 9, 18, 0.94);
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 0 14px;
          border-bottom: 1px solid rgba(0, 140, 255, 0.4);
        }}
        .strobe-pill-left {{
          background: rgba(0, 140, 255, 0.22);
          border: 1px solid #00d4ff;
          color: #00e5ff;
          font-size: 9px;
          font-weight: 800;
          padding: 2px 8px;
          border-radius: 4px;
          box-shadow: 0 0 10px rgba(0, 212, 255, 0.6);
        }}
        .strobe-pill-right {{
          background: rgba(255, 0, 60, 0.22);
          border: 1px solid #ff1744;
          color: #ff5252;
          font-size: 9px;
          font-weight: 800;
          padding: 2px 8px;
          border-radius: 4px;
          box-shadow: 0 0 10px rgba(255, 23, 68, 0.6);
        }}
        .strobe-center-badge {{
          font-size: 10px;
          font-weight: 900;
          letter-spacing: 1.5px;
          color: #ffffff;
          text-shadow: 0 0 8px rgba(0, 212, 255, 0.8), 0 0 14px rgba(255, 23, 68, 0.7);
        }}

        /* Pipeline Card */
        .pipeline-card {{
          background: #091322;
          border: 1px solid #1c324e;
          border-radius: 12px;
          padding: 34px 44px;
          margin-bottom: 24px;
          box-shadow: 0 8px 30px rgba(0, 0, 0, 0.5);
          position: relative;
        }}
        .pipeline-track {{
          display: flex;
          align-items: center;
          position: relative;
          justify-content: space-between;
          margin: 30px 10px 10px 10px;
        }}

        .line-segment {{
          position: absolute;
          height: 4px;
          top: 50%;
          transform: translateY(-50%);
          z-index: 1;
        }}
        .line-cleared {{
          left: 5%;
          width: 25%;
          background: #00f0ff;
          box-shadow: 0 0 14px #00f0ff;
          transition: width 0.3s ease;
        }}
        .line-dashed {{
          left: 5%;
          width: 90%;
          border-top: 2.5px dashed #2d4869;
        }}

        .pipeline-node {{
          display: flex;
          flex-direction: column;
          align-items: center;
          position: relative;
          z-index: 2;
          width: 150px;
        }}
        .node-pill-top {{
          padding: 3px 14px;
          border-radius: 20px;
          font-size: 10px;
          font-weight: 800;
          letter-spacing: 1px;
          margin-bottom: 14px;
          text-transform: uppercase;
          transition: all 0.3s ease;
        }}
        .pill-cleared {{
          background: rgba(0, 240, 255, 0.15);
          border: 1.5px solid #00f0ff;
          color: #00f0ff;
          box-shadow: 0 0 10px rgba(0, 240, 255, 0.35);
        }}
        .pill-normal {{
          background: rgba(45, 78, 115, 0.35);
          border: 1.5px solid #2d4e73;
          color: #6db3f2;
        }}

        /* Synced Moving Ambulance on Pipeline */
        #pcr-moving-ambulance {{
          position: absolute;
          top: 50%;
          left: 5%;
          transform: translate(-50%, -50%);
          z-index: 10;
          transition: left 0.3s ease;
        }}
        .node-disc-active {{
          width: 36px;
          height: 36px;
          border-radius: 50%;
          background: #ff3b30;
          border: 3px solid #ffffff;
          box-shadow: 0 0 20px #ff3b30, 0 0 35px rgba(255, 59, 48, 0.7);
          display: grid;
          place-items: center;
          font-size: 17px;
          animation: pulseMarker 1.8s infinite;
        }}
        @keyframes pulseMarker {{
          0% {{ box-shadow: 0 0 0 0 rgba(255, 59, 48, 0.7); }}
          70% {{ box-shadow: 0 0 0 18px rgba(255, 59, 48, 0); }}
          100% {{ box-shadow: 0 0 0 0 rgba(255, 59, 48, 0); }}
        }}

        .node-dot-small {{
          width: 14px;
          height: 14px;
          border-radius: 50%;
          background: #0f243d;
          border: 2.5px solid #4a75a3;
          box-shadow: 0 0 8px rgba(74, 117, 163, 0.4);
          transition: all 0.3s;
        }}
        .node-label-bottom {{
          margin-top: 14px;
          font-size: 14px;
          font-weight: 700;
          color: #ffffff;
          text-align: center;
        }}

        /* Table */
        .table-card {{ margin-bottom: 24px; }}
        .tactical-table {{
          width: 100%;
          border-collapse: separate;
          border-spacing: 0 6px;
        }}
        .tactical-table th {{
          font-size: 13px;
          font-weight: 800;
          color: #ffffff;
          padding: 8px 18px;
          text-align: left;
        }}
        .tactical-table td {{
          padding: 12px 18px;
          font-size: 14px;
        }}
        .row-highlight {{
          background: #0d6efd !important;
          color: #ffffff !important;
          font-weight: 700;
        }}
        .row-highlight td:first-child {{ border-top-left-radius: 6px; border-bottom-left-radius: 6px; }}
        .row-highlight td:last-child {{ border-top-right-radius: 6px; border-bottom-right-radius: 6px; }}
        .row-secondary {{ background: #0c182a; color: #9bb1c8; }}
        .row-secondary td:first-child {{ border-top-left-radius: 6px; border-bottom-left-radius: 6px; }}
        .row-secondary td:last-child {{ border-top-right-radius: 6px; border-bottom-right-radius: 6px; }}

        /* Telemetry */
        .telemetry-strip {{
          display: flex;
          align-items: center;
          justify-content: space-around;
          padding: 16px 24px;
          background: #08111d;
          border: 1px solid #16263b;
          border-radius: 10px;
          margin-bottom: 24px;
        }}
        .telem-item {{ display: flex; flex-direction: column; align-items: center; gap: 6px; }}
        .telem-label {{
          font-size: 10px;
          font-weight: 800;
          letter-spacing: 1.5px;
          color: #7b94ad;
          text-transform: uppercase;
        }}
        .telem-val {{
          font-size: 18px;
          font-weight: 900;
          color: #ffffff;
          font-family: monospace;
        }}
        .telem-status-badge {{
          border: 1.5px solid #00f0ff;
          color: #00f0ff;
          background: rgba(0, 240, 255, 0.1);
          padding: 3px 10px;
          border-radius: 4px;
          font-size: 13px;
          font-weight: 800;
          letter-spacing: 1px;
          box-shadow: 0 0 10px rgba(0, 240, 255, 0.25);
        }}
        .telem-divider {{ width: 1px; height: 36px; background: #1b2f48; }}

        /* Bottom Controls Bar */
        .bottom-controls-bar {{
          display: flex;
          align-items: center;
          justify-content: space-between;
          background: #08111d;
          border: 1px solid #16263b;
          border-radius: 10px;
          padding: 14px 20px;
        }}
        .controls-group {{ display: flex; align-items: center; gap: 24px; }}
        .control-field {{ display: flex; align-items: center; gap: 12px; }}
        .control-label {{ font-size: 13px; font-weight: 700; color: #ffffff; }}
        .control-select {{
          background: #0f1c2d;
          border: 1px solid #233954;
          color: #e2ecf5;
          padding: 8px 16px;
          border-radius: 6px;
          font-size: 13px;
          font-weight: 600;
          outline: none;
          cursor: pointer;
        }}
        .speed-input {{
          width: 55px;
          background: #0f1c2d;
          border: 1px solid #233954;
          color: #e2ecf5;
          padding: 8px 10px;
          border-radius: 6px;
          font-size: 13px;
          font-weight: 700;
          text-align: center;
        }}
        .model-badge {{
          display: flex;
          align-items: center;
          gap: 6px;
          background: #0f1e31;
          border: 1px solid #1f3653;
          color: #72a5db;
          padding: 6px 14px;
          border-radius: 20px;
          font-size: 12px;
          font-weight: 700;
        }}
      </style>
    </head>
    <body>
      <div class="header">
        <div style="display:flex; align-items:center; gap:14px;">
          <div class="header-title">Emergency Corridor Dashboard</div>
          <div style="background:linear-gradient(90deg, #0051ff, #ff0033); padding:4px 12px; border-radius:6px; font-size:11px; font-weight:800; letter-spacing:1px; color:#fff; box-shadow:0 0 14px rgba(0,81,255,0.5);">
            🚨 EMERGENCY BLUE & RED LOCK
          </div>
        </div>
        <div class="header-controls">
          <button class="action-circle-btn" onclick="togglePause()" id="btn-pause" title="Pause / Play">❚❚</button>
          <button class="action-circle-btn" onclick="resetCorridor()" title="Reset Corridor">↻</button>
          <a href="https://www.google.com/maps/dir/?api=1&origin=12.9767,77.5713&destination=12.9634,77.5739&travelmode=driving&dir_action=navigate" 
             target="_blank" 
             rel="noopener noreferrer" 
             class="pcr-gmaps-pill" 
             id="pcr-gmaps-link" 
             onclick="openGmapsDirections(event)" 
             title="Open Live Turn-by-Turn Navigation in Google Maps">
            <span style="font-size:13px;">↗</span> <b>Open in Google Maps</b>
          </a>
        </div>
      </div>

      <!-- Tactical Emergency Map for Police Control Room (Blue & Red Theme) -->
      <div class="pcr-map-card">
        <div class="map-emergency-strobe-bar">
          <div class="strobe-pill-left">🚨 BLUE SECTOR (CLEAR)</div>
          <div class="strobe-center-badge">⚡ PCR TACTICAL SITUATIONAL CORRIDOR · BLUE & RED LOCK ⚡</div>
          <div class="strobe-pill-right">🚨 RED SECTOR (LOCKDOWN)</div>
        </div>
        <div id="pcr-map" style="width:100%; height:320px; background:#040914;"></div>
      </div>

      <div class="pipeline-card">
        <div class="line-segment line-dashed"></div>
        <div class="line-segment line-cleared" id="track-cleared"></div>

        <div id="pcr-moving-ambulance">
          <div class="node-disc-active">🚑</div>
        </div>

        <div class="pipeline-track">
          <div class="pipeline-node" id="node-1">
            <div class="node-pill-top pill-cleared" id="pill-j1">CLEARED</div>
            <div class="node-dot-small" id="dot-j1" style="background:#00f0ff;"></div>
            <div class="node-label-bottom" id="label-j1">PCR Junction</div>
          </div>

          <div class="pipeline-node" id="node-2">
            <div class="node-pill-top pill-normal" id="pill-j2">NORMAL</div>
            <div class="node-dot-small" id="dot-j2"></div>
            <div class="node-label-bottom" id="label-j2">Corporation Circle</div>
          </div>

          <div class="pipeline-node" id="node-3">
            <div class="node-pill-top pill-normal" id="pill-j3">NORMAL</div>
            <div class="node-dot-small" id="dot-j3"></div>
            <div class="node-label-bottom" id="label-j3">Richmond Circle</div>
          </div>

          <div class="pipeline-node" id="node-4">
            <div class="node-pill-top pill-normal" id="pill-j4">NORMAL</div>
            <div class="node-dot-small" id="dot-j4"></div>
            <div class="node-label-bottom" id="label-j4">Hospital Gate</div>
          </div>
        </div>
      </div>

      <div class="table-card">
        <table class="tactical-table">
          <thead>
            <tr>
              <th>Timestamp</th>
              <th>Location</th>
              <th>Action</th>
              <th>System Status</th>
            </tr>
          </thead>
          <tbody>
            <tr class="row-highlight">
              <td id="tbl-time">6:49:38 PM</td>
              <td>System</td>
              <td>Ready</td>
              <td>STANDBY</td>
            </tr>
            <tr class="row-secondary">
              <td>6:49:15 PM</td>
              <td>Richmond Circle</td>
              <td>Signal Preemption Override</td>
              <td style="color:#00f0ff;">CORRIDOR ACTIVE</td>
            </tr>
            <tr class="row-secondary">
              <td>6:48:50 PM</td>
              <td>Corporation Circle</td>
              <td>Traffic Redirection Automated</td>
              <td style="color:#00e676;">CLEARED</td>
            </tr>
            <tr class="row-secondary">
              <td>6:48:10 PM</td>
              <td>PCR Junction (Majestic)</td>
              <td>Emergency Unit Dispatched</td>
              <td style="color:#ff9f0a;">EN ROUTE</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="telemetry-strip">
        <div class="telem-item">
          <div class="telem-label">UNIT ID</div>
          <div class="telem-val">{live_state['unit_id']}</div>
        </div>
        <div class="telem-divider"></div>
        <div class="telem-item">
          <div class="telem-label">STATUS</div>
          <div class="telem-status-badge">[ CORRIDOR ACTIVE ]</div>
        </div>
        <div class="telem-divider"></div>
        <div class="telem-item">
          <div class="telem-label">ETA</div>
          <div class="telem-val" id="hud-eta">1:38</div>
        </div>
        <div class="telem-divider"></div>
        <div class="telem-item">
          <div class="telem-label">SPEED</div>
          <div class="telem-val" id="hud-speed">{live_state['speed_kph'] * 3.3:.0f} km/h</div>
        </div>
        <div class="telem-divider"></div>
        <div class="telem-item">
          <div class="telem-label">DIST</div>
          <div class="telem-val" id="hud-dist">{live_state['distance_km']} km</div>
        </div>
      </div>

      <div class="bottom-controls-bar">
        <div class="controls-group">
          <div class="control-field">
            <span class="control-label">Destination</span>
            <select class="control-select" id="dest-select" onchange="onDestinationChange()">
              <option value="victoria" {'selected' if dest_key == 'victoria' else ''}>Victoria Hospital (City Market)</option>
              <option value="manipal" {'selected' if dest_key == 'manipal' else ''}>Manipal Hospital Bengaluru (HAL Rd)</option>
              <option value="fortis" {'selected' if dest_key == 'fortis' else ''}>Fortis Hospital (Cunningham Rd)</option>
              <option value="aster" {'selected' if dest_key == 'aster' else ''}>Aster Ramesh Hospital</option>
            </select>
          </div>
          <div class="control-field">
            <span class="control-label">Speed Multiplier</span>
            <input type="number" class="speed-input" id="multiplier" value="{live_state['speed_multiplier']}" min="1" max="10" onchange="onSpeedChange()" />
          </div>
        </div>
        <div class="model-badge">
          <span>●</span> Flash Extended ▾
        </div>
      </div>

      <script>
        let isPaused = false;
        let speedMultiplier = {live_state['speed_multiplier']};
        let pcrProgress = 0.25;
        let pcrMap, pcrMarker, pcrClearedPolyline;

        const destCoords = {{
          victoria: '12.9634,77.5739',
          manipal: '12.9582,77.6521',
          fortis: '12.9866,77.5975',
          aster: '12.9601,77.5925'
        }};

        const pcrWaypoints = [
          [12.9767, 77.5713], // Majestic Terminal
          [12.9785, 77.5750], // Seshadri Road
          [12.9750, 77.5815], // K.R. Circle
          [12.9692, 77.5872], // Hudson Circle
          [12.9667, 77.5890], // Corporation Circle
          [12.9645, 77.5935], // Mission Road
          [12.9620, 77.5986], // Richmond Circle
          [12.9628, 77.6045], // Hosur link
          [12.9634, 77.5739]  // Victoria Hospital
        ];

        function initPcrMap() {{
          pcrMap = L.map('pcr-map', {{
            center: [12.9680, 77.5880],
            zoom: 14,
            zoomControl: false,
            attributionControl: false
          }});

          L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
            maxZoom: 19,
            className: 'osm-tile-dark'
          }}).addTo(pcrMap);

          // Emergency Blue & Red Corridor Polylines
          L.polyline(pcrWaypoints, {{ color: '#ff0033', weight: 24, opacity: 0.38, lineCap: 'round', lineJoin: 'round' }}).addTo(pcrMap);
          L.polyline(pcrWaypoints, {{ color: '#0066ff', weight: 15, opacity: 0.88, lineCap: 'round', lineJoin: 'round' }}).addTo(pcrMap);
          L.polyline(pcrWaypoints, {{ color: '#00e5ff', weight: 7, opacity: 0.95, lineCap: 'round', lineJoin: 'round' }}).addTo(pcrMap);
          L.polyline(pcrWaypoints, {{ color: '#ff1744', weight: 4, opacity: 1.0, lineCap: 'round', lineJoin: 'round' }}).addTo(pcrMap);
          L.polyline(pcrWaypoints, {{ color: '#ffffff', weight: 1.8, opacity: 0.95, dashArray: '8, 12', lineCap: 'round', lineJoin: 'round' }}).addTo(pcrMap);

          pcrClearedPolyline = L.polyline([], {{ color: '#00f0ff', weight: 9, opacity: 0.9, lineCap: 'round', lineJoin: 'round' }}).addTo(pcrMap);

          const ambIcon = L.divIcon({{
            className: 'ambulance-div-icon',
            html: `
              <div class="ambulance-marker">
                <div class="amb-siren-left"></div>
                <div class="amb-center-icon">🚑</div>
                <div class="amb-siren-right"></div>
              </div>
            `,
            iconSize: [42, 42],
            iconAnchor: [21, 21]
          }});
          pcrMarker = L.marker(pcrWaypoints[0], {{ icon: ambIcon }}).addTo(pcrMap);
          pcrMap.fitBounds(L.latLngBounds(pcrWaypoints), {{ padding: [35, 35] }});
        }}

        function getPcrGmapsUrl() {{
          const destKey = document.getElementById('dest-select').value || 'victoria';
          const destCoord = destCoords[destKey] || '12.9634,77.5739';
          return `https://www.google.com/maps/dir/?api=1&origin=12.9767,77.5713&destination=${{destCoord}}&travelmode=driving&dir_action=navigate`;
        }}

        function openGmapsDirections(event) {{
          const url = getPcrGmapsUrl();
          if (event && event.currentTarget) {{
            event.currentTarget.href = url;
          }}
          try {{
            const win = window.open(url, '_blank', 'noopener,noreferrer');
            if (win) win.focus();
          }} catch (e) {{}}
        }}

        function onDestinationChange() {{
          const sel = document.getElementById('dest-select');
          const chosen = sel.options[sel.selectedIndex].text;
          document.getElementById('label-j4').textContent = chosen.split('(')[0].trim() + ' Gate';
          const link = document.getElementById('pcr-gmaps-link');
          if (link) link.href = getPcrGmapsUrl();
        }}

        function onSpeedChange() {{
          const val = document.getElementById('multiplier').value;
          speedMultiplier = parseFloat(val) || 2;
        }}

        function interpolatePcrPosition(t) {{
          const totalSegments = pcrWaypoints.length - 1;
          const globalT = Math.max(0, Math.min(1, t)) * totalSegments;
          const index = Math.min(Math.floor(globalT), totalSegments - 1);
          const localT = globalT - index;
          const p1 = pcrWaypoints[index];
          const p2 = pcrWaypoints[index + 1];
          return [
            p1[0] + (p2[0] - p1[0]) * localT,
            p1[1] + (p2[1] - p1[1]) * localT
          ];
        }}

        function togglePause() {{
          isPaused = !isPaused;
          document.getElementById('btn-pause').textContent = isPaused ? '▶' : '❚❚';
        }}

        function resetCorridor() {{
          pcrProgress = 0.05;
          updateTimelineView(pcrProgress);
        }}

        function updateTimelineView(prog) {{
          const leftPercent = 5 + (prog * 90);
          document.getElementById('pcr-moving-ambulance').style.left = leftPercent + '%';
          document.getElementById('track-cleared').style.width = (leftPercent - 5) + '%';

          // Sync Leaflet map ambulance and cleared trail
          if (pcrMap && pcrMarker) {{
            const pos = interpolatePcrPosition(prog);
            pcrMarker.setLatLng(pos);
            const totalSegs = pcrWaypoints.length - 1;
            const currentSeg = Math.min(Math.floor(prog * totalSegs), totalSegs - 1);
            const clearedCoords = pcrWaypoints.slice(0, currentSeg + 1);
            clearedCoords.push(pos);
            if (pcrClearedPolyline) pcrClearedPolyline.setLatLngs(clearedCoords);
          }}

          if (prog >= 0.33) {{
            document.getElementById('pill-j2').className = 'node-pill-top pill-cleared';
            document.getElementById('pill-j2').textContent = 'CLEARED';
            document.getElementById('dot-j2').style.background = '#00f0ff';
          }} else {{
            document.getElementById('pill-j2').className = 'node-pill-top pill-normal';
            document.getElementById('pill-j2').textContent = 'NORMAL';
            document.getElementById('dot-j2').style.background = '#0f243d';
          }}

          if (prog >= 0.66) {{
            document.getElementById('pill-j3').className = 'node-pill-top pill-cleared';
            document.getElementById('pill-j3').textContent = 'CLEARED';
            document.getElementById('dot-j3').style.background = '#00f0ff';
          }} else {{
            document.getElementById('pill-j3').className = 'node-pill-top pill-normal';
            document.getElementById('pill-j3').textContent = 'NORMAL';
            document.getElementById('dot-j3').style.background = '#0f243d';
          }}

          if (prog >= 0.95) {{
            document.getElementById('pill-j4').className = 'node-pill-top pill-cleared';
            document.getElementById('pill-j4').textContent = 'CLEARED';
            document.getElementById('dot-j4').style.background = '#00f0ff';
          }} else {{
            document.getElementById('pill-j4').className = 'node-pill-top pill-normal';
            document.getElementById('pill-j4').textContent = 'NORMAL';
            document.getElementById('dot-j4').style.background = '#0f243d';
          }}

          const dist = (3.68 * (1 - prog)).toFixed(2);
          document.getElementById('hud-dist').textContent = dist + ' km';
          const totalSec = Math.round((1 - prog) * 160);
          const m = Math.floor(totalSec / 60);
          const s = totalSec % 60;
          document.getElementById('hud-eta').textContent = m + ':' + (s < 10 ? '0' : '') + s;
        }}

        window.onload = initPcrMap;

        setInterval(() => {{
          if (isPaused) return;
          pcrProgress += (0.003 * speedMultiplier);
          if (pcrProgress > 1.0) pcrProgress = 0.05;
          updateTimelineView(pcrProgress);
        }}, 300);
      </script>
    </body>
    </html>
    """
    components.html(html_content, height=1100, scrolling=True)


# -------------------------------------------------------------------------------------------------
# STRICT ROUTING BASED ON AUTHENTICATED ROLE
# -------------------------------------------------------------------------------------------------
if st.session_state.user_role == "driver":
    render_ambulance_driver_dashboard()
elif st.session_state.user_role == "police":
    render_police_control_room_dashboard()
else:
    st.error("No valid role assigned in Supabase. Please contact the administrator.")
