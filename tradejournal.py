# ✅ TRADE JOURNAL APP — MODIFIED FOR SUPABASE v0.4.3

import streamlit as st
import os
import json
import base64
import datetime
from fpdf import FPDF
from PIL import Image
import pandas as pd
import matplotlib.pyplot as plt
import pytz
import re
from streamlit_autorefresh import st_autorefresh
import plotly.graph_objects as go
import plotly.express as px
import unicodedata
import glob
import requests
from datetime import timedelta
import streamlit.components.v1 as components
from supabase import create_client, Client
from supabase_config import get_supabase_client

# Initialize Supabase client
supabase: Client = get_supabase_client()

# Page config
st.set_page_config(page_title="📘 Trade Journal", layout="wide")

st.set_page_config(
    page_title="Trade Journal",
    page_icon="images/favicon.png",  # Relative path to the favicon
    layout="wide"
)


# Login form
if "user_id" not in st.session_state:
    st.session_state.user_id = None

if not st.session_state.user_id:
    st.title("📘 Trade Journal Login")
    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        login_button = st.form_submit_button("Login")
        signup_button = st.form_submit_button("Sign Up")

        if login_button:
            try:
                response = supabase.auth.sign_in_with_password({"email": email, "password": password})
                st.session_state.user_id = response.user.id
                st.success("✅ Logged in successfully!")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Login failed: {e}")

        if signup_button:
            try:
                response = supabase.auth.sign_up({"email": email, "password": password})
                st.session_state.user_id = response.user.id
                st.success("✅ Signed up successfully! Please check your email to confirm if required.")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Sign-up failed: {e}")
    st.stop()

# Authentication helper
def check_authentication():
    if not st.session_state.user_id:
        st.error("❌ No authenticated user found. Please log in.")
        st.stop()
    return st.session_state.user_id

def sanitize_text(text):
    if not text:
        return ""
    try:
        normalized = unicodedata.normalize("NFKD", str(text))
        return normalized.encode("latin-1", "ignore").decode("latin-1")
    except Exception:
        return str(text).encode("ascii", "ignore").decode("ascii")

# 🔁 Last mode memory (stored in Supabase)
def load_last_mode():
    user_id = check_authentication()
    if not user_id:
        return "Real"
    try:
        response = supabase.table("settings").select("last_mode").eq("user_id", user_id).execute()
        return response.data[0]["last_mode"] if response.data else "Real"
    except:
        return "Real"

def save_current_mode(selected_mode):
    user_id = check_authentication()
    if not user_id:
        return
    try:
        supabase.table("settings").upsert({"user_id": user_id, "last_mode": selected_mode}).execute()
    except Exception as e:
        st.error(f"Error saving mode: {e}")

if "mode" not in st.session_state:
    st.session_state.mode = load_last_mode()
mode = st.sidebar.radio("🧭 Mode", ["Real", "Demo"], index=0 if st.session_state.mode == "Real" else 1)
if mode != st.session_state.mode:
    st.session_state.mode = mode
    save_current_mode(mode)

# ✅ FINANCIAL METRICS
def get_account_balance(mode):
    user_id = check_authentication()
    if not user_id:
        return 0.0
    try:
        trades = supabase.table("trades").select("pnl").eq("trade_type", mode).eq("user_id", user_id).execute().data
        deposits = supabase.table("deposits").select("amount").eq("trade_type", mode).eq("user_id", user_id).execute().data
        withdrawals = supabase.table("withdrawals").select("amount").eq("trade_type", mode).eq("user_id", user_id).execute().data
        base = 0.0
        pnl = sum(t["pnl"] for t in trades) if trades else 0.0
        dep_sum = sum(d["amount"] for d in deposits) if deposits else 0.0
        wd_sum = sum(w["amount"] for w in withdrawals) if withdrawals else 0.0
        return round(base + dep_sum - wd_sum + pnl, 2)
    except Exception as e:
        st.error(f"Error fetching balance: {e}")
        return 0.0

def get_total_pnl(mode):
    user_id = check_authentication()
    if not user_id:
        return 0.0
    try:
        trades = supabase.table("trades").select("pnl").eq("trade_type", mode).eq("user_id", user_id).execute().data
        return round(sum(t["pnl"] for t in trades), 2) if trades else 0.0
    except:
        return 0.0

def get_today_pnl(mode):
    user_id = check_authentication()
    if not user_id:
        return 0.0
    today = datetime.datetime.now().strftime("%d/%m/%Y")
    try:
        trades = supabase.table("trades").select("pnl, entry_time").eq("trade_type", mode).eq("user_id", user_id).execute().data
        return round(sum(t["pnl"] for t in trades if today in t["entry_time"]), 2)
    except:
        return 0.0

def get_pips_and_stats(mode):
    user_id = check_authentication()
    if not user_id:
        return 0.0, 0.0, 0, 0, "N/A"
    total_pips = today_pips = wins = losses = 0.0
    today = datetime.datetime.now().strftime("%d/%m/%Y")
    last_trade_date = "N/A"
    try:
        trades = supabase.table("trades").select("*").eq("trade_type", mode).eq("user_id", user_id).execute().data
        for t in trades:
            pnl = t.get("pnl", 0)
            entry = float(t.get("entry", 0))
            exit_price = float(t.get("exit", 0))
            symbol = t.get("symbol", "XAUUSD")
            pip_value = 0.1 if symbol == "XAUUSD" else (0.01 if symbol == "USDJPY" else 0.0001)
            pips = t.get("pips", round(abs(exit_price - entry) / pip_value, 1))
            net_pips = pips if pnl >= 0 else -pips
            total_pips += net_pips
            if today in t.get("entry_time", ""):
                today_pips += net_pips
            if pnl >= 0:
                wins += 1
            elif pnl < 0:
                losses += 1
            last_trade_date = t.get("entry_time", "N/A")
        return round(total_pips, 1), round(today_pips, 1), int(wins), int(losses), last_trade_date
    except:
        return 0.0, 0.0, 0, 0, "N/A"

# Financial calculations
current_balance = get_account_balance(mode)
total_pnl = get_total_pnl(mode)
today_pnl = get_today_pnl(mode)
total_pips, today_pips, wins, losses, last_trade = get_pips_and_stats(mode)

# Color function
def pnl_class(pnl):
    if pnl > 0:
        return "green-card"
    elif pnl < 0:
        return "red-card"
    return ""

import streamlit as st
import streamlit.components.v1 as components

# Clock display
with st.container():
    components.html("""
    <style>
    .clock-container {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 24px;
        justify-content: center;
        margin: 8px 4px;
        padding-bottom: 12px;
        font-family: 'Montserrat', sans-serif;
        max-width: 100%;
    }
    .clock-card {
        background: #f9f9f9;
        padding: 5px;
        border-radius: 8px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
        text-align: center;
        width: 100%;
        max-width: 100px;
        margin: 0 auto;
        box-sizing: border-box;
    }
    .clock-flag {
        font-size: 12px;
        margin-bottom: 2px;
    }
    .clock-label {
        font-weight: 600;
        font-size: 10px;
        margin-bottom: 2px;
    }
    .clock-time {
        font-size: 11px;
        color: #333;
        font-weight: 500;
    }
    @media (max-width: 600px) {
        .clock-container {
            gap: 24px;
            margin: 6px 2px;
            padding-bottom: 10px;
        }
        .clock-card {
            max-width: 100px;
            padding: 5px;
        }
    }
    </style>
    <div class="clock-container">
      <div class="clock-card">
        <div class="clock-flag">🇮🇳</div>
        <div class="clock-label">IST</div>
        <div class="clock-time" id="ist">--:--:--</div>
      </div>
      <div class="clock-card">
        <div class="clock-flag">🇯🇵</div>
        <div class="clock-label">Tokyo</div>
        <div class="clock-time" id="tokyo">--:--:--</div>
      </div>
      <div class="clock-card">
        <div class="clock-flag">🇬🇧</div>
        <div class="clock-label">London</div>
        <div class="clock-time" id="london">--:--:--</div>
      </div>
      <div class="clock-card">
        <div class="clock-flag">🇺🇸</div>
        <div class="clock-label">New York</div>
        <div class="clock-time" id="ny">--:--:--</div>
      </div>
    </div>
    <script>
    function updateClocks() {
        const options = {
            hour: '2-digit', minute: '2-digit', second: '2-digit',
            hour12: true
        };
        document.getElementById("ist").innerText =
            new Date().toLocaleString("en-US", { ...options, timeZone: "Asia/Kolkata" });
        document.getElementById("tokyo").innerText =
            new Date().toLocaleString("en-US", { ...options, timeZone: "Asia/Tokyo" });
        document.getElementById("london").innerText =
            new Date().toLocaleString("en-US", { ...options, timeZone: "Europe/London" });
        document.getElementById("ny").innerText =
            new Date().toLocaleString("en-US", { ...options, timeZone: "America/New_York" });
    }
    setInterval(updateClocks, 1000);
    updateClocks();
    </script>
    """, height=180)

