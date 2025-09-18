import os
import base64
import requests
import streamlit as st

# Hardcoded product settings
BLUEPRINT_ID = 145  # Gildan 64000
PROVIDER_ID = 0     # Printify Choice
VARIANT_PRICE = 2999  # $29.99 in cents

# Map variant IDs to friendly size names (for user selection)
SIZE_MAP = {
    401: "S",
    402: "M",
    403: "L",
    404: "XL",
    405: "2XL",
    406: "3XL"
}

def main():
    st.title("📦 Gildan 64000 Printify Uploader")

    api_token = st.text_input("Printify API Token", type="password")
    uploaded_files = st.file_uploader(
        "Upload design files (PNG/JPG)", type=["png", "jpg", "jpeg"], accept_multiple_files=True
    )

    color_input = st.text_input(
        "Enter desired colors (for description)", value="White"
    )
    selected_colors_text = [c.strip() for c in color_input.split(",") if c.strip()]

    if st.button("Upload & Publish"):
        if not api_token or not uploaded_files:
            st.error("Please enter API token and upload at least one design.")
            st.stop()

        headers = {"Authorization": f"Bearer {api_token}"}

        # --- Get Shop ID ---
        resp = requests.get("https://api.printify.com/v1/shops.json", headers=headers)
        resp.raise_for_status()
        shops = resp.json()
        if not shops:
            st.error("No shops found for this API token.")
            st.stop()
        shop_id = shops[0]["id"]

        # --- Fetch enabled variants for blueprint + provider ---
        variants_resp = requests.get(
            f"https://api.printify.com/v1/catalog/blueprints/{BLUEPRINT_ID}/print_providers/{PROVIDER_ID}.json",
            headers=headers
        )
        if variants_resp.status_code != 200:
            st.error(f"Failed to fetch provider variants: {variants_resp.text}")
            st.stop()
        variants_data = variants_resp.json().get("variants", [])
        enabled_variants = [v for v in variants_data if v.get("enabled")]

        if not enabled_variants:
            st.error("No enabled variants found for this blueprint with Printify Choice.")
            st.stop()

        # Let user select which sizes
        enabled_variant_ids = [v["id"] for v in enabled_variants if v["id"] in SIZE_MAP]
        selected_sizes = st.multiselect(
            "Select sizes to include",
            options=[SIZE_MAP[vid] for vid in enabled_variant_ids],
            default=[SIZE_MAP[vid] for vid in enabled_variant_ids]
        )
        final_variant_ids = [vid for vid in enabled_variant_ids if SIZE_MAP[vid] in selected_sizes]
        if not final_variant_ids:
            st.error("No sizes selected.")
            st.stop()

        # --- Upload & Create Products ---
        for file_obj in uploaded_files:
            st.info(f"Uploading {file_obj.name}...")

            # Safe image upload
            file_bytes = file_obj.read()
            file_obj.seek(0)
            encoded = base64.b64encode(file_bytes).decode("utf-8")
            upload_payload = {"file_name": file_obj.name, "contents": encoded}
            upload_resp = requests.post(
                "https://api.printify.com/v1/uploads/images.json",
                headers=headers,
                json=upload_payload
            )
            upload_resp.raise_for_status()
            image_id = upload_resp.json()["id"]

            # Create product
            product_title = os.path.splitext(file_obj.name)[0]
            product_description = f"High-quality Gildan 64000 tee. Selected colors: {', '.join(selected_colors_text)}"

            print_areas = [
                {
                    "variant_ids": final_variant_ids,
                    "placeholders": [
                        {"position": "front", "images": [{"id": image_id, "x": 0.5, "y": 0.0, "scale": 0.9, "angle": 0}]}
                    ]
                }
            ]
            variants = [{"id": vid, "price": VARIANT_PRICE} for vid in final_variant_ids]

            product_body = {
                "title": f"{product_title} - Gildan 64000",
                "description": product_description,
                "blueprint_id": BLUEPRINT_ID,
                "print_provider_id": PROVIDER_ID,
                "variants": variants,
                "print_areas": print_areas
            }

            st.info(f"Creating product: {product_title}...")
            product_resp = requests.post(
                f"https://api.printify.com/v1/shops/{shop_id}/products.json",
                headers=headers,
                json=product_body
            )
            product_resp.raise_for_status()
            product_id = product_resp.json()["id"]

            # Publish
            st.info(f"Publishing product: {product_title}...")
            publish_resp = requests.post(
                f"https://api.printify.com/v1/shops/{shop_id}/products/{product_id}/publish.json",
                headers=headers,
                json={"title": True, "description": True, "images": True, "variants": True}
            )
            publish_resp.raise_for_status()

            st.success(f"✅ {product_title} published! Product ID: {product_id}")

if __name__ == "__main__":
    main()
