import os
import base64
import requests
import streamlit as st

BLUEPRINT_ID = 145  # Gildan 64000
VARIANT_PRICE = 2999  # $29.99 in cents

def main():
    st.title("📦 Gildan 64000 Printify Uploader")

    api_token = st.text_input("Printify API Token", type="password")
    uploaded_files = st.file_uploader(
        "Upload design files (PNG/JPG)", type=["png", "jpg", "jpeg"], accept_multiple_files=True
    )

    if not api_token or not uploaded_files:
        st.info("Enter your API token and upload at least one design to enable uploading.")
        st.stop()

    headers = {"Authorization": f"Bearer {api_token}"}

    # --- Get Shop ID ---
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

    # --- Fetch Print Providers for Blueprint ---
    try:
        providers_resp = requests.get(
            f"https://api.printify.com/v1/catalog/blueprints/{BLUEPRINT_ID}/print_providers.json",
            headers=headers
        )
        providers_resp.raise_for_status()
        providers = providers_resp.json()
        if not providers:
            st.error("No print providers available for this blueprint.")
            st.stop()
    except requests.exceptions.HTTPError as e:
        st.error(f"HTTP error fetching providers: {e.response.status_code} - {e.response.text}")
        st.stop()

    provider_options = {p["title"]: p["id"] for p in providers}
    selected_provider_title = st.selectbox("Select a print provider", options=list(provider_options.keys()))
    provider_id = provider_options[selected_provider_title]

    # --- Fetch Enabled Variants for Selected Provider ---
    try:
        variants_resp = requests.get(
            f"https://api.printify.com/v1/catalog/blueprints/{BLUEPRINT_ID}/print_providers/{provider_id}.json",
            headers=headers
        )
        variants_resp.raise_for_status()
        variants_data = variants_resp.json().get("variants", [])
        enabled_variants = [v for v in variants_data if v.get("enabled")]
        if not enabled_variants:
            st.error("No enabled variants found for this provider.")
            st.stop()
    except requests.exceptions.HTTPError as e:
        st.error(f"HTTP error fetching variants: {e.response.status_code} - {e.response.text}")
        st.stop()

    variant_options = {v["title"]: v["id"] for v in enabled_variants}
    selected_variant_titles = st.multiselect("Select sizes to include", options=list(variant_options.keys()))
    selected_variant_ids = [variant_options[t] for t in selected_variant_titles]
    if not selected_variant_ids:
        st.error("No sizes selected.")
        st.stop()

    # --- Fetch Available Colors for Each Variant ---
    color_map = {}
    for vid in selected_variant_ids:
        try:
            colors_resp = requests.get(
                f"https://api.printify.com/v1/catalog/blueprints/{BLUEPRINT_ID}/print_providers/{provider_id}/variants/{vid}/colors.json",
                headers=headers
            )
            colors_resp.raise_for_status()
            colors = colors_resp.json()
            color_map[vid] = {c["title"]: c["id"] for c in colors}
        except requests.exceptions.HTTPError as e:
            st.error(f"HTTP error fetching colors for variant {vid}: {e.response.status_code} - {e.response.text}")
            st.stop()

    # --- Let User Select Colors per Variant ---
    selected_colors_per_variant = {}
    for vid in selected_variant_ids:
        colors = list(color_map[vid].keys())
        if colors:
            chosen_colors = st.multiselect(f"Select colors for {vid}", options=colors, default=colors)
            selected_colors_per_variant[vid] = [color_map[vid][c] for c in chosen_colors]
        else:
            selected_colors_per_variant[vid] = []

    # --- Upload & Create Products ---
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

                for vid in selected_variant_ids:
                    color_ids = selected_colors_per_variant.get(vid, [])
                    for color_id in color_ids:
                        product_title = os.path.splitext(file_obj.name)[0]
                        product_description = f"Gildan 64000 T-shirt, Variant ID {vid}, Color ID {color_id}"

                        product_body = {
                            "title": f"{product_title} - Gildan 64000",
                            "description": product_description,
                            "blueprint_id": BLUEPRINT_ID,
                            "print_provider_id": provider_id,
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

                        st.info(f"Creating product for Variant {vid}, Color {color_id}...")
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
                        st.success(f"✅ Published product {product_title} - Variant {vid} - Color {color_id}")

            except requests.exceptions.HTTPError as e:
                st.error(f"HTTP error for {file_obj.name}: {e.response.status_code} - {e.response.text}")
            except Exception as e:
                st.error(f"Unexpected error for {file_obj.name}: {e}")


if __name__ == "__main__":
    main()
