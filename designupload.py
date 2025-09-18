import os
import time
import base64
import requests
import streamlit as st

# -------------------- CONFIG --------------------
BLUEPRINT_ID = 145                 # Gildan 64000 (confirm in your account)
PROVIDER_ID = 789                  # Monster Digital (confirm in your shop)
WANTED_SIZES = ["S", "M", "L", "XL", "2XL", "3XL"]
WANTED_COLORS = ["White", "Black", "Red"]  # Must match Printify's color titles exactly
VARIANT_PRICE_CENTS = 2999         # $29.99
TITLE_SUFFIX = " - Gildan 64000"

CENTER_X = 0.5                     # Centered placement
CENTER_Y = 0.5
SCALE = 0.9                        # 0..1 relative to print area
ANGLE = 0

API_BASE = "https://api.printify.com/v1"

# -------------------- UI --------------------
st.title("📦 Printify Auto Uploader — Gildan 64000 (Monster Digital)")
api_token = st.text_input("Printify API Token", type="password")
uploaded_files = st.file_uploader("Upload design files (PNG/JPG)", type=["png", "jpg", "jpeg"], accept_multiple_files=True)

if not api_token or not uploaded_files:
    st.info("Enter your API token and upload at least one design to enable uploading.")
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
    return resp  # last response

def api_post(path, json=None, headers=HEADERS, retries=3):
    url = f"{API_BASE}{path}"
    for i in range(retries):
        resp = requests.post(url, headers=headers, json=json)
        if resp.status_code == 429 and i < retries - 1:
            time.sleep(1.5 * (i + 1))
            continue
        resp.raise_for_status()
        return resp
    return resp

def upload_image(file_obj):
    # Printify uploads expects base64 in "contents"
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

# -------------------- Fetch provider variants for this blueprint --------------------
try:
    cat = api_get(f"/catalog/blueprints/{BLUEPRINT_ID}/print_providers/{PROVIDER_ID}/variants.json").json()
    # Each item includes id, title (size), options->color->title, etc.
    # Normalize a simple structure: {variant_id, size, color, is_available}
    available_variants = []
    for v in cat:
        size = v.get("title") or v.get("size") or ""
        color = (v.get("options", {}).get("color", {}) or {}).get("title", "")
        is_available = v.get("is_available", True)
        if not (size and color and is_available):
            continue
        if size in WANTED_SIZES and color in WANTED_COLORS:
            available_variants.append({"id": v["id"], "size": size, "color": color})
    if not available_variants:
        st.warning("No matching variants found for your requested sizes/colors. Check WANTED_SIZES and WANTED_COLORS.")
except Exception as e:
    st.error(f"Failed to fetch catalog variants: {e}")
    st.stop()

# Group by color if you want per-color products; otherwise do one product with all variants:
MAKE_ONE_PRODUCT_PER_COLOR = False

# -------------------- Create products --------------------
if st.button("Upload & Publish All"):
    for file_obj in uploaded_files:
        try:
            # 1) Upload the design image once
            image_id = upload_image(file_obj)
            base_title = os.path.splitext(file_obj.name)[0]

            if MAKE_ONE_PRODUCT_PER_COLOR:
                # Split variants by color, make separate products (optional)
                color_groups = {}
                for v in available_variants:
                    color_groups.setdefault(v["color"], []).append(v)

                for color, varis in color_groups.items():
                    title = f"{base_title}{TITLE_SUFFIX} ({color})"
                    description = f"Gildan 64000 T-Shirt — {color}. Sizes: {', '.join(sorted({v['size'] for v in varis}))}."

                    product_body = {
                        "title": title,
                        "description": description,
                        "blueprint_id": BLUEPRINT_ID,
                        "print_provider_id": PROVIDER_ID,
                        "variants": [{"id": v["id"], "price": VARIANT_PRICE_CENTS} for v in varis],
                        "print_areas": [
                            {
                                "variant_ids": [v["id"] for v in varis],
                                "placeholders": [
                                    {
                                        "position": "front",
                                        "images": [{"id": image_id, "x": CENTER_X, "y": CENTER_Y, "scale": SCALE, "angle": ANGLE}]
                                    }
                                ]
                            }
                        ]
                    }

                    # Create product
                    pr = api_post(f"/shops/{shop_id}/products.json", json=product_body)
                    product_id = pr.json()["id"]

                    # Publish (booleans match Printify docs)
                    pub = api_post(f"/shops/{shop_id}/products/{product_id}/publish.json",
                                   json={"title": True, "description": True, "images": True, "variants": True})
                    st.success(f"✅ Published: {title}")

            else:
                # One product containing ALL selected variants
                title = f"{base_title}{TITLE_SUFFIX}"
                sizes_str = ", ".join(sorted({v["size"] for v in available_variants},
                                             key=lambda s: ["XS","S","M","L","XL","2XL","3XL","4XL","5XL"].index(s) if s in ["XS","S","M","L","XL","2XL","3XL","4XL","5XL"] else 999))
                colors_str = ", ".join(sorted({v["color"] for v in available_variants}))
                description = f"Gildan 64000 T-Shirt — Colors: {colors_str}. Sizes: {sizes_str}."

                product_body = {
                    "title": title,
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
                                    "images": [{"id": image_id, "x": CENTER_X, "y": CENTER_Y, "scale": SCALE, "angle": ANGLE}]
                                }
                            ]
                        }
                    ]
                }

                pr = api_post(f"/shops/{shop_id}/products.json", json=product_body)
                product_id = pr.json()["id"]

                api_post(f"/shops/{shop_id}/products/{product_id}/publish.json",
                         json={"title": True, "description": True, "images": True, "variants": True})

                st.success(f"✅ Published: {title}")

        except requests.HTTPError as http_err:
            try:
                detail = http_err.response.json()
            except Exception:
                detail = http_err.response.text if http_err.response is not None else str(http_err)
            st.error(f"❌ HTTP error for {file_obj.name}: {http_err} | Detail: {detail}")
        except Exception as e:
            st.error(f"❌ Error processing {file_obj.name}: {e}")
