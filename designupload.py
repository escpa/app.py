import os
import base64
import requests
import streamlit as st

def main():
    st.title("📦 Gildan 64000 Printify Uploader")

    # --- User Inputs ---
    api_token = st.text_input("Printify API Token", type="password")
    uploaded_files = st.file_uploader(
        "Upload design files (PNG/JPG)", 
        type=["png", "jpg", "jpeg"], 
        accept_multiple_files=True
    )
    markup = st.number_input("Markup in cents (e.g. 1000 = $10)", min_value=0, value=1000)

    BLUEPRINT_ID = 57  # Gildan 64000

    # --- Helper Functions ---
    def get_shop_id():
        headers = {"Authorization": f"Bearer {api_token}"}
        resp = requests.get("https://api.printify.com/v1/shops.json", headers=headers)
        resp.raise_for_status()
        shops = resp.json()
        if not shops:
            st.error("No shops found for this API token.")
            return None
        return shops[0]["id"]

    def get_valid_provider(shop_id):
        """
        Fetches all providers for the blueprint and returns the first one with enabled variants.
        """
        headers = {"Authorization": f"Bearer {api_token}"}
        resp = requests.get(
            f"https://api.printify.com/v1/catalog/blueprints/{BLUEPRINT_ID}/print_providers.json",
            headers=headers
        )
        resp.raise_for_status()
        providers = resp.json()
        for p in providers:
            # Check if this provider has variants enabled
            provider_resp = requests.get(
                f"https://api.printify.com/v1/catalog/blueprints/{BLUEPRINT_ID}/print_providers/{p['id']}.json",
                headers=headers
            ).json()
            enabled_variants = [v for v in provider_resp["variants"] if v["enabled"]]
            if enabled_variants:
                return p["id"], enabled_variants
        st.error("No valid print providers found for Gildan 64000.")
        return None, None

    def upload_image(file_obj):
        """Upload an image to Printify using base64 encoding."""
        url = "https://api.printify.com/v1/uploads/images.json"
        file_bytes = file_obj.read()
        encoded = base64.b64encode(file_bytes).decode("utf-8")
        payload = {"file_name": file_obj.name, "contents": encoded}
        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }
        resp = requests.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        return resp.json()["id"]

    def build_print_area(image_id, variants):
        return [
            {
                "variant_ids": [v["id"] for v in variants],
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

    def create_product(shop_id, provider_id, title, description, image_id, variants):
        print_areas = build_print_area(image_id, variants)
        url = f"https://api.printify.com/v1/shops/{shop_id}/products.json"
        body = {
            "title": title,
            "description": description,
            "blueprint_id": BLUEPRINT_ID,
            "print_provider_id": provider_id,
            "variants": [{"id": v["id"], "price": v["cost"] + markup} for v in variants],
            "print_areas": print_areas
        }
        headers = {"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"}
        resp = requests.post(url, headers=headers, json=body)
        resp.raise_for_status()
        return resp.json()

    def publish_product(shop_id, product_id):
        url = f"https://api.printify.com/v1/shops/{shop_id}/products/{product_id}/publish.json"
        body = {
            "title": True,
            "description": True,
            "images": True,
            "variants": True,
            "tags": True,
            "keyFeatures": True,
            "shipping_template": True
        }
        headers = {"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"}
        resp = requests.post(url, headers=headers, json=body)
        resp.raise_for_status()
        return resp.json()

    # --- Main Upload & Publish ---
    if st.button("Upload & Publish"):
        if not api_token or not uploaded_files:
            st.error("Please enter API token and upload at least one design.")
        else:
            try:
                shop_id = get_shop_id()
                if not shop_id:
                    st.stop()
                provider_id, variants = get_valid_provider(shop_id)
                if not provider_id or not variants:
                    st.stop()
            except requests.exceptions.HTTPError as e:
                st.error(f"❌ Error fetching Shop ID or provider: {e.response.text}")
                st.stop()

            for file_obj in uploaded_files:
                try:
                    st.info(f"Uploading {file_obj.name}...")
                    image_id = upload_image(file_obj)

                    product_title = os.path.splitext(file_obj.name)[0]
                    st.info(f"Creating product: {product_title}...")
                    product = create_product(
                        shop_id,
                        provider_id,
                        f"{product_title} - Gildan 64000",
                        "High-quality Gildan 64000 tee with centered design.",
                        image_id,
                        variants
                    )
                    product_id = product["id"]

                    st.info(f"Publishing product: {product_title}...")
                    publish_product(shop_id, product_id)

                    st.success(f"✅ {product_title} published! Product ID: {product_id}")

                except requests.exceptions.HTTPError as e:
                    st.error(f"❌ HTTP error for {file_obj.name}: {e.response.text}")
                except Exception as e:
                    st.error(f"❌ Error processing {file_obj.name}: {e}")

if __name__ == "__main__":
    main()