# Metric cards (unchanged)
def box_style(bg_color):
    return f"""
        background-color: {bg_color};
        padding: 10px 8px;
        border-radius: 8px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.06);
        text-align: center;
        font-weight: 500;
        font-size: 13px;
        line-height: 1.4;
        margin-bottom: 10px;
        width: 100%;
        box-sizing: border-box;
    """

def get_pnl_color(pnl):
    return "color: #b33939;" if pnl < 0 else "color: #1a4fa3;"

colors = {
    "balance": "#e6f4ea",
    "pnl": "#e6f0fa",
    "pips": "#fffbe6",
    "neutral": "#f0f0f0"
}

# Custom CSS for metric cards layout
st.markdown("""
<style>
@media (max-width: 600px) {
    .stColumn > div {
        width: 100% !important;
        margin-bottom: 10px;
    }
}
.metric-row {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 10px;
    margin: 10px 4px;
}
.last-metric-row {
    display: grid;
    grid-template-columns: 1fr;
    max-width: 33.33%;
    margin: 10px auto;
}
@media (max-width: 600px) {
    .metric-row {
        grid-template-columns: 1fr;
    }
    .last-metric-row {
        max-width: 100%;
    }
}
</style>
""", unsafe_allow_html=True)

# First row of metric cards (3 cards)
with st.container():
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        st.markdown(f"<div style='{box_style(colors['balance'])} color:#1a7f2e;'>"
                    f"<b>💰 {mode} Balance</b><br>${current_balance:.2f}</div>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"<div style='{box_style(colors['pnl'])} {get_pnl_color(total_pnl)}'>"
                    f"<b>📈 Total PnL</b><br>${total_pnl:.2f}</div>", unsafe_allow_html=True)
    with col3:
        st.markdown(f"<div style='{box_style(colors['pnl'])} {get_pnl_color(today_pnl)}'>"
                    f"<b>📆 Today's PnL</b><br>${today_pnl:.2f}</div>", unsafe_allow_html=True)

# Second row of metric cards (3 cards)
with st.container():
    col4, col5, col6 = st.columns([1, 1, 1])
    with col4:
        st.markdown(f"<div style='{box_style(colors['pips'])} color:#a67c00;'>"
                    f"<b>📊 Total Pips</b><br>{total_pips:.1f} pips</div>", unsafe_allow_html=True)
    with col5:
        st.markdown(f"<div style='{box_style(colors['pips'])} color:#a67c00;'>"
                    f"<b>📅 Today's Pips</b><br>{today_pips:.1f} pips</div>", unsafe_allow_html=True)
    with col6:
        st.markdown(f"<div style='{box_style(colors['neutral'])} color:#333;'>"
                    f"<b>✅ Wins vs Losses</b><br>{wins} Wins | {losses} Losses</div>", unsafe_allow_html=True)

# Last row of metric cards (1 card, centered)
with st.container():
    st.markdown(f"<div class='last-metric-row'><div style='{box_style(colors['neutral'])} color:#333;'>"
                f"<b>🗓 Last Trade</b><br>{last_trade}</div></div>", unsafe_allow_html=True)
                
                
# Tabs
tabs = [
    "📘 Journal", "🔥 Streak Tracker",
    "💸 Deposits & Withdrawals", "📈 PnL Overview", "📊 Stats Dashboard", "🗓 Calendar View",
    "📁 Trade Archive", "🧠 Edge Analysis", "🧪 Strategy Builder", "🌡 Setup Heatmap",
    "📐 Calculators", "📍 Profit Roadmap Creator", "🪙 Currency Converter", "🛠️ Trade Tools",
    "🎶 Motivational Music Time"
]
tab = st.sidebar.radio("📁 Select Tab", tabs)

# Strategy Manager in Sidebar
with st.sidebar.expander("🎯 Strategy Manager"):
    user_id = check_authentication()
    strategies = ["#Breakout", "#Reversal", "#News", "#Scalp", "#Swing"]
    if user_id:
        try:
            strategies = supabase.table("strategies").select("name").eq("trade_type", mode).eq("user_id", user_id).execute().data
            strategies = [s["name"] for s in strategies]
        except:
            pass

    st.markdown("### ➕ Add New Strategy")
    add_new = st.text_input("New Strategy (start with #):")
    if st.button("✅ Add Strategy"):
        if add_new.startswith("#") and add_new not in strategies:
            if not user_id:
                st.stop()
            try:
                supabase.table("strategies").insert({
                    "name": add_new,
                    "trade_type": mode,
                    "user_id": user_id
                }).execute()
                st.success(f"✅ Added {add_new}")
                st.rerun()
            except Exception as e:
                st.error(f"Error adding strategy: {e}")
        elif not add_new.startswith("#"):
            st.error("❌ Strategy must start with #")
        else:
            st.info("ℹ️ Already exists.")

    st.markdown("### ❌ Delete Strategies")
    strategies_to_delete = st.multiselect("Select strategies to delete", strategies)
    if st.button("🗑️ Delete Selected Strategies"):
        if not user_id:
            st.stop()
        try:
            for s in strategies_to_delete:
                supabase.table("strategies").delete().eq("name", s).eq("trade_type", mode).eq("user_id", user_id).execute()
            st.success("✅ Deleted")
            st.rerun()
        except Exception as e:
            st.error(f"Error deleting strategies: {e}")

