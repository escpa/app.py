import os
import time
import base64
import requests
import streamlit as st

# -------------------- CONFIG --------------------
BLUEPRINT_ID = 145                 # Gildan 64000
PROVIDER_NAME = "Monster Digital"  # We'll resolve its ID dynamically
VARIANT_PRICE_CENTS = 2999         # $29.99
WANTED_SIZES = ["S", "M", "L", "XL", "2XL", "3XL"]  # Keep sizes fixed (can expose later if you want)
TITLE_SUFFIX = " - Gildan 64000"
API_BASE = "https://api.printify.com/v1"

CENTER_X = 0.5
CENTER_Y = 0.5
SCALE = 0.9
ANGLE = 0

# -------------------- UI --------------------
st.title("📦 Printify Auto Uploader — Gildan 64000 (Monster Digital)")

api_token = st.text_input("Printify API Token", type="password")
uploaded_files = st.file_uploader("Upload design files (PNG/JPG)", type=["png", "jpg", "jpeg"], accept_multiple_files=True)

if not api_token:
    st.info("Enter your API token to proceed.")
    st.stop()

HEADERS = {"Authorization": f"Bearer {api_token}"}

# -------------------- Helpers --------------------
def api_get(path, headers=HEADERS, params=None, retries=3):
    url = f"{API_BASE}{path}"
    for i in range(retries):
        resp = requests.get(url, headers=headers, params=params)
        if resp.status_code == 429 and i < retries - 1:
            time.sleep(1.5 * (i + 1))
            continue
        resp.raise_for_status()
        return resp

def api_post(path, json=None, headers=HEADERS, retries=3):
    url = f"{API_BASE}{path}"
    for i in range(retries):
        resp = requests.post(url, headers=headers, json=json)
        if resp.status_code == 429 and i < retries - 1:
            time.sleep(1.5 * (i + 1))
            continue
        resp.raise_for_status()
        return resp

def get_provider_id_for_blueprint(blueprint_id: int, provider_name: str) -> int:
    r = api_get(f"/catalog/blueprints/{blueprint_id}/print_providers.json")
    providers = r.json()  # [{"id": 29, "title": "Monster Digital"}, ...]
    for p in providers:
        if p["title"].lower() == provider_name.lower():
            return p["id"]
    raise ValueError(
        f"Provider '{provider_name}' not found for blueprint {blueprint_id}. "
        f"Available: {', '.join([p['title'] for p in providers])}"
    )

def upload_image(file_obj):
    file_bytes = file_obj.read()
    encoded = base64.b64encode(file_bytes).decode("utf-8")
    payload = {"file_name": file_obj.name, "contents": encoded}
    r = api_post("/uploads/images.json", json=payload)
    return r.json()["id"]

# -------------------- Get shop --------------------
try:
    shop_resp = api_get("/shops.json")
    shops = shop_resp.json()
    if not shops:
        st.error("No shops found on your account.")
        st.stop()
    shop_id = shops[0]["id"]
    st.success(f"Connected to shop: {shops[0].get('title', shop_id)}")
except Exception as e:
    st.error(f"Error fetching shop ID: {e}")
    st.stop()

# -------------------- Resolve provider ID --------------------
try:
    PROVIDER_ID = get_provider_id_for_blueprint(BLUEPRINT_ID, PROVIDER_NAME)
    st.caption(f"Using print provider: {PROVIDER_NAME} (ID {PROVIDER_ID})")
except Exception as e:
    st.error(f"Could not resolve provider ID: {e}")
    st.stop()

# -------------------- Fetch catalog variants & build color choices --------------------
try:
    # Tip: add params={"show-out-of-stock": 1} if you want to see OOS colors too
    cat = api_get(f"/catalog/blueprints/{BLUEPRINT_ID}/print_providers/{PROVIDER_ID}/variants.json").json()

    # Normalize data
    norm = []
    for v in cat:
        size = v.get("title") or v.get("size") or ""
        color = (v.get("options", {}).get("color", {}) or {}).get("title", "")
        if not size or not color:
            continue
        norm.append({
            "id": v["id"],
            "size": size,
            "color": color,
            "is_available": v.get("is_available", True)
        })

    # Available colors for the wanted sizes
    colors_available = sorted({x["color"] for x in norm if x["size"] in WANTED_SIZES and x["is_available"]})
    if not colors_available:
        st.warning("No available colors found for the selected sizes. Try relaxing size constraints.")
except Exception as e:
    st.error(f"Failed to fetch catalog variants: {e}")
    st.stop()

# -------------------- Color selection (applies to ALL uploads) --------------------
st.subheader("Select colors to include")
selected_colors = st.multiselect(
    "Colors (applies to all designs you upload below)",
    options=colors_available,
    default=colors_available  # default to all available
)

if not selected_colors:
    st.info("Select at least one color to continue.")
    st.stop()

# Build the final variant list based on color selection + wanted sizes
available_variants = [
    {"id": v["id"], "size": v["size"], "color": v["color"]}
    for v in norm
    if v["is_available"] and v["size"] in WANTED_SIZES and v["color"] in selected_colors
]

if not available_variants:
    st.warning("No matching variants with your color selection. Choose different colors or adjust sizes.")
    st.stop()

# -------------------- Upload & Create Products --------------------
if uploaded_files:
    if st.button("Upload & Publish All"):
        for file_obj in uploaded_files:
            try:
                # 1) Upload the graphic once
                image_id = upload_image(file_obj)
                base_title = os.path.splitext(file_obj.name)[0]

                # Build dynamic description from chosen colors/sizes
                sizes_str = ", ".join(sorted({v["size"] for v in available_variants},
                                             key=lambda s: ["XS","S","M","L","XL","2XL","3XL","4XL","5XL"].index(s) if s in ["XS","S","M","L","XL","2XL","3XL","4XL","5XL"] else 999))
                colors_str = ", ".join(sorted({v["color"] for v in available_variants}))
                description = f"Gildan 64000 T-Shirt — Colors: {colors_str}. Sizes: {sizes_str}."

                product_body = {
                    "title": f"{base_title}{TITLE_SUFFIX}",
                    "description": description,
                    "blueprint_id": BLUEPRINT_ID,
                    "print_provider_id": PROVIDER_ID,
                    "variants": [{"id": v["id"], "price": VARIANT_PRICE_CENTS} for v in available_variants],
                    "print_areas": [
                        {
                            "variant_ids": [v["id"] for v in available_variants],
                            "placeholders": [
                                {
                                    "position": "front",
                                    "images": [
                                        {"id": image_id, "x": CENTER_X, "y": CENTER_Y, "scale": SCALE, "angle": ANGLE}
                                    ]
                                }
                            ]
                        }
                    ]
                }

                # 2) Create product
                pr = api_post(f"/shops/{shop_id}/products.json", json=product_body)
                product_id = pr.json()["id"]

                # 3) Publish to your channel(s)
                api_post(
                    f"/shops/{shop_id}/products/{product_id}/publish.json",
                    json={"title": True, "description": True, "images": True, "variants": True}
                )

                st.success(f"✅ Published: {base_title} ({len(available_variants)} variants)")

            except requests.HTTPError as http_err:
                try:
                    detail = http_err.response.json()
                except Exception:
                    detail = http_err.response.text if http_err.response is not None else str(http_err)
                st.error(f"❌ HTTP error for {file_obj.name}: {http_err} | Detail: {detail}")
            except Exception as e:
                st.error(f"❌ Error processing {file_obj.name}: {e}")
else:
    st.info("Upload at least one design file to enable publishing.")
