import os
import base64
import requests
import streamlit as st

def main():
    st.title("📦 Gildan 64000 Printify Uploader (Printify Choice)")

    # --- User Inputs ---
    api_token = st.text_input("Printify API Token", type="password")
    uploaded_files = st.file_uploader(
        "Upload design files (PNG/JPG)", 
        type=["png", "jpg", "jpeg"], 
        accept_multiple_files=True
    )
    markup = st.number_input("Markup in cents (e.g. 1000 = $10)", min_value=0, value=1000)

    # --- Hardcoded Gildan 64000 Blueprint ---
    BLUEPRINT_ID = 145  # Gildan 64000
    PROVIDER_ID = 0     # Printify Choice

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

    def upload_image(file_obj):
        """Upload an image to Printify using base64."""
        url = "https://api.printify.com/v1/uploads/images.json"
        file_bytes = file_obj.read()
        encoded = base64.b64encode(file_bytes).decode("utf-8")
        payload = {"file_name": file_obj.name, "contents": encoded}
        headers = {"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"}
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

    def create_product(shop_id, blueprint_id, provider_id, title, description, image_id, variants):
        print_areas = build_print_area(image_id, variants)
        url = f"https://api.printify.com/v1/shops/{shop_id}/products.json"
        body = {
            "title": title,
            "description": description,
            "blueprint_id": blueprint_id,
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
        body = {"title": True, "description": True, "images": True, "variants": True}
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
                # --- Shop ID ---
                shop_id = get_shop_id()
                if not shop_id:
                    st.stop()

                # --- Get blueprint variants ---
                headers = {"Authorization": f"Bearer {api_token}"}
                bp_resp = requests.get(f"https://api.printify.com/v1/catalog/blueprints/{BLUEPRINT_ID}.json", headers=headers)
                bp_resp.raise_for_status()
                blueprint_data = bp_resp.json()
                variants = blueprint_data.get("variants", [])
                if not variants:
                    st.error("No variants found for this blueprint.")
                    st.stop()

                # --- Color Selection ---
                variant_options = {v["title"]: v for v in variants}  # title -> variant
                selected_colors = st.multiselect(
                    "Select t-shirt colors to publish",
                    options=list(variant_options.keys()),
                    default=list(variant_options.keys())
                )
                if selected_colors:
                    variants = [variant_options[color] for color in selected_colors]
                else:
                    st.error("No colors selected. Please select at least one color.")
                    st.stop()

            except requests.exceptions.HTTPError as e:
                st.error(f"❌ Error fetching shop or blueprint: {e.response.text}")
                st.stop()

            # --- Upload & Create Products ---
            for file_obj in uploaded_files:
                try:
                    st.info(f"Uploading {file_obj.name}...")
                    image_id = upload_image(file_obj)

                    product_title = os.path.splitext(file_obj.name)[0]
                    st.info(f"Creating product: {product_title}...")
                    product = create_product(
                        shop_id,
                        BLUEPRINT_ID,
                        PROVIDER_ID,
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