# ✅ JOURNAL TAB
if tab == "📘 Journal":
    st.title(f"📘 {mode} Trade Journal")

    user_id = check_authentication()
    strategies = ["#Breakout", "#Reversal", "#News", "#Scalp", "#Swing"]
    if user_id:
        try:
            strategies = supabase.table("strategies").select("name").eq("user_id", user_id).execute().data
            strategies = [s["name"] for s in strategies]
        except:
            pass

    pair_multipliers = {
        "XAUUSD": 10,  # 1 pip = 0.1 price movement, $10 per pip per lot
        "BTCUSD": 1,   # 1 pip = 1 price movement
        "EURUSD": 10000,  # 1 pip = 0.0001 price movement
        "USDJPY": 100,    # 1 pip = 0.01 price movement
        "GBPUSD": 10000   # 1 pip = 0.0001 price movement
    }

    st.markdown("### 🎯 Select Strategy Hashtags (Multiple):")
    selected_strategies = st.multiselect("Select Strategies", strategies)

    with st.form("journal_form"):
        symbol = st.selectbox("Symbol", list(pair_multipliers.keys()))
        position = st.radio("Trade Direction", ["Long", "Short"])
        session = st.selectbox("🕒 Session Traded", ["London", "New York", "Asian", "Other"])
        entry = st.number_input("Entry Price", format="%.5f")
        exit = st.number_input("Exit Price", format="%.5f")
        sl = st.number_input("Stop Loss (SL)", format="%.5f")
        tp = st.number_input("Take Profit (TP)", format="%.5f")
        lot = st.number_input("Lot Size", format="%.2f")
        commission = st.number_input("Commission ($)", format="%.2f")
        trade_number = st.text_input("Trade Number (e.g. T123)")
        position_id = st.text_input("Position ID")
        entry_str = st.text_input("Entry Date & Time (DD/MM/YYYY HH:MM:SS)")
        exit_str = st.text_input("Exit Date & Time (DD/MM/YYYY HH:MM:SS)")
        rating = st.slider("Rating (out of 10)", 1, 10, 5)
        notes = ", ".join(selected_strategies)
        screenshot = st.file_uploader("Screenshot (optional)", type=["png", "jpg"])
        pdf_name_input = st.text_input("Custom PDF name (optional)")

        st.markdown("### ✅ Post-Trade Reflection")
        questions = [
            "Followed your trading plan?",
            "Avoided FOMO?",
            "Clear and valid setup?",
            "No revenge trading?",
            "Proper risk taken?"
        ]
        reflection = {q: st.checkbox(q) for q in questions}
        reflection_notes = st.text_area("🧠 Reflection Notes")

        submitted = st.form_submit_button("✅ Save Trade")

        if submitted:
            if not user_id:
                st.stop()
            try:
                entry_dt = datetime.datetime.strptime(entry_str, "%d/%m/%Y %H:%M:%S")
                exit_dt = datetime.datetime.strptime(exit_str, "%d/%m/%Y %H:%M:%S")
            except:
                st.error("❌ Invalid Date-Time format. Use DD/MM/YYYY HH:MM:SS")
                st.stop()

            now = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            multiplier = pair_multipliers.get(symbol, 1)
            pip_diff = (exit - entry) if position == "Long" else (entry - exit)
            pips_captured = round(pip_diff * multiplier, 1)
            if symbol == "XAUUSD":
                # For XAUUSD: PnL = pips * lot * $10/pip - commission
                pnl = round(pips_captured * lot * 10 - abs(commission), 2)
            else:
                # For other pairs: PnL = pips * lot * multiplier * pip_size ($1 per pip for forex)
                pip_size = 0.0001 if symbol in ["EURUSD", "GBPUSD"] else 0.01 if symbol == "USDJPY" else 1
                pnl = round(pips_captured * lot * pip_size * multiplier - abs(commission), 2)
            risk = abs(entry - sl)
            reward = abs(tp - entry)
            rrr = round(reward / risk, 2) if risk != 0 else None
            duration = str(exit_dt - entry_dt)

            pdf_name = sanitize_text(pdf_name_input) if pdf_name_input else f"{sanitize_text(symbol)}_{now}"
            pdf_filename = f"{user_id}/{pdf_name}.pdf"  # Organize by user_id

            # Verify buckets exist
            try:
                buckets = supabase.storage.list_buckets()
                bucket_names = [bucket.name for bucket in buckets]
                if "screenshots" not in bucket_names or "pdfs" not in bucket_names:
                    st.error("❌ Required buckets ('screenshots' or 'pdfs') not found in Supabase. Please create them.")
                    st.stop()
            except Exception as e:
                st.error(f"Error checking storage buckets: {e}")
                st.stop()

            screenshot_url = None
            screenshot_path = None
            if screenshot:
                try:
                    screenshot_path = f"{user_id}/screenshot_{now}.png"
                    file_data = screenshot.read()
                    supabase.storage.from_("screenshots").upload(screenshot_path, file_data, {"content-type": screenshot.type})
                    # Verify screenshot upload
                    file_list = supabase.storage.from_("screenshots").list(path=user_id)
                    if screenshot_path.split("/")[-1] not in [f["name"] for f in file_list if "name" in f]:
                        raise Exception("Screenshot not found in bucket after upload")
                    # Use signed URL to avoid public access issues
                    screenshot_url = supabase.storage.from_("screenshots").create_signed_url(screenshot_path, expires_in=60)["signedURL"]
                except Exception as e:
                    st.warning(f"⚠️ Failed to upload screenshot to Supabase: {e} (Path: {screenshot_path})")
                    screenshot_url = None
                    screenshot_path = None

            trade = {
                "symbol": symbol,
                "position": position,
                "entry": entry,
                "exit": exit,
                "sl": sl,
                "tp": tp,
                "lot_size": lot,
                "commission": commission,
                "pips": pips_captured,
                "pnl": pnl,
                "rrr": rrr,
                "trade_number": trade_number,
                "position_id": position_id,
                "rating": rating,
                "notes": notes,
                "entry_time": entry_str,
                "exit_time": exit_str,
                "duration": duration,
                "strategies": selected_strategies,
                "reflection": reflection,
                "reflection_notes": reflection_notes,
                "pdf_name": pdf_filename,
                "screenshot": screenshot_url,
                "trade_type": mode,
                "time": now,
                "user_id": user_id
            }

            try:
                supabase.table("trades").insert(trade).execute()
                st.success(f"✅ Trade saved with PDF name: {pdf_filename}")
            except Exception as e:
                st.error(f"Error saving trade to database: {e}")
                st.stop()

            # PDF Export
            pdf = FPDF()
            pdf.add_page()
            logo_path = f"logos/{sanitize_text(symbol)}.png"
            if os.path.exists(logo_path):
                pdf.image(logo_path, x=85, y=10, w=40)
            pdf.ln(50)
            pdf.set_font("Times", "B", 16)
            pdf.set_text_color(0, 0, 0)
            pdf.cell(0, 10, f"Trade Summary - {sanitize_text(symbol)} ({mode} Mode)", 0, 1, "C")
            pdf.set_font("Helvetica", "B", 14)
            pdf.set_text_color(0, 200, 0) if position == "Long" else pdf.set_text_color(200, 0, 0)
            pdf.cell(0, 10, f"Position: {'LONG (Buy)' if position == 'Long' else 'SHORT (Sell)'}", 0, 1)
            pdf.set_text_color(0)
            pdf.set_font("Helvetica", "", 12)
            pdf.cell(0, 8, f"Entry: {entry}", 0, 1)
            pdf.cell(0, 8, f"Exit: {exit}", 0, 1)
            pdf.cell(0, 8, f"SL: {sl}", 0, 1)
            pdf.cell(0, 8, f"TP: {tp}", 0, 1)
            pdf.cell(0, 8, f"Lot: {lot}", 0, 1)
            pdf.cell(0, 8, f"Session Traded: {sanitize_text(session)}", 0, 1)
            pdf.cell(0, 8, f"Commission: ${commission}", 0, 1)
            pdf.cell(0, 8, f"Pips Captured: {pips_captured}", 0, 1)
            if rrr is not None:
                pdf.set_text_color(0, 180, 0) if rrr >= 2 else pdf.set_text_color(200, 0, 0)
                pdf.cell(0, 8, f"Risk-Reward: {rrr}", 0, 1)
            pdf.set_text_color(0, 180, 0) if pnl >= 0 else pdf.set_text_color(200, 0, 0)
            pdf.set_font("Helvetica", "B", 14)
            pdf.cell(0, 8, f"PnL: ${pnl}", 0, 1)
            pdf.set_text_color(0)
            pdf.set_font("Helvetica", "", 12)
            pdf.multi_cell(0, 8, f"Entry Time: {entry_str}\nExit Time: {exit_str}\nDuration: {duration}")
            pdf.set_text_color(0, 0, 200)
            pdf.set_font("Helvetica", "U", 12)
            pdf.cell(0, 8, f"Position ID: {sanitize_text(position_id)}", 0, 1)
            pdf.set_text_color(0)
            pdf.set_font("Helvetica", "", 12)
            pdf.multi_cell(0, 8, f"Rating: {rating}/10")
            pdf.multi_cell(0, 8, f"Strategies: {sanitize_text(notes)}")
            pdf.multi_cell(0, 8, "Reflection:")
            for q, ans in reflection.items():
                pdf.multi_cell(0, 8, f"- {sanitize_text(q)}: {'Yes' if ans else 'No'}")
            pdf.multi_cell(0, 8, "Reflection Notes:")
            for line in reflection_notes.split("\n"):
                pdf.multi_cell(0, 8, f"- {sanitize_text(line.strip())}")

            if screenshot_url and screenshot_path:
                try:
                    import tempfile
                    response = requests.get(screenshot_url, timeout=5)
                    response.raise_for_status()  # Raise exception for bad status codes
                    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
                        temp_file.write(response.content)
                        temp_file_path = temp_file.name
                    pdf.image(temp_file_path, x=15, w=180)
                    os.remove(temp_file_path)
                except Exception as e:
                    st.warning(f"⚠️ Failed to add screenshot to PDF: {e} (URL: {screenshot_url}, Path: {screenshot_path})")

            try:
                pdf_data = pdf.output(dest="S").encode("latin-1", errors="ignore")
                # Retry upload up to 3 times
                for attempt in range(3):
                    try:
                        supabase.storage.from_("pdfs").upload(pdf_filename, pdf_data, {"content-type": "application/pdf"})
                        # Verify PDF upload
                        file_list = supabase.storage.from_("pdfs").list(path=user_id)
                        if pdf_filename.split("/")[-1] not in [f["name"] for f in file_list if "name" in f]:
                            raise Exception("PDF not found in bucket after upload")
                        st.success(f"✅ PDF saved to bucket 'pdfs': {pdf_filename}")
                        break
                    except Exception as e:
                        if attempt == 2:
                            st.error(f"Error saving PDF to Supabase after 3 attempts: {e} (Path: {pdf_filename})")
                            st.stop()
                        time.sleep(1)  # Wait before retry
            except Exception as e:
                st.error(f"Error generating or saving PDF: {e}")
                st.stop()

elif tab == "📈 PnL Overview":
    st.header("📈 Live PnL Line Graph")
    user_id = check_authentication()
    if not user_id:
        st.stop()

    history_daily = {}
    try:
        trades = supabase.table("trades").select("entry_time, pnl").eq("trade_type", mode).eq("user_id", user_id).execute().data
        for trade in trades:
            date = trade["entry_time"].split(" ")[0]
            pnl = trade["pnl"]
            history_daily[date] = history_daily.get(date, 0) + pnl
    except:
        history_daily = {}

    if not history_daily:
        st.warning("No trades yet.")
    else:
        sorted_dates = sorted(history_daily.keys(), key=lambda x: datetime.datetime.strptime(x, "%d/%m/%Y"))
        cum_pnl_values = []
        daily_pnl_values = []
        cum_pnl = 0
        for date in sorted_dates:
            daily = history_daily[date]
            cum_pnl += daily
            daily_pnl_values.append(daily)
            cum_pnl_values.append(round(cum_pnl, 2))

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=sorted_dates,
            y=cum_pnl_values,
            mode='lines+markers',
            name='Cumulative PnL',
            line=dict(color='lime', width=2),
            marker=dict(size=6)
        ))
        fig.add_trace(go.Scatter(
            x=[sorted_dates[-1]],
            y=[cum_pnl_values[-1]],
            mode='markers+text',
            name='Latest',
            marker=dict(size=14, color='red', opacity=0.9, symbol='circle-open-dot'),
            text=[f"${cum_pnl_values[-1]:.2f}"],
            textposition='top center',
            showlegend=False
        ))
        fig.add_trace(go.Bar(
            x=sorted_dates,
            y=daily_pnl_values,
            name='Daily PnL',
            yaxis='y2',
            opacity=0.5,
            marker_color='lightblue'
        ))
        fig.update_layout(
            title=f"{mode} Account PnL Overview",
            xaxis_title="Date",
            yaxis=dict(title="Cumulative PnL"),
            yaxis2=dict(title="Daily PnL", overlaying='y', side='right'),
            template="plotly_dark",
            height=500,
            margin=dict(l=40, r=40, t=40, b=40),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig, use_container_width=True)

