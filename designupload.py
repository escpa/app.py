import os
import time
import base64
import requests
import streamlit as st

API_BASE = "https://api.printify.com/v1"

# --------------- UI: token input + cleaning ---------------
st.set_page_config(page_title="Printify Auto Uploader — Gildan 64000", page_icon="📦", layout="centered")
st.title("📦 Printify Auto Uploader — Gildan 64000 (Monster Digital)")

raw_token = st.text_input("Printify Merchant API Token", type="password", help="From Printify > Settings > API tokens (Merchant token)")
def clean_token(t: str) -> str:
    t = (t or "").strip()
    # Users sometimes paste with quotes or 'Bearer ' included; strip those.
    if t.lower().startswith("bearer "):
        t = t[7:]
    t = t.strip().strip('"').strip("'")
    return t

api_token = clean_token(raw_token)

def mask_token(t: str) -> str:
    if not t:
        return ""
    if len(t) <= 8:
        return f"{t[:2]}…{t[-2:]}"
    return f"{t[:4]}…{t[-4:]} (len={len(t)})"

HEADERS = {
    "Authorization": f"Bearer {api_token}" if api_token else "",
    "Content-Type": "application/json",
}

# --------------- simple HTTP helpers ---------------
def api_get(path, params=None, retries=3, backoff=1.25):
    url = f"{API_BASE}{path}"
    for i in range(retries):
        resp = requests.get(url, headers=HEADERS, params=params, timeout=20)
        if resp.status_code == 429 and i < retries - 1:
            time.sleep(backoff * (i + 1))
            continue
        resp.raise_for_status()
        return resp

def api_post(path, json=None, retries=3, backoff=1.25):
    url = f"{API_BASE}{path}"
    for i in range(retries):
        resp = requests.post(url, headers=HEADERS, json=json, timeout=30)
        if resp.status_code == 429 and i < retries - 1:
            time.sleep(backoff * (i + 1))
            continue
        resp.raise_for_status()
        return resp

# --------------- quick token verifier ---------------
col1, col2 = st.columns([1,1])
with col1:
    if api_token:
        st.caption(f"Token preview: {mask_token(api_token)}")
with col2:
    if st.button("🔑 Verify token"):
        if not api_token:
            st.error("Enter your Merchant API token first.")
        else:
            try:
                r = api_get("/shops.json")
                shops = r.json()
                if not shops:
                    st.warning("Token is valid, but no shops found on this account.")
                else:
                    st.success(f"Token OK. Found {len(shops)} shop(s). Using: {shops[0].get('title', shops[0]['id'])}")
            except requests.HTTPError as e:
                code = e.response.status_code if e.response is not None else "?"
                body = e.response.text if e.response is not None else str(e)
                st.error(f"HTTP {code} verifying token: {body}")

# Stop early if no token
if not api_token:
    st.info("Paste your **Merchant API** token to continue.")
    st.stop()

# --------------- fetch shop (fails fast if 401) ---------------
try:
    shops_resp = api_get("/shops.json")
    shops = shops_resp.json()
    if not shops:
        st.error("Token is valid, but no shops are linked to this account.")
        st.stop()
    shop_id = shops[0]["id"]
    st.caption(f"Connected to shop: {shops[0].get('title', shop_id)}")
except requests.HTTPError as e:
    # Give a targeted explanation for 401
    if e.response is not None and e.response.status_code == 401:
        st.error(
            "Unauthenticated (401). Double-check the **Merchant API** token. "
            "Common causes:\n"
            "• Using an OAuth/app/publishable token (must be a *Merchant* token)\n"
            "• Token pasted with quotes or with 'Bearer ' (the app strips it, but re-check)\n"
            "• Token belongs to a different Printify account than the shop\n"
            "• Token revoked/expired — generate a new one\n\n"
            "Sanity check (terminal):\n"
            "curl -sS -H \"Authorization: Bearer YOUR_TOKEN\" https://api.printify.com/v1/shops.json"
        )
    else:
        st.error(f"Error fetching shops: {e.response.text if e.response is not None else str(e)}")
    st.stop()
