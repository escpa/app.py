import os
import base64
import requests
import streamlit as st

# -------------------- CONFIG: Hardcoded --------------------
BLUEPRINT_ID = 145              # Gildan 64000
PROVIDER_ID = 789               # Monster Digital (replace with your shop's actual provider ID)
VARIANT_IDS = [401, 402, 403, 404, 405, 406]  # Sizes S–3XL
COLOR_IDS = [1, 2, 3]           # Colors: White, Black, Red (replace with actual IDs)
VARIANT_PRICE = 2999             # $29.99 in cents
SIZE_MAP = {401: "S", 402: "M", 403: "L", 404: "XL", 405: "2XL", 406: "3XL"}
COLOR_MAP = {1: "White", 2: "Black", 3: "Red"}

# -------------------- STREAMLIT APP --------------------
st.title("📦 Gildan 64000 Auto Uploader (Monster Digital Only)")

api_token = st.text_input("Printify API Token", type="password")
uploaded_files = st.file_uploader(
    "Upload design files (PNG/JPG)", type=["png", "jpg", "jpeg"], accept_multiple_files=True
)

if not api_token or not uploaded_files:
    st.info("Enter your API token and upload at least one design to enable uploading.")
    st.stop()

headers = {"Authorization": f"Bearer {api_token}"}

# -------------------- GET SHOP ID --------------------
try:
    resp = requests.get("https://api.printify.com/v1/shops.json", headers=headers)
    resp.raise_for_status()
    shop_id = resp.json()[0]["id"]
except Exception as e:
    st.error(f"Error fetching shop ID: {e}")
    st.stop()

# -------------------- UPLOAD & CREATE PRODUCTS --------------------
if st.button("Upload & Publish All"):
    for file_obj in uploaded_files:
        try:
            # Upload image
            file_bytes = file_obj.read()
            encoded = base64.b64encode(file_bytes).decode("utf-8")
            upload_resp = requests.post(
                "https://api.printify.com/v1/uploads/images.json",
                headers=headers,
                json={"file_name": file_obj.name, "contents": encoded}
            )
            upload_resp.raise_for_status()
            image_id = upload_resp.json()["id"]

            # Loop through all hardcoded sizes and colors
            for vid in VARIANT_IDS:
                for cid in COLOR_IDS:
                    product_title = os.path.splitext(file_obj.name)[0]
                    product_body = {
                        "title": f"{product_title} - Gildan 64000",
                        "description": f"Gildan 64000 T-shirt, Size {SIZE_MAP[vid]}, Color {COLOR_MAP[cid]}",
                        "blueprint_id": BLUEPRINT_ID,
                        "print_provider_id": PROVIDER_ID,
                        "variants": [{"id": vid, "price": VARIANT_PRICE}],
                        "print_areas": [
                            {
                                "variant_ids": [vid],
                                "placeholders": [
                                    {
                                        "position": "front",
                                        "images": [
                                            {"id": image_id, "x": 0.5, "y": 0.0, "scale": 0.9, "angle": 0}
                                        ]
                                    }
                                ]
                            }
                        ]
                    }

                    # Create product
                    product_resp = requests.post(
                        f"https://api.printify.com/v1/shops/{shop_id}/products.json",
                        headers=headers,
                        json=product_body
                    )
                    product_resp.raise_for_status()
                    product_id = product_resp.json()["id"]

                    # Publish product
                    publish_resp = requests.post(
                        f"https://api.printify.com/v1/shops/{shop_id}/products/{product_id}/publish.json",
                        headers=headers,
                        json={"title": True, "description": True, "images": True, "variants": True}
                    )
                    publish_resp.raise_for_status()
                    st.success(f"✅ Published {product_title} - Size {SIZE_MAP[vid]} - Color {COLOR_MAP[cid]}")

        except Exception as e:
            st.error(f"Error processing {file_obj.name}: {e}")