elif tab == "🗓 Calendar View":
    st.header(f"🗓 {mode} Calendar View")
    user_id = check_authentication()
    if not user_id:
        st.stop()

    all_trades = []
    try:
        all_trades = supabase.table("trades").select("*").eq("trade_type", mode).eq("user_id", user_id).execute().data
    except:
        all_trades = []

    if not all_trades:
        st.info("No trades yet.")
    else:
        symbol_options = sorted(list(set(t["symbol"] for t in all_trades)))
        selected_symbol = st.selectbox("🔎 Filter by symbol", ["All"] + symbol_options)
        date_options = sorted(list(set(t["entry_time"].split(" ")[0] for t in all_trades)))
        selected_date = st.selectbox("📅 Filter by date", ["All"] + date_options)

        filtered = []
        for t in all_trades:
            if selected_symbol != "All" and t["symbol"] != selected_symbol:
                continue
            if selected_date != "All" and not t["entry_time"].startswith(selected_date):
                continue
            filtered.append(t)

        if not filtered:
            st.warning("No trades match the filters.")
        else:
            trades_by_date = {}
            for t in filtered:
                d = t["entry_time"].split(" ")[0]
                trades_by_date.setdefault(d, []).append(t)

            for date in sorted(trades_by_date.keys(), key=lambda x: datetime.datetime.strptime(x, "%d/%m/%Y"), reverse=True):
                trades = trades_by_date[date]
                total_pnl = sum(t["pnl"] for t in trades)
                pnl_color = "lime" if total_pnl >= 0 else "red"

                st.markdown(f"### 📅 {date} | 💰 <span style='color:{pnl_color}; font-weight:bold;'>Total PnL: ${total_pnl:.2f}</span>", unsafe_allow_html=True)

                for trade in trades:
                    logo_path = f"logos/{sanitize_text(trade['symbol'])}.png"
                    symbol_logo = ""
                    if os.path.exists(logo_path):
                        with open(logo_path, "rb") as img:
                            symbol_logo = base64.b64encode(img.read()).decode("utf-8")

                    pnl_color = "lime" if trade["pnl"] >= 0 else "red"
                    direction = "Buy" if trade["position"] == "Long" else "Sell"
                    direction_color = "green" if direction == "Buy" else "red"

                    sl_hit = abs(trade["exit"] - trade["sl"]) < abs(trade["exit"] - trade["tp"])
                    tp_hit = abs(trade["exit"] - trade["tp"]) < abs(trade["exit"] - trade["sl"])
                    sl_color = "red" if sl_hit else "#555"
                    tp_color = "green" if tp_hit else "#555"

                    summary_html = f"""
                    <div style='display:flex; align-items:center; gap:8px; padding:10px; background:#111; border-radius:8px;'>
                        <img src='data:image/png;base64,{symbol_logo}' width='20'>
                        <b>{trade['symbol']}</b> | 
                        <b style='color:{direction_color}'>{direction}</b> |
                        {trade['entry']} ➜ {trade['exit']} |
                        💰 <span style='color:{pnl_color};'>${trade['pnl']:.2f}</span> |
                        <span style='color:{sl_color}; font-weight:bold;'>🛑 SL</span> |
                        <span style='color:{tp_color}; font-weight:bold;'>🎯 TP</span> |
                        🔢 {trade['lot_size']} lots
                    </div>
                    """
                    with st.container():
                        st.markdown(summary_html, unsafe_allow_html=True)
                        with st.expander("🔍 View trade details"):
                            st.write(f"**Trade Number:** {trade['trade_number']}")
                            st.write(f"**Position ID:** {trade['position_id']}")
                            st.write(f"**Entry Time:** {trade['entry_time']}")
                            st.write(f"**Exit Time:** {trade['exit_time']}")
                            st.write(f"**Duration:** {trade['duration']}")
                            st.write(f"**Commission:** ${trade['commission']}")
                            st.write(f"**Rating:** {trade['rating']}/10")
                            st.write(f"**SL:** {trade['sl']} | **TP:** {trade['tp']}")
                            st.write(f"**Risk–Reward Ratio:** {trade.get('rrr', '-')}")
                            st.markdown(f"**Notes:** {trade.get('notes', '-')}")
                            st.markdown(f"**Reflection:**")
                            for q, v in trade.get("reflection", {}).items():
                                st.write(f"- {q}: {'✅' if v else '❌'}")
                            st.markdown(f"**Reflection Notes:** {trade.get('reflection_notes', '-')}")
                            if trade.get("screenshot"):
                                try:
                                    st.image(trade["screenshot"])
                                except:
                                    st.warning("⚠️ Screenshot not found.")
                            else:
                                st.info("ℹ️ No screenshot uploaded.")

elif tab == "🛠️ Trade Tools":
    st.header(f"🗑 Delete a Trade ({mode} Mode)")
    user_id = check_authentication()
    if not user_id:
        st.stop()

    try:
        trade_files = supabase.table("trades").select("trade_number, time").eq("trade_type", mode).eq("user_id", user_id).execute().data
        matching_trades = [(t["trade_number"], t["time"]) for t in trade_files]
    except:
        matching_trades = []

    trade_options = [f"{t[0]} (trade_{t[1]}.json)" for t in matching_trades]

    if trade_options:
        selected = st.selectbox("Select a Trade to Delete", trade_options)
        if st.button("❌ Delete Selected Trade"):
            selected_time = [t[1] for t in matching_trades if selected.startswith(t[0])][0]
            try:
                trade = supabase.table("trades").select("pdf_name, screenshot").eq("time", selected_time).eq("user_id", user_id).execute().data[0]
                try:
                    if trade["pdf_name"]:
                        supabase.storage.from_("pdfs").remove([trade["pdf_name"]])
                    if trade["screenshot"]:
                        screenshot_name = trade["screenshot"].split("/")[-1]
                        supabase.storage.from_("screenshots").remove([screenshot_name])
                except Exception as e:
                    st.warning(f"⚠️ Failed to delete storage files: {e}")
                supabase.table("trades").delete().eq("time", selected_time).eq("user_id", user_id).execute()
                st.success(f"✅ Trade {selected} deleted.")
                st.rerun()
            except Exception as e:
                st.error(f"Error deleting trade: {e}")
    else:
        st.info("No trades found for this mode.")

elif tab == "📊 Stats Dashboard":
    st.header(f"📊 {mode} Stats Overview")
    user_id = check_authentication()
    if not user_id:
        st.stop()
    total_trades, wins, losses, total_pnl, total_pips = 0, 0, 0, 0, 0
    setup_counts = {}

    try:
        trades = supabase.table("trades").select("*").eq("trade_type", mode).eq("user_id", user_id).execute().data
        for t in trades:
            total_trades += 1
            total_pnl += t["pnl"]
            if t["pnl"] > 0:
                wins += 1
            elif t["pnl"] < 0:
                losses += 1
            tags = [x.strip() for x in t["notes"].split() if x.startswith("#")]
            for tag in tags:
                setup_counts[tag] = setup_counts.get(tag, 0) + 1
    except:
        pass

    st.metric("Total Trades", total_trades)
    st.metric("Total PnL", f"${total_pnl:.2f}")
    if total_trades > 0:
        win_rate = (wins / total_trades) * 100
        st.metric("Win Rate", f"{win_rate:.1f}%")

    st.markdown("### 🔖 Most Used Tags")
    if setup_counts:
        tag_df = pd.DataFrame(list(setup_counts.items()), columns=["Tag", "Count"])
        st.bar_chart(tag_df.set_index("Tag"))
    else:
        st.info("No setup tags used yet.")

elif tab == "🌡 Setup Heatmap":
    st.header(f"🌡 Setup Frequency Heatmap ({mode})")
    user_id = check_authentication()
    if not user_id:
        st.stop()
    tag_freq = {}

    try:
        trades = supabase.table("trades").select("notes").eq("trade_type", mode).eq("user_id", user_id).execute().data
        for t in trades:
            tags = [x for x in t["notes"].split() if x.startswith("#")]
            for tag in tags:
                tag_freq[tag] = tag_freq.get(tag, 0) + 1
    except:
        tag_freq = {}

    if tag_freq:
        heatmap_df = pd.DataFrame(sorted(tag_freq.items(), key=lambda x: -x[1]), columns=["Setup", "Frequency"])
        st.dataframe(heatmap_df)
        st.bar_chart(heatmap_df.set_index("Setup"))
    else:
        st.info("No setups found yet.")

