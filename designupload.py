import os
import base64
import requests
import streamlit as st

# -------------------- CONFIG: Hardcoded --------------------
BLUEPRINT_ID = 145              # Gildan 64000
PROVIDER_ID = 789               # Monster Digital (replace with your shop's actual provider ID)
VARIANT_IDS = [401, 402, 403, 404, 405, 406]  # Sizes S–3XL
COLOR_IDS = [1, 2, 3]           # Example: White, Black, Red
VARIANT_PRICE = 2999             # $29.99 in cents
SIZE_MAP = {401: "S", 402: "M", 403: "L", 404: "XL", 405: "2XL", 406: "3XL"}
COLOR_MAP = {1: "White", 2: "Black", 3: "Red"}

def main():
    st.title("📦 Gildan 64000 Printify Uploader (Monster Digital Only)")

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
        shops = resp.json()
        if not shops:
            st.error("No shops found for this API token.")
            st.stop()
        shop_id = shops[0]["id"]
    except requests.exceptions.HTTPError as e:
        st.error(f"HTTP error fetching shops: {e.response.status_code} - {e.response.text}")
        st.stop()

    # -------------------- SELECT SIZES & COLORS --------------------
    selected_sizes = st.multiselect(
        "Select sizes to include",
        options=[SIZE_MAP[vid] for vid in VARIANT_IDS],
        default=[SIZE_MAP[vid] for vid in VARIANT_IDS]
    )
    selected_variant_ids = [vid for vid in VARIANT_IDS if SIZE_MAP[vid] in selected_sizes]

    selected_colors = st.multiselect(
        "Select colors to include",
        options=[COLOR_MAP[cid] for cid in COLOR_IDS],
        default=[COLOR_MAP[cid] for cid in COLOR_IDS]
    )
    selected_color_ids = [cid for cid in COLOR_IDS if COLOR_MAP[cid] in selected_colors]

    if not selected_variant_ids or not selected_color_ids:
        st.error("No sizes or colors selected.")
        st.stop()

    # -------------------- UPLOAD & CREATE PRODUCTS --------------------
    if st.button("Upload & Publish"):
        for file_obj in uploaded_files:
            try:
                st.info(f"Uploading {file_obj.name}...")
                file_bytes = file_obj.read()
                encoded = base64.b64encode(file_bytes).decode("utf-8")
                upload_payload = {"file_name": file_obj.name, "contents": encoded}
                upload_resp = requests.post(
                    "https://api.printify.com/v1/uploads/images.json",
                    headers=headers,
                    json=upload_payload
                )
                upload_resp.raise_for_status()
                image_id = upload_resp.json()["id"]

                # Loop through selected sizes and colors
                for vid in selected_variant_ids:
                    for color_id in selected_color_ids:
                        product_title = os.path.splitext(file_obj.name)[0]
                        product_description = f"Gildan 64000 T-shirt, Size {SIZE_MAP[vid]}, Color {COLOR_MAP[color_id]}"

                        product_body = {
                            "title": f"{product_title} - Gildan 64000",
                            "description": product_description,
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

                        st.info(f"Creating product for Size {SIZE_MAP[vid]}, Color {COLOR_MAP[color_id]}...")
                        product_resp = requests.post(
                            f"https://api.printify.com/v1/shops/{shop_id}/products.json",
                            headers=headers,
                            json=product_body
                        )
                        product_resp.raise_for_status()
                        product_id = product_resp.json()["id"]

                        st.info(f"Publishing product {product_id}...")
                        publish_resp = requests.post(
                            f"https://api.printify.com/v1/shops/{shop_id}/products/{product_id}/publish.json",
                            headers=headers,
                            json={"title": True, "description": True, "images": True, "variants": True}
                        )
                        publish_resp.raise_for_status()
                        st.success(f"✅ Published product {product_title} - Size {SIZE_MAP[vid]} - Color {COLOR_MAP[color_id]}")

            except requests.exceptions.HTTPError as e:
                st.error(f"HTTP error for {file_obj.name}: {e.response.status_code} - {e.response.text}")
            except Exception as e:
                st.error(f"Unexpected error for {file_obj.name}: {e}")


if __name__ == "__main__":
    main()
