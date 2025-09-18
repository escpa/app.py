# streamlit run printify_auto_uploader.py
import os
import time
import base64
import requests
import streamlit as st

# -------------------- CONSTANTS --------------------
API_BASE = "https://api.printify.com/v1"
BLUEPRINT_ID = 145                  # Gildan 64000
PROVIDER_NAME = "Monster Digital"   # Resolved dynamically
VARIANT_PRICE_CENTS = 2999          # $29.99
WANTED_SIZES = ["S", "M", "L", "XL", "2XL", "3XL"]
TITLE_SUFFIX = " - Gildan 64000"

# Default artwork placement (relative to print area)
CENTER_X, CENTER_Y, SCALE, ANGLE = 0.5, 0.5, 0.9, 0

# -------------------- UI --------------------
st.set_page_config(page_title="Printify Auto Uploader — Gildan 64000", page_icon="📦", layout="centered")
st.title("📦 Printify Auto Uploader — Gildan 64000 (Monster Digital)")

raw_token = st.text_input("Printify API Token", type="password", help="Merchant API token from Printify > Settings > API tokens")
api_token = (raw_token or "").strip()

uploaded_files = st.file_uploader("Upload design files (PNG/JPG)", type=["png", "jpg", "jpeg"], accept_multiple_files=True)

# Global headers
HEADERS = {
    "Authorization": f"Bearer {api_token}" if api_token else "",
    "Content-Type": "application/json",
}

# -------------------- HTTP helpers --------------------
def api_get(path, params=None, retries=3, backoff=1.25):
    url = f"{API_BASE}{path}"
    for i in range(retries):
        resp = requests.get(url, headers=HEADERS, params=params)
        if resp.status_code == 429 and i < retries - 1:
            time.sleep(backoff * (i + 1))
            continue
        resp.raise_for_status()
        return resp

def api_post(path, json=None, retries=3, backoff=1.25):
    url = f"{API_BASE}{path}"
    for i in range(retries):
        resp = requests.post(url, headers=HEADERS, json=json)
        if resp.status_code == 429 and i < retries - 1:
            time.sleep(backoff * (i + 1))
            continue
        resp.raise_for_status()
        return resp

# -------------------- Business helpers --------------------
def verify_token_and_get_shop():
    """Return first shop (id, title). Raises HTTPError if unauthorized."""
    shops = api_get("/shops.json").json()
    if not shops:
        raise RuntimeError("Token is valid, but no shops found on this account.")
    return shops[0]["id"], shops[0].get("title", str(shops[0]["id"]))

def get_provider_id_for_blueprint(blueprint_id: int, provider_name: str) -> int:
    """Resolve print_provider_id for a given blueprint by human title."""
    providers = api_get(f"/catalog/blueprints/{blueprint_id}/print_providers.json").json()
    for p in providers:
        if p.get("title", "").lower() == provider_name.lower():
            return p["id"]
    raise RuntimeError(
        f"Provider '{provider_name}' not found for blueprint {blueprint_id}. "
        f"Available: {', '.join([p.get('title','?') for p in providers])}"
    )

def fetch_catalog_variants(blueprint_id: int, provider_id: int, include_oos=False):
    """Return normalized list of variants with id/size/color/is_available."""
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

def upload_image(file_obj) -> str:
    """Upload art to Printify and return image_id."""
    file_bytes = file_obj.read()
    encoded = base64.b64encode(file_bytes).decode("utf-8")
    payload = {"file_name": file_obj.name, "contents": encoded}
    r = api_post("/uploads/images.json", json=payload)
    return r.json()["id"]

def human_size_sort_key(s: str) -> int:
    order = ["XS","S","M","L","XL","2XL","3XL","4XL","5XL"]
    return order.index(s) if s in order else 999

# -------------------- Token verification --------------------
if st.button("🔑 Verify token"):
    if not api_token:
        st.error("Enter your API token first.")
    else:
        try:
            shop_id, shop_title = verify_token_and_get_shop()
            st.success(f"Token OK. Using shop: {shop_title} ({shop_id})")
        except requests.HTTPError as e:
            code = e.response.status_code if e.response is not None else "?"
            detail = e.response.text if e.response is not None else str(e)
            st.error(f"HTTP {code} verifying token: {detail}")
        except Exception as e:
            st.error(str(e))

# Stop early if no token yet
if not api_token:
    st.stop()

# -------------------- Resolve shop & provider --------------------
try:
    shop_id, shop_title = verify_token_and_get_shop()
    st.caption(f"Connected to shop: {shop_title} ({shop_id})")
except Exception as e:
    st.error(f"Cannot access shops with this token. {e}")
    st.stop()

try:
    provider_id = get_provider_id_for_blueprint(BLUEPRINT_ID, PROVIDER_NAME)
    st.caption(f"Using print provider: {PROVIDER_NAME} (ID {provider_id})")
except Exception as e:
    st.error(str(e))
    st.stop()

# -------------------- Fetch variants & build color selector --------------------
include_oos = st.checkbox("Show out-of-stock colors", value=False, help="For planning; OOS variants will be skipped if not available.")
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

# Final variant pool for product creation
chosen_variants = [
    {"id": v["id"], "size": v["size"], "color": v["color"]}
    for v in catalog
    if v["size"] in WANTED_SIZES and v["color"] in selected_colors and v["is_available"]
]

if not chosen_variants:
    st.warning("No available variants match your color selection (and size filter).")
    st.stop()

# -------------------- Create & publish --------------------
if uploaded_files and st.button("🚀 Upload & Publish All"):
    for file_obj in uploaded_files:
        try:
            # 1) Upload art
            image_id = upload_image(file_obj)
            base_title = os.path.splitext(file_obj.name)[0]

            # 2) Build product
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