elif tab == "📐 Calculators":
    st.header("📐 Multi-Tool Trading Calculator")
    tool = st.radio("🧮 Choose Calculator", ["Lot Size", "Pip Value", "Risk Amount", "PnL"], horizontal=True)
    pair = st.selectbox("Select Pair", ["XAUUSD", "BTCUSD", "EURUSD", "USDJPY", "GBPUSD"])

    settings = {
        "XAUUSD": {"multiplier": 100, "pip": 0.1},
        "BTCUSD": {"multiplier": 1, "pip": 1},
        "EURUSD": {"multiplier": 100000, "pip": 0.0001},
        "USDJPY": {"multiplier": 100000, "pip": 0.01},
        "GBPUSD": {"multiplier": 100000, "pip": 0.0001}
    }

    multiplier = settings[pair]["multiplier"]
    pip_size = settings[pair]["pip"]

    if tool == "Lot Size":
        st.subheader("🎯 Lot Size Calculator")
        balance = st.number_input("Account Balance ($)", format="%.2f")
        risk_percent = st.slider("Risk %", 0.1, 10.0, 1.0)
        sl_pips = st.number_input("Stop Loss (pips)", format="%.2f")
        if sl_pips > 0:
            risk_amount = (risk_percent / 100) * balance
            lot_size = risk_amount / (sl_pips * pip_size * multiplier)
            st.success(f"✅ Max Lot Size: **{lot_size:.2f} lots**")

    elif tool == "Pip Value":
        st.subheader("📏 Pip Value + Distance Calculator")
        entry_price = st.number_input("Entry Price", format="%.10f")
        exit_price = st.number_input("Target/Exit Price", format="%.10f")
        lot_size = st.number_input("Lot Size", value=1.0)
        if entry_price > 0 and exit_price > 0 and lot_size > 0:
            pip_distance = abs(exit_price - entry_price) / pip_size
            pip_value = pip_size * lot_size * multiplier
            total_value = pip_distance * pip_value
            st.info(f"📐 Pip Distance: **{pip_distance:.2f} pips**")
            st.success(f"💲 Pip Value: **${pip_value:.2f} per pip**")
            st.success(f"💰 Total Value: **${total_value:.2f} for this move**")

    elif tool == "Risk Amount":
        st.subheader("⚠️ Risk Amount Calculator")
        lot_size = st.number_input("Lot Size", format="%.2f")
        sl_pips = st.number_input("Stop Loss (pips)", format="%.2f")
        if lot_size > 0 and sl_pips > 0:
            risk = lot_size * sl_pips * pip_size * multiplier
            st.success(f"⚠️ Total Risk on Trade: **${risk:.2f}**")

    elif tool == "PnL":
        st.subheader("📈 PnL Calculator")
        direction = st.radio("Trade Direction", ["Long", "Short"], horizontal=True)
        entry_price = st.number_input("Entry Price", format="%.10f")
        exit_price = st.number_input("Exit Price", format="%.10f")
        lot_size = st.number_input("Lot Size", value=1.0)
        commission = st.number_input("Commission ($)", min_value=0.0, value=0.0, format="%.2f")
        if entry_price > 0 and exit_price > 0 and lot_size > 0:
            size = lot_size * multiplier
            if direction == "Long":
                gross_pnl = (exit_price - entry_price) * size
            else:
                gross_pnl = (entry_price - exit_price) * size
            net_pnl = gross_pnl - commission
            pnl_color = "🟢" if net_pnl >= 0 else "🔴"
            st.markdown(f"""
            <div style='background:#111; padding:15px; border-radius:10px; color:white; font-size:16px'>
                💵 <b>Gross PnL:</b> ${gross_pnl:.2f}<br>
                💸 <b>Commission:</b> ${commission:.2f}<br>
                {pnl_color} <b>Net PnL:</b> ${net_pnl:.2f}
            </div>
            """, unsafe_allow_html=True)

elif tab == "📍 Profit Roadmap Creator":
    st.header("📍 Profit Roadmap Creator")
    user_id = check_authentication()
    if not user_id:
        st.stop()

    def load_saved_roadmaps():
        try:
            roadmaps = supabase.table("roadmaps").select("*").eq("trade_type", mode).eq("user_id", user_id).execute().data
            for r in roadmaps:
                st.session_state.roadmaps[r["name"]] = {
                    "risk": r["risk"],
                    "df": pd.DataFrame(r["df"])
                }
        except:
            pass

    def save_roadmap(name, data):
        try:
            supabase.table("roadmaps").upsert({
                "name": name,
                "risk": data["risk"],
                "df": data["df"].to_dict(orient="records"),
                "trade_type": mode,
                "user_id": user_id
            }).execute()
        except Exception as e:
            st.error(f"Error saving roadmap: {e}")

    if "roadmaps" not in st.session_state:
        st.session_state.roadmaps = {}
        load_saved_roadmaps()
    elif not st.session_state.roadmaps:
        load_saved_roadmaps()

    with st.form("create_roadmap"):
        roadmap_name = st.text_input("📘 Roadmap Name", placeholder="e.g. My Plan")
        start_balance_input = st.text_input("💵 Starting Balance ($)", placeholder="enter amount")
        target_balance_input = st.text_input("🎯 Target Balance ($)", placeholder="enter goal")
        growth_percent_input = st.text_input("📈 Growth per Trade (%)", placeholder="e.g. 2")
        risk_percent_input = st.text_input("⚠️ Risk per Trade (%)", placeholder="e.g. 1")
        submit = st.form_submit_button("➕ Create Roadmap")

    try:
        start_balance = float(start_balance_input)
        target_balance = float(target_balance_input)
        growth_percent = float(growth_percent_input)
        risk_percent = float(risk_percent_input)
        inputs_valid = True
    except:
        inputs_valid = False

    if submit and roadmap_name and inputs_valid:
        trades = []
        balance = start_balance
        i = 1
        while balance < target_balance:
            profit_target = round(balance * (growth_percent / 100), 2)
            closing = round(balance + profit_target, 2)
            max_loss = round(balance * (risk_percent / 100), 2)
            trades.append({
                "Trade #": i,
                "Opening Balance": round(balance, 2),
                "Profit Target": profit_target,
                "Planned Closing": closing,
                "Max Loss Allowed": max_loss,
                "Actual P/L": "",
                "Adjusted Balance": closing
            })
            balance = closing
            i += 1

        df = pd.DataFrame(trades)
        st.session_state.roadmaps[roadmap_name] = {
            "risk": risk_percent,
            "df": df
        }
        save_roadmap(roadmap_name, st.session_state.roadmaps[roadmap_name])
        st.success(f"✅ Roadmap '{roadmap_name}' created.")
        st.rerun()

    to_delete = None
    for name, data in st.session_state.roadmaps.items():
        df = data["df"]
        risk = data["risk"]

        with st.expander(f"{name} | Risk: {risk}%", expanded=False):
            edited_df = st.data_editor(
                df,
                use_container_width=True,
                key=f"editor_{name}",
                num_rows="fixed"
            )

            for i in range(len(edited_df)):
                if i == 0:
                    opening = edited_df.loc[0, "Opening Balance"]
                else:
                    opening = edited_df.loc[i - 1, "Adjusted Balance"]
                edited_df.loc[i, "Opening Balance"] = round(opening, 2)
                edited_df.loc[i, "Max Loss Allowed"] = round(opening * float(risk) / 100, 2)
                try:
                    actual_pl = float(edited_df.loc[i, "Actual P/L"])
                except:
                    actual_pl = edited_df.loc[i, "Profit Target"]
                edited_df.loc[i, "Adjusted Balance"] = round(opening + actual_pl, 2)

            st.session_state.roadmaps[name]["df"] = edited_df
            save_roadmap(name, st.session_state.roadmaps[name])

            col1, col2 = st.columns([1, 1])
            with col1:
                class PDF(FPDF):
                    def header(self):
                        self.set_font("Arial", "B", 12)
                        self.cell(0, 10, f"Profit Roadmap - {name}", ln=True, align="C")
                        self.set_font("Arial", "", 10)
                        self.cell(0, 10, f"Risk per Trade: {risk}%", ln=True, align="C")
                        self.ln(5)
                    def footer(self):
                        self.set_y(-15)
                        self.set_font("Arial", "I", 8)
                        self.cell(0, 10, f"Page {self.page_no()}", align="C")

                pdf = PDF()
                pdf.set_auto_page_break(auto=True, margin=15)
                pdf.add_page()
                pdf.set_font("Arial", "B", 9)
                columns = ["Trade #", "Opening Balance", "Profit Target", "Max Loss Allowed", "Actual P/L", "Adjusted Balance"]
                col_widths = [20, 35, 35, 35, 30, 35]
                for i, col in enumerate(columns):
                    pdf.cell(col_widths[i], 8, col, border=1, align="C")
                pdf.ln()
                pdf.set_font("Arial", "", 9)
                for _, row in edited_df.iterrows():
                    values = [
                        str(int(row["Trade #"])),
                        f"${row['Opening Balance']}",
                        f"${row['Profit Target']}",
                        f"${row['Max Loss Allowed']}",
                        str(row["Actual P/L"]),
                        f"${row['Adjusted Balance']}"
                    ]
                    for i, val in enumerate(values):
                        pdf.cell(col_widths[i], 8, val, border=1, align="C")
                    pdf.ln()
                pdf_data = pdf.output(dest="S").encode("latin-1")
                st.download_button(
                    label="⬇️ Download PDF",
                    data=pdf_data,
                    file_name=f"{name.replace(' ', '_')}_roadmap.pdf",
                    mime="application/pdf"
                )
            with col2:
                if st.button(f"🗑️ Delete '{name}'", key=f"delete_{name}"):
                    to_delete = name

    if to_delete:
        try:
            supabase.table("roadmaps").delete().eq("name", to_delete).eq("trade_type", mode).eq("user_id", user_id).execute()
            del st.session_state.roadmaps[to_delete]
            st.rerun()
        except Exception as e:
            st.error(f"Error deleting roadmap: {e}")

