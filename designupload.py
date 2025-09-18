# streamlit run printify_auto_uploader.py
import os
import re
import time
import base64
import hashlib
import requests
import streamlit as st

# -------------------- CONSTANTS --------------------
API_BASE = "https://api.printify.com/v1"
BLUEPRINT_ID = 145                  # Gildan 64000
PROVIDER_NAME = "Monster Digital"   # Resolved dynamically per blueprint
VARIANT_PRICE_CENTS = 2999          # $29.99
WANTED_SIZES = ["S", "M", "L", "XL", "2XL", "3XL"]
TITLE_SUFFIX = " - Gildan 64000"

# Default artwork placement (relative to print area)
CENTER_X, CENTER_Y, SCALE, ANGLE = 0.5, 0.5, 0.9, 0

# -------------------- UI BOOTSTRAP --------------------
st.set_page_config(page_title="Printify Auto Uploader — Gildan 64000", page_icon="📦", layout="centered")
st.title("📦 Printify Auto Uploader — Gildan 64000 (Monster Digital)")

# -------------------- ROBUST TOKEN CLEANING --------------------
ZERO_WIDTH = "".join(["\u200B", "\u200C", "\u200D", "\uFEFF"])  # zwsp, zwnj, zwj, bom

def clean_token(raw: str) -> str:
    if not raw:
        return ""
    t = raw.strip()
    if t.lower().startswith("bearer "):
        t = t[7:]
    t = t.strip().strip('"').strip("'")        # strip quotes
    t = re.sub(r"\s+", "", t)                  # remove all whitespace/newlines
    for z in ZERO_WIDTH:
        t = t.replace(z, "")                   # remove zero-width chars
    return t

def mask_token(t: str) -> str:
    if not t:
        return ""
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

# -------------------- HTTP HELPERS --------------------
def api_get(path, params=None, retries=2, backoff=1.25, timeout=30):
    url = f"{API_BASE}{path}"
    for i in range(retries):
        r = requests.get(url, headers=HEADERS, params=params, timeout=timeout)
        if r.status_code == 429 and i < retries - 1:
            time.sleep(backoff * (i + 1))
            continue
        r.raise_for_status()
        return r

def api_post(path, json=None, retries=2, backoff=1.25, timeout=30):
    url = f"{API_BASE}{path}"
    for i in range(retries):
        r = requests.post(url, headers=HEADERS, json=json, timeout=timeout)
        if r.status_code == 429 and i < retries - 1:
            time.sleep(backoff * (i + 1))
            continue
        r.raise_for_status()
        return r

# -------------------- QUICK TOKEN VERIFY --------------------
col1, col2 = st.columns(2)
with col1:
    if st.button("🔑 Verify token"):
        if not api_token:
            st.error("Enter your Merchant API token first.")
        else:
            try:
                r = api_get("/shops.json")
                shops = r.json()
                if not shops:
                    st.warning("Token accepted, but no shops found on this account.")
                else:
                    st.success(f"✅ Token OK. Found {len(shops)} shop(s). Using: {shops[0].get('title', shops[0]['id'])}")
            except requests.HTTPError as e:
                code = e.response.status_code if e.response is not None else "?"
                body = e.response.text if e.response is not None else str(e)
                st.error(f"HTTP {code} verifying token: {body}")
with col2:
    st.write("")  # spacer

if not api_token:
    st.info("Paste your **Merchant API** token to continue.")
    st.stop()

# -------------------- SHOP ACCESS (FAILS FAST IF 401) --------------------
try:
    shops = api_get("/shops.json").json()
    if not shops:
        st.error("Token is valid, but no shops are linked to this account.")
        st.stop()
    shop_id = shops[0]["id"]
    shop_title = shops[0].get("title", shop_id)
    st.caption(f"Connected to shop: {shop_title} ({shop_id})")
except requests.HTTPError as e:
    if e.response is not None and e.response.status_code == 401:
        st.error(
            "❌ Unauthenticated (401). Printify rejected the token you sent.\n\n"
            "Try this checklist:\n"
            "• Generate a **Merchant API token** in Printify → Settings → API tokens (not OAuth/app/publishable)\n"
            "• Copy the token exactly (no quotes). Don’t include `Bearer `\n"
            "• Make sure you're logged into the **same Printify account** that owns the shop\n"
            "• If unsure, **revoke & create a fresh token** and paste it again\n\n"
            "Sanity check (terminal):\n"
            "curl -sS -H \"Authorization: Bearer YOUR_TOKEN\" https://api.printify.com/v1/shops.json\n"
            "You should get a JSON array (shops). If it still says Unauthenticated, the token is invalid or wrong type."
        )
    else:
        st.error(f"Error fetching shops: {e.response.text if e.response is not None else str(e)}")
    st.stop()

# -------------------- PROVIDER RESOLUTION --------------------
def get_provider_id_for_blueprint(blueprint_id: int, provider_name: str) -> int:
    providers = api_get(f"/catalog/blueprints/{blueprint_id}/print_providers.json").json()
    for p in providers:
        if p.get("title", "").lower() == provider_name.lower():
            return p["id"]
    raise RuntimeError(
        f"Provider '{provider_name}' not found for blueprint {blueprint_id}. "
        f"Available: {', '.join([p.get('title','?') for p in providers])}"
    )

