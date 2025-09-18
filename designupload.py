# streamlit run printify_auto_uploader.py
import os, re, time, base64, hashlib, requests, streamlit as st

# ================== CONSTANTS ==================
API_BASE = "https://api.printify.com/v1"
VARIANT_PRICE_CENTS = 2999          # $29.99
WANTED_SIZES = ["S", "M", "L", "XL", "2XL", "3XL"]
TITLE_SUFFIX = " - Selected Garment"
CENTER_X, CENTER_Y, SCALE, ANGLE = 0.5, 0.5, 0.9, 0

# ================== UI SETUP ==================
st.set_page_config(page_title="Printify Auto Uploader — Blueprint/Provider Picker", page_icon="📦", layout="centered")
st.title("📦 Printify Auto Uploader")

# ---- Token cleaning/diagnostics ----
ZERO_WIDTH = "".join(["\u200B", "\u200C", "\u200D", "\uFEFF"])
def clean_token(raw: str) -> str:
    if not raw: return ""
    t = raw.strip()
    if t.lower().startswith("bearer "): t = t[7:]
    t = t.strip().strip('"').strip("'")
    t = re.sub(r"\s+", "", t)
    for z in ZERO_WIDTH: t = t.replace(z, "")
    return t

def mask_token(t: str) -> str:
    if not t: return ""
    return f"{t[:6]}…{t[-6:]} (len={len(t)})" if len(t) > 12 else f"{t[:2]}…{t[-2:]} (len={len(t)})"

def token_fingerprint(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()[:8] if t else ""

raw_token = st.text_input("Printify Merchant API Token", type="password",
                          help="Create in Printify → Settings → API tokens (Merchant token, not OAuth/publishable). Paste exactly.")
api_token = clean_token(raw_token)
st.caption(f"Token preview: {mask_token(api_token)}  •  sha256:{token_fingerprint(api_token)}")

HEADERS = {
    "Authorization": f"Bearer {api_token}" if api_token else "",
    "Content-Type": "application/json",
}

# ---- HTTP helpers with debug ----
def api_get(path, params=None, retries=2, backoff=1.25, timeout=30):
    url = f"{API_BASE}{path}"
    for i in range(retries):
        r = requests.get(url, headers=HEADERS, params=params, timeout=timeout)
        if r.status_code == 429 and i < retries - 1:
            time.sleep(backoff * (i + 1)); continue
        if r.status_code >= 400:
            # show exact URL that failed
            st.error(f"HTTP {r.status_code} GET {url}  •  params={params}  •  body={r.text}")
            r.raise_for_status()
        r.raise_for_status()
        return r

def api_post(path, json=None, retries=2, backoff=1.25, timeout=30):
    url = f"{API_BASE}{path}"
    for i in range(retries):
        r = requests.post(url, headers=HEADERS, json=json, timeout=timeout)
        if r.status_code == 429 and i < retries - 1:
            time.sleep(backoff * (i + 1)); continue
        if r.status_code >= 400:
            st.error(f"HTTP {r.status_code} POST {url}  •  json={json}  •  body={r.text}")
            r.raise_for_status()
        r.raise_for_status()
        return r

# ================== VERIFY TOKEN & SHOP ==================
col1, col2 = st.columns(2)
with col1:
    if st.button("🔑 Verify token"):
        if not api_token:
            st.error("Enter your Merchant API token first.")
        else:
            try:
                r = api_get("/shops.json")
                shops = r.json()
                if not shops: st.warning("Token accepted, but no shops found on this account.")
                else: st.success(f"✅ Token OK. Found {len(shops)} shop(s). Using: {shops[0].get('title', shops[0]['id'])}")
            except requests.HTTPError:
                pass
with col2:
    st.write("")

if not api_token:
    st.info("Paste your **Merchant API** token to continue.")
    st.stop()

try:
    shops = api_get("/sho_