elif tab == "🪙 Currency Converter":
    st.header("🪙 Currency Converter")

    subtab1, subtab2 = st.tabs(["🌍 Fiat ↔ Fiat", "🪙 Crypto → Fiat"])

    with subtab1:
        st.subheader("🌍 Convert Between Fiat Currencies")
        col1, col2 = st.columns([2, 1])
        with col1:
            @st.cache_data
            def get_fiat_currencies():
                res = requests.get("https://api.frankfurter.app/currencies")
                return res.json()
            fiat_data = get_fiat_currencies()
            fiat_codes = list(fiat_data.keys())

            if "from_fiat" not in st.session_state:
                st.session_state["from_fiat"] = "USD"
            if "to_fiat" not in st.session_state:
                st.session_state["to_fiat"] = "INR"

            from_fiat = st.selectbox("From", fiat_codes, index=fiat_codes.index(st.session_state["from_fiat"]), key="from_fiat")
            to_fiat = st.selectbox("To", fiat_codes, index=fiat_codes.index(st.session_state["to_fiat"]), key="to_fiat")
            amount = st.number_input("💰 Amount", min_value=0.0, step=10.0, format="%.2f", key="fiat_amount")

            if "fiat_result" not in st.session_state:
                st.session_state["fiat_result"] = ""
            if "fiat_chart_df" not in st.session_state:
                st.session_state["fiat_chart_df"] = None

            if st.button("Convert", key="convert_fiat"):
                if from_fiat == to_fiat:
                    st.warning("⚠️ Please select two different currencies.")
                else:
                    url = f"https://api.frankfurter.app/latest?amount={amount}&from={from_fiat}&to={to_fiat}"
                    res = requests.get(url).json()
                    rate = res['rates'][to_fiat]
                    result_html = f"""
                        <div style='
                            background: linear-gradient(to right, #141e30, #243b55);
                            padding: 1.2rem;
                            border-radius: 12px;
                            margin-top: 1rem;
                            font-size: 1.3rem;
                            color: #f1f1f1;
                            text-align: center;
                            box-shadow: 0px 0px 10px #000;
                        '>
                            💱 <b>{amount} {from_fiat}</b> = <span style="color:#00FFAA;"><b>{rate:.2f} {to_fiat}</b></span>
                        </div>
                    """
                    st.session_state["fiat_result"] = result_html
                    end_date = datetime.datetime.now().date()
                    start_date = end_date - timedelta(days=7)
                    chart_url = f"https://api.frankfurter.app/{start_date}..{end_date}?from={from_fiat}&to={to_fiat}"
                    chart_data = requests.get(chart_url).json()
                    if "rates" in chart_data:
                        df = pd.DataFrame(chart_data["rates"]).T
                        df.index = pd.to_datetime(df.index)
                        df.columns = [f"{from_fiat} → {to_fiat}"]
                        st.session_state["fiat_chart_df"] = df
            if st.session_state["fiat_result"]:
                st.markdown(st.session_state["fiat_result"], unsafe_allow_html=True)
            if st.button("Reset", key="reset_fiat"):
                st.session_state["fiat_result"] = ""
                st.session_state["fiat_chart_df"] = None
            if st.session_state["fiat_chart_df"] is not None:
                st.markdown("### 📈 Last 7 Days Exchange Rate")
                fig = px.line(
                    st.session_state["fiat_chart_df"],
                    x=st.session_state["fiat_chart_df"].index,
                    y=st.session_state["fiat_chart_df"].columns[0],
                    markers=True,
                    template="plotly_dark"
                )
                fig.update_layout(height=350, margin=dict(l=0, r=0, t=30, b=0))
                st.plotly_chart(fig, use_container_width=True)
        with col2:
            st.markdown("### 🧮 Calculator")
            expr = st.text_input("Enter expression (use +, -, *, /)", key="calc1")
            if st.button("Evaluate", key="eval1"):
                try:
                    result = numexpr.evaluate(expr)
                    st.success(f"Result: {result}")
                except:
                    st.error("❌ Invalid expression.")

    with subtab2:
        st.subheader("🪙 Convert Crypto to Fiat")
        col1, col2 = st.columns([2, 1])
        with col1:
            crypto_list = ["bitcoin", "ethereum", "litecoin", "dogecoin", "solana", "ripple", "cardano", "polkadot"]
            fiat_list = ["usd", "inr", "eur", "gbp", "jpy", "aed", "cad"]
            if "crypto_from" not in st.session_state:
                st.session_state["crypto_from"] = "bitcoin"
            if "crypto_to_fiat" not in st.session_state:
                st.session_state["crypto_to_fiat"] = "inr"
            from_crypto = st.selectbox("From (Crypto)", crypto_list, index=crypto_list.index(st.session_state["crypto_from"]), key="from_crypto")
            to_fiat = st.selectbox("To (Fiat)", fiat_list, index=fiat_list.index(st.session_state["crypto_to_fiat"]), key="to_fiat_for_crypto")
            crypto_amount = st.number_input("💰 Amount", min_value=0.0, step=0.0001, format="%.6f", key="crypto_to_fiat_amount")

            if "crypto_fiat_result" not in st.session_state:
                st.session_state["crypto_fiat_result"] = ""
            if "crypto_fiat_chart_df" not in st.session_state:
                st.session_state["crypto_fiat_chart_df"] = None

            if st.button("Convert", key="convert_crypto_to_fiat"):
                price_url = f"https://api.coingecko.com/api/v3/simple/price?ids={from_crypto}&vs_currencies={to_fiat}"
                res = requests.get(price_url).json()
                if from_crypto in res and to_fiat in res[from_crypto]:
                    price = res[from_crypto][to_fiat]
                    converted = crypto_amount * price
                    result_html = f"""
                        <div style='
                            background: linear-gradient(to right, #1c1c1c, #3a3a3a);
                            padding: 1.2rem;
                            border-radius: 12px;
                            margin-top: 1rem;
                            font-size: 1.3rem;
                            color: #f1f1f1;
                            text-align: center;
                            box-shadow: 0px 0px 10px #000;
                        '>
                            💱 {crypto_amount} <b>{from_crypto.capitalize()}</b> = <span style="color:#FFAA00;"><b>{converted:.2f} {to_fiat.upper()}</b></span>
                        </div>
                    """
                    st.session_state["crypto_fiat_result"] = result_html
                    chart_url = f"https://api.coingecko.com/api/v3/coins/{from_crypto}/market_chart?vs_currency={to_fiat}&days=7"
                    data = requests.get(chart_url).json()
                    try:
                        prices = data['prices']
                        df = pd.DataFrame(prices, columns=["timestamp", "price"])
                        df["date"] = pd.to_datetime(df["timestamp"], unit="ms")
                        df = df.set_index("date")
                        st.session_state["crypto_fiat_chart_df"] = df
                    except:
                        st.session_state["crypto_fiat_chart_df"] = None
                else:
                    st.error("❌ Unable to fetch conversion rate.")
                    st.session_state["crypto_fiat_result"] = ""
                    st.session_state["crypto_fiat_chart_df"] = None
            if st.session_state["crypto_fiat_result"]:
                st.markdown(st.session_state["crypto_fiat_result"], unsafe_allow_html=True)
            if st.button("Reset", key="reset_crypto_to_fiat"):
                st.session_state["crypto_fiat_result"] = ""
                st.session_state["crypto_fiat_chart_df"] = None
            if st.session_state["crypto_fiat_chart_df"] is not None:
                st.markdown("### 📈 Last 7 Days Price Chart")
                fig = px.line(
                    st.session_state["crypto_fiat_chart_df"],
                    x=st.session_state["crypto_fiat_chart_df"].index,
                    y="price",
                    markers=True,
                    template="plotly_dark",
                    title=f"{from_crypto.capitalize()} → {to_fiat.upper()} (7 Days)"
                )
                fig.update_layout(height=350, margin=dict(l=0, r=0, t=30, b=0))
                st.plotly_chart(fig, use_container_width=True)
        with col2:
            st.markdown("### 🧮 Calculator")
            expr = st.text_input("Enter expression (use +, -, *, /)", key="calc2")
            if st.button("Evaluate", key="eval2"):
                try:
                    result = numexpr.evaluate(expr)
                    st.success(f"Result: {result}")
                except:
                    st.error("❌ Invalid expression.")