try:
    provider_id = get_provider_id_for_blueprint(BLUEPRINT_ID, PROVIDER_NAME)
    st.caption(f"Using print provider: {PROVIDER_NAME} (ID {provider_id})")
except Exception as e:
    st.error(str(e))
    st.stop()

# -------------------- CATALOG & COLOR PICKER --------------------
def fetch_catalog_variants(blueprint_id: int, provider_id: int, include_oos=False):
    params = {"show-out-of-stock": 1} if include_oos else None
    raw = api_get(f"/catalog/blueprints/{blueprint_id}/print_providers/{provider_id}/variants.json", params=params).json()
    norm = []
    for v in raw:
        size = v.get("title") or v.get("size") or ""
        color = (v.get("options", {}).get("color", {}) or {}).get("title", "")
        if not size or not color:
            continue
        norm.append({
            "id": v["id"],
            "size": size,
            "color": color,
            "is_available": v.get("is_available", True),
        })
    return norm

include_oos = st.checkbox("Show out-of-stock colors", value=False,
                          help="For planning; OOS variants are skipped during creation if unavailable.")
try:
    catalog = fetch_catalog_variants(BLUEPRINT_ID, provider_id, include_oos=include_oos)
    available_colors = sorted({v["color"] for v in catalog if v["size"] in WANTED_SIZES and (include_oos or v["is_available"])})
    if not available_colors:
        st.warning("No colors available for the selected sizes.")
except Exception as e:
    st.error(f"Failed to load catalog: {e}")
    st.stop()

st.subheader("Colors (applies to ALL uploaded designs)")
selected_colors = st.multiselect("Choose colors to include:", options=available_colors, default=available_colors)
if not selected_colors:
    st.info("Select at least one color to continue.")
    st.stop()

# Final variant pool (only available ones)
chosen_variants = [
    {"id": v["id"], "size": v["size"], "color": v["color"]}
    for v in catalog
    if v["size"] in WANTED_SIZES and v["color"] in selected_colors and v["is_available"]
]

if not chosen_variants:
    st.warning("No available variants match your color selection (and size filter).")
    st.stop()

# -------------------- UTILITIES --------------------
def upload_image(file_obj) -> str:
    file_bytes = file_obj.read()
    encoded = base64.b64encode(file_bytes).decode("utf-8")
    payload = {"file_name": file_obj.name, "contents": encoded}
    r = api_post("/uploads/images.json", json=payload)
    return r.json()["id"]

def human_size_sort_key(s: str) -> int:
    order = ["XS", "S", "M", "L", "XL", "2XL", "3XL", "4XL", "5XL"]
    return order.index(s) if s in order else 999

# -------------------- FILE UPLOADS --------------------
uploaded_files = st.file_uploader("Upload design files (PNG/JPG)", type=["png", "jpg", "jpeg"], accept_multiple_files=True)

# -------------------- CREATE & PUBLISH --------------------
if uploaded_files and st.button("🚀 Upload & Publish All"):
    for file_obj in uploaded_files:
        try:
            # 1) Upload art
            image_id = upload_image(file_obj)
            base_title = os.path.splitext(file_obj.name)[0]

            # 2) Build product body
            sizes_str = ", ".join(sorted({v["size"] for v in chosen_variants}, key=human_size_sort_key))
            colors_str = ", ".join(sorted({v["color"] for v in chosen_variants}))
            product_body = {
                "title": f"{base_title}{TITLE_SUFFIX}",
                "description": f"Gildan 64000 T-Shirt — Colors: {colors_str}. Sizes: {sizes_str}.",
                "blueprint_id": BLUEPRINT_ID,
                "print_provider_id": provider_id,
                "variants": [{"id": v["id"], "price": VARIANT_PRICE_CENTS} for v in chosen_variants],
                "print_areas": [
                    {
                        "variant_ids": [v["id"] for v in chosen_variants],
                        "placeholders": [
                            {
                                "position": "front",
                                "images": [
                                    {"id": image_id, "x": CENTER_X, "y": CENTER_Y, "scale": SCALE, "angle": ANGLE}
                                ],
                            }
                        ],
                    }
                ],
            }

            # 3) Create product
            pr = api_post(f"/shops/{shop_id}/products.json", json=product_body)
            product_id = pr.json()["id"]

            # 4) Publish
            api_post(
                f"/shops/{shop_id}/products/{product_id}/publish.json",
                json={"title": True, "description": True, "images": True, "variants": True},
            )

            st.success(f"✅ Published: {base_title}  •  {len(chosen_variants)} variants")

        except requests.HTTPError as http_err:
            try:
                detail = http_err.response.json()
            except Exception:
                detail = http_err.response.text if http_err.response is not None else str(http_err)
            st.error(f"❌ HTTP error for {file_obj.name}: {http_err} | Detail: {detail}")
        except Exception as e:
            st.error(f"❌ Error processing {file_obj.name}: {e}")

elif not uploaded_files:
    st.info("Upload at least one PNG/JPG to enable publishing.")
