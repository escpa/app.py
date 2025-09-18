import os
import base64
import requests
import streamlit as st

# --- Hardcoded product settings ---
BLUEPRINT_ID = 145  # Gildan 64000
PROVIDER_ID = 0     # Printify Choice
VARIANT_IDS = [401, 402, 403, 404, 405, 406]  # S, M, L, XL, 2XL, 3XL
VARIANT_PRICE = 2999  # cents = $29.99

def main():
    st.title("📦 Gildan 64000 Printify Uploader (S–3XL, $29.99)")

    # --- User Inputs ---
    api_token = st.text_input("Printify API Token", type="password")
    uploaded_files = st.file_uploader(
        "Upload design files (PNG/JPG, max 25MB)", 
        type=["png", "jpg", "jpeg"], 
        accept_multiple_files=True
    )

    color_input = st.text_input(
        "Enter desired colors (for reference in description, e.g., Red, Black, White)",
        value="White"
    )
    selected_colors = [c.strip() for c in color_input.split(",") if c.strip()]

    if st.button("Upload & Publish"):
        if not api_token or not uploaded_files:
            st.error("Please enter your API token and upload at least one design.")
            st.stop()

        try:
            # --- Get shop ID ---
            headers = {"Authorization": f"Bearer {api_token}"}
            resp = requests.get("https://api.printify.com/v1/shops.json", headers=headers)
            resp.raise_for_status()
            shops = resp.json()
            if not shops:
                st.error("No shops found for this API token.")
                st.stop()
            shop_id = shops[0]["id"]

            # --- Check blueprint availability ---
            resp_bp = requests.get(f"https://api.printify.com/v1/catalog/blueprints/{BLUEPRINT_ID}.json", headers=headers)
            if resp_bp.status_code != 200:
                st.error(f"Blueprint {BLUEPRINT_ID} not available in your account. Please add it manually first.")
                st.stop()

            # --- Process each uploaded design ---
            for file_obj in uploaded_files:
                st.info(f"Uploading {file_obj.name}...")

                # Safe image upload
                file_bytes = file_obj.read()
                file_obj.seek(0)
                encoded = base64.b64encode(file_bytes).decode("utf-8")
                upload_payload = {"file_name": file_obj.name, "contents": encoded}
                upload_resp = requests.post("https://api.printify.com/v1/uploads/images.json", headers=headers, json=upload_payload)
                upload_resp.raise_for_status()
                image_id = upload_resp.json()["id"]

                # --- Create product ---
                product_title = os.path.splitext(file_obj.name)[0]
                product_description = f"High-quality Gildan 64000 tee. Selected colors: {', '.join(selected_colors)}"

                print_areas = [
                    {
                        "variant_ids": VARIANT_IDS,
                        "placeholders": [
                            {
                                "position": "front",
                                "images": [{"id": image_id, "x": 0.5, "y": 0.0, "scale": 0.9, "angle": 0}]
                            }
                        ]
                    }
                ]
                variants = [{"id": vid, "price": VARIANT_PRICE} for vid in VARIANT_IDS]

                product_body = {
                    "title": f"{product_title} - Gildan 64000",
                    "description": product_description,
                    "blueprint_id": BLUEPRINT_ID,
                    "print_provider_id": PROVIDER_ID,
                    "variants": variants,
                    "print_areas": print_areas
                }

                st.info(f"Creating product: {product_title}...")
                product_resp = requests.post(f"https://api.printify.com/v1/shops/{shop_id}/products.json", headers=headers, json=product_body)
                product_resp.raise_for_status()
                product_id = product_resp.json()["id"]

                # --- Publish product ---
                st.info(f"Publishing product: {product_title}...")
                publish_resp = requests.post(f"https://api.printify.com/v1/shops/{shop_id}/products/{product_id}/publish.json", headers=headers, json={"title": True, "description": True, "images": True, "variants": True})
                publish_resp.raise_for_status()

                st.success(f"✅ {product_title} published! Product ID: {product_id}")

        except requests.exceptions.HTTPError as e:
            st.error(f"❌ HTTP error: {e.response.text}")
        except Exception as e:
            st.error(f"❌ Unexpected error: {e}")

if __name__ == "__main__":
    main()