elif tab == "🔥 Streak Tracker":
    st.header(f"🔥 {mode} Streak Tracker")
    user_id = check_authentication()
    if not user_id:
        st.stop()

    def load_streak_data():
        try:
            trades = supabase.table("trades").select("entry_time, pnl").eq("trade_type", mode).eq("user_id", user_id).execute().data
            trades.sort(key=lambda x: x["entry_time"])
            return trades
        except:
            return []

    trades = load_streak_data()
    if not trades:
        st.info("No trades found for this mode.")
    else:
        streaks = []
        current_streak = {"type": None, "count": 0, "start_date": None}
        for trade in trades:
            date = trade["entry_time"].split(" ")[0]
            if trade["pnl"] > 0:
                outcome = "Win"
            elif trade["pnl"] < 0:
                outcome = "Loss"
            else:
                continue

            if current_streak["type"] is None:
                current_streak = {"type": outcome, "count": 1, "start_date": date}
            elif current_streak["type"] == outcome:
                current_streak["count"] += 1
            else:
                streaks.append(current_streak)
                current_streak = {"type": outcome, "count": 1, "start_date": date}
        streaks.append(current_streak)

        if streaks:
            st.markdown("### 🔥 Current Streak")
            current = streaks[-1]
            streak_emoji = "🏆" if current["type"] == "Win" else "😓"
            st.markdown(f"{streak_emoji} {current['count']} {current['type']}{'s' if current['count'] > 1 else ''} (Started: {current['start_date']})")
            
            st.markdown("### 📜 Streak History")
            for streak in reversed(streaks[:-1]):
                streak_emoji = "🏆" if streak["type"] == "Win" else "😓"
                st.write(f"{streak_emoji} {streak['count']} {streak['type']}{'s' if streak['count'] > 1 else ''} (Started: {streak['start_date']})")
        else:
            st.info("No streaks recorded yet.")

elif tab == "🧠 Edge Analysis":
    st.header(f"🧠 {mode} Edge Analysis")
    user_id = check_authentication()
    if not user_id:
        st.stop()

    try:
        trades = supabase.table("trades").select("*").eq("trade_type", mode).eq("user_id", user_id).execute().data
    except:
        trades = []

    if not trades:
        st.info("No trades found for this mode.")
    else:
        strategy_performance = {}
        for trade in trades:
            for strategy in trade["strategies"]:
                if strategy not in strategy_performance:
                    strategy_performance[strategy] = {"wins": 0, "losses": 0, "total_pnl": 0}
                if trade["pnl"] > 0:
                    strategy_performance[strategy]["wins"] += 1
                elif trade["pnl"] < 0:
                    strategy_performance[strategy]["losses"] += 1
                strategy_performance[strategy]["total_pnl"] += trade["pnl"]

        if strategy_performance:
            st.markdown("### 📊 Strategy Performance")
            for strategy, stats in strategy_performance.items():
                total_trades = stats["wins"] + stats["losses"]
                win_rate = (stats["wins"] / total_trades * 100) if total_trades > 0 else 0
                st.markdown(
                    f"""
                    <div style='background:#111; padding:10px; border-radius:8px; margin-bottom:10px;'>
                        <b>{strategy}</b><br>
                        Wins: {stats["wins"]} | Losses: {stats["losses"]} | Win Rate: {win_rate:.1f}%<br>
                        Total PnL: <span style='color:{"lime" if stats["total_pnl"] >= 0 else "red"};'>${stats["total_pnl"]:.2f}</span>
                    </div>
                    """, unsafe_allow_html=True
                )
        else:
            st.info("No strategy performance data available.")

elif tab == "🧪 Strategy Builder":
    st.header(f"🧪 {mode} Strategy Builder")
    user_id = check_authentication()
    if not user_id:
        st.stop()

    try:
        strategies = supabase.table("strategy_builder").select("*").eq("trade_type", mode).eq("user_id", user_id).execute().data
        strategy_names = [s["name"] for s in strategies]
    except:
        strategies = []
        strategy_names = []

    with st.form("strategy_form"):
        strategy_name = st.text_input("Strategy Name", placeholder="e.g. Breakout Strategy")
        entry_rules = st.text_area("📥 Entry Rules")
        exit_rules = st.text_area("📤 Exit Rules")
        risk_management = st.text_area("⚖️ Risk Management")
        notes = st.text_area("📝 Notes")
        submit_strategy = st.form_submit_button("✅ Save Strategy")

        if submit_strategy:
            try:
                strategy_data = {
                    "name": strategy_name,
                    "entry_rules": entry_rules,
                    "exit_rules": exit_rules,
                    "risk_management": risk_management,
                    "notes": notes,
                    "trade_type": mode,
                    "user_id": user_id
                }
                supabase.table("strategy_builder").upsert(strategy_data).execute()
                st.success(f"✅ Strategy '{strategy_name}' saved")
                st.rerun()
            except Exception as e:
                st.error(f"Error saving strategy: {e}")

    if strategies:
        st.markdown("### 📋 Saved Strategies")
        selected_strategy = st.selectbox("Select Strategy to View", strategy_names)
        if selected_strategy:
            strategy = next(s for s in strategies if s["name"] == selected_strategy)
            st.markdown(f"""
            **{strategy['name']}**<br>
            **Entry Rules:** {strategy.get('entry_rules', '-')}<br>
            **Exit Rules:** {strategy.get('exit_rules', '-')}<br>
            **Risk Management:** {strategy.get('risk_management', '-')}<br>
            **Notes:** {strategy.get('notes', '-')}<br>
            """, unsafe_allow_html=True)
            if st.button(f"🗑️ Delete '{selected_strategy}'"):
                try:
                    supabase.table("strategy_builder").delete().eq("name", selected_strategy).eq("trade_type", mode).eq("user_id", user_id).execute()
                    st.success(f"✅ Strategy '{selected_strategy}' deleted")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error deleting strategy: {e}")

elif tab == "📁 Trade Archive":
    st.header(f"📁 {mode} Trade Archive")
    user_id = check_authentication()
    if not user_id:
        st.stop()

    try:
        trades = supabase.table("trades").select("*").eq("trade_type", mode).eq("user_id", user_id).execute().data
        trades = sorted(trades, key=lambda x: x["time"], reverse=True)
    except Exception as e:
        st.error(f"Error fetching trades: {e}")
        trades = []

    if not trades:
        st.info("No trades found for this mode.")
    else:
        # Verify bucket existence
        try:
            buckets = supabase.storage.list_buckets()
            bucket_names = [bucket.name for bucket in buckets]
            st.write(f"DEBUG: Available buckets: {bucket_names}")  # Debug logging
            if "pdfs" not in bucket_names or "screenshots" not in bucket_names:
                st.error("❌ Required buckets ('pdfs' or 'screenshots') not found in Supabase. Please create them.")
                st.stop()
        except Exception as e:
            st.error(f"Error checking storage buckets: {e}")
            st.error("Please check SUPABASE_URL, SUPABASE_KEY, and storage permissions.")
            st.stop()

        for trade in trades:
            logo_path = f"logos/{sanitize_text(trade['symbol'])}.png"
            symbol_logo = ""
            if os.path.exists(logo_path):
                with open(logo_path, "rb") as img:
                    symbol_logo = base64.b64encode(img.read()).decode("utf-8")

            pnl_color = "lime" if trade["pnl"] >= 0 else "red"
            direction = "Buy" if trade["position"] == "Long" else "Sell"
            direction_color = "green" if direction == "Buy" else "red"

            sl_hit = abs(trade["exit"] - trade["sl"]) < abs(trade["exit"] - trade["tp"])
            tp_hit = abs(trade["exit"] - trade["tp"]) < abs(trade["exit"] - trade["sl"])
            sl_color = "red" if sl_hit else "#555"
            tp_color = "green" if tp_hit else "#555"

            with st.container():
                st.markdown(
                    f"""
                    <div style='display:flex; align-items:center; gap:8px; padding:10px; background:#111; border-radius:8px;'>
                        <img src='data:image/png;base64,{symbol_logo}' width='20'>
                        <b>{trade['symbol']}</b> | 
                        <b style='color:{direction_color}'>{direction}</b> |
                        {trade['entry']} ➜ {trade['exit']} |
                        💰 <span style='color:{pnl_color};'>${trade['pnl']:.2f}</span> |
                        <span style='color:{sl_color}; font-weight:bold;'>🛑 SL</span> |
                        <span style='color:{tp_color}; font-weight:bold;'>🎯 TP</span> |
                        🔢 {trade['lot_size']} lots
                    </div>
                    """, unsafe_allow_html=True
                )
                with st.expander(f"🔍 View Trade {trade['trade_number']} Details"):
                    st.write(f"**Trade Number:** {trade['trade_number']}")
                    st.write(f"**Position ID:** {trade['position_id']}")
                    st.write(f"**Entry Time:** {trade['entry_time']}")
                    st.write(f"**Exit Time:** {trade['exit_time']}")
                    st.write(f"**Duration:** {trade['duration']}")
                    st.write(f"**Commission:** ${trade['commission']}")
                    st.write(f"**Rating:** {trade['rating']}/10")
                    st.write(f"**SL:** {trade['sl']} | **TP:** {trade['tp']}")
                    st.write(f"**Risk–Reward Ratio:** {trade.get('rrr', '-')}")
                    st.write(f"**Pips:** {trade['pips']}")
                    st.markdown(f"**Strategies:** {', '.join(trade['strategies'])}")
                    st.markdown(f"**Reflection:**")
                    for q, v in trade.get("reflection", {}).items():
                        st.write(f"- {q}: {'✅' if v else '❌'}")
                    st.markdown(f"**Reflection Notes:** {trade.get('reflection_notes', '-')}")
                    if trade.get("screenshot"):
                        try:
                            screenshot_name = trade["screenshot"].split("/")[-1]
                            screenshot_path = f"{user_id}/{screenshot_name}"
                            signed_url = supabase.storage.from_("screenshots").create_signed_url(screenshot_path, expires_in=60)["signedURL"]
                            st.image(signed_url)
                        except Exception as e:
                            st.warning(f"⚠️ Screenshot not found for trade {trade['trade_number']}: {e} (Path: {screenshot_path})")
                    if trade.get("pdf_name"):
                        try:
                            # Normalize pdf_path
                            pdf_path = trade["pdf_name"].replace("//", "/").strip("/")
                            pdf_filename = pdf_path.split("/")[-1]
                            st.write(f"DEBUG: Checking PDF: {pdf_path}, Expected filename: {pdf_filename}")  # Debug
                            file_list = supabase.storage.from_("pdfs").list(path=user_id)
                            file_names = [f["name"] for f in file_list if "name" in f]
                            st.write(f"DEBUG: Files in pdfs/{user_id}: {file_names}")  # Debug
                            if pdf_filename not in file_names:
                                st.warning(f"⚠️ PDF not found in bucket for trade {trade['trade_number']}: {pdf_path}")
                                # Attempt download anyway
                                try:
                                    pdf_data = supabase.storage.from_("pdfs").download(pdf_path)
                                    st.download_button(
                                        label=f"⬇️ Download PDF (Trade {trade['trade_number']})",
                                        data=pdf_data,
                                        file_name=pdf_filename,
                                        mime="application/pdf"
                                    )
                                except Exception as e:
                                    st.warning(f"⚠️ Unable to download PDF: {e} (Path: {pdf_path})")
                            else:
                                pdf_data = supabase.storage.from_("pdfs").download(pdf_path)
                                st.download_button(
                                    label=f"⬇️ Download PDF (Trade {trade['trade_number']})",
                                    data=pdf_data,
                                    file_name=pdf_filename,
                                    mime="application/pdf"
                                )
                        except Exception as e:
                            st.warning(f"⚠️ Unable to process PDF for trade {trade['trade_number']}: {e} (Path: {pdf_path})")
                    else:
                        st.info("ℹ️ No PDF available for this trade.")
                    if st.button(f"🗑️ Delete Trade {trade['trade_number']}", key=f"delete_{trade['time']}"):
                        try:
                            if trade.get("pdf_name"):
                                try:
                                    supabase.storage.from_("pdfs").remove([trade["pdf_name"]])
                                except Exception as e:
                                    st.warning(f"⚠️ Failed to delete PDF {trade['pdf_name']}: {e}")
                            if trade.get("screenshot"):
                                try:
                                    screenshot_name = trade["screenshot"].split("/")[-1]
                                    screenshot_path = f"{user_id}/{screenshot_name}"
                                    supabase.storage.from_("screenshots").remove([screenshot_path])
                                except Exception as e:
                                    st.warning(f"⚠️ Failed to delete screenshot {screenshot_path}: {e}")
                            supabase.table("trades").delete().eq("time", trade["time"]).eq("user_id", user_id).execute()
                            st.success(f"✅ Trade {trade['trade_number']} deleted")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error deleting trade: {e}")

elif tab == "💸 Deposits & Withdrawals":
    st.header(f"💸 {mode} Deposits & Withdrawals")
    user_id = check_authentication()
    if not user_id:
        st.stop()

    with st.form("deposit_form"):
        deposit_amount = st.number_input("Deposit Amount ($)", min_value=0.0, format="%.2f")
        deposit_date = st.date_input("Deposit Date")
        deposit_notes = st.text_area("Deposit Notes (optional)")
        submit_deposit = st.form_submit_button("➕ Add Deposit")

        if submit_deposit:
            try:
                deposit = {
                    "amount": deposit_amount,
                    "date": deposit_date.strftime("%Y-%m-%d"),
                    "notes": deposit_notes,
                    "trade_type": mode,
                    "timestamp": datetime.datetime.now().strftime("%Y%m%d%H%M%S"),
                    "user_id": user_id
                }
                supabase.table("deposits").insert(deposit).execute()
                st.success(f"✅ Deposit of ${deposit_amount:.2f} added")
                st.rerun()
            except Exception as e:
                st.error(f"Error adding deposit: {e}")

    with st.form("withdrawal_form"):
        withdrawal_amount = st.number_input("Withdrawal Amount ($)", min_value=0.0, format="%.2f")
        withdrawal_date = st.date_input("Withdrawal Date")
        withdrawal_notes = st.text_area("Withdrawal Notes (optional)")
        submit_withdrawal = st.form_submit_button("➖ Add Withdrawal")

        if submit_withdrawal:
            try:
                withdrawal = {
                    "amount": withdrawal_amount,
                    "date": withdrawal_date.strftime("%Y-%m-%d"),
                    "notes": withdrawal_notes,
                    "trade_type": mode,
                    "timestamp": datetime.datetime.now().strftime("%Y%m%d%H%M%S"),
                    "user_id": user_id
                }
                supabase.table("withdrawals").insert(withdrawal).execute()
                st.success(f"✅ Withdrawal of ${withdrawal_amount:.2f} added")
                st.rerun()
            except Exception as e:
                st.error(f"Error adding withdrawal: {e}")

    st.markdown("### 📜 Transaction History")
    try:
        deposits = supabase.table("deposits").select("*").eq("trade_type", mode).eq("user_id", user_id).execute().data
        withdrawals = supabase.table("withdrawals").select("*").eq("trade_type", mode).eq("user_id", user_id).execute().data
    except:
        deposits = []
        withdrawals = []

    if deposits or withdrawals:
        history = []
        for d in deposits:
            history.append({"Type": "Deposit", "Amount": d["amount"], "Date": d["date"], "Notes": d.get("notes", ""), "Timestamp": d["timestamp"]})
        for w in withdrawals:
            history.append({"Type": "Withdrawal", "Amount": -w["amount"], "Date": w["date"], "Notes": w.get("notes", ""), "Timestamp": w["timestamp"]})
        history = sorted(history, key=lambda x: x["Timestamp"], reverse=True)
        history_df = pd.DataFrame(history)
        st.dataframe(history_df[["Type", "Amount", "Date", "Notes"]], use_container_width=True)
    else:
        st.info("No transactions recorded yet.")

# Reset Data
with st.sidebar.expander("⚠️ Reset Data"):
    st.markdown(f"### ⚠️ Reset {mode} Data")
    confirm = st.checkbox(f"I confirm I want to reset ALL {mode} data")
    submit_reset = st.button("🗑️ Reset All Data")
    if submit_reset and confirm:
        user_id = check_authentication()
        if not user_id:
            st.stop()
        try:
            trades = supabase.table("trades").select("pdf_name, screenshot").eq("trade_type", mode).eq("user_id", user_id).execute().data
            for t in trades:
                try:
                    if t["pdf_name"]:
                        supabase.storage.from_("pdfs").remove([t["pdf_name"]])
                    if t["screenshot"]:
                        screenshot_name = t["screenshot"].split("/")[-1]
                        supabase.storage.from_("screenshots").remove([screenshot_name])
                except Exception as e:
                    st.warning(f"⚠️ Failed to delete storage files for trade: {e}")
            supabase.table("trades").delete().eq("trade_type", mode).eq("user_id", user_id).execute()
            supabase.table("deposits").delete().eq("trade_type", mode).eq("user_id", user_id).execute()
            supabase.table("withdrawals").delete().eq("trade_type", mode).eq("user_id", user_id).execute()
            supabase.table("daily_reviews").delete().eq("user_id", user_id).execute()
            supabase.table("roadmaps").delete().eq("trade_type", mode).eq("user_id", user_id).execute()
            st.success(f"✅ All `{mode}` mode data, daily reviews, and roadmaps have been fully reset.")
            st.session_state.clear()
            st.rerun()
        except Exception as e:
            st.error(f"Error resetting data: {e}")
