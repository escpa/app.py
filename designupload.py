import os
import base64
import requests
import streamlit as st

def main():
    st.title("📦 Gildan 64000 Printify Uploader (S–3XL, $29.99 each)")

    # --- User Inputs ---
    api_token = st.text_input("Printify API Token", type="password")
    uploaded_files = st.file_uploader(
        "Upload design files (PNG/JPG)", 
        type=["png", "jpg", "jpeg"], 
        accept_multiple_files=True
    )

    # --- Hardcoded blueprint, provider, variants, price ---
    BLUEPRINT_ID = 145  # Gildan 64000
    PROVIDER_ID = 0     # Printify Choice
    VARIANT_IDS = [401, 402, 403, 404, 405, 406]  # S, M, L, XL, 2XL, 3XL
    VARIANT_PRICE = 2999  # cents = $29.99

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
        """Safely upload an image to Printify using base64."""
        try:
            file_bytes = file_obj.read()
            file_obj.seek(0)
            encoded = base64.b64encode(file_bytes).decode("utf-8")
            payload = {"file_name": file_obj.name, "contents": encoded}
            headers = {"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"}
            resp = requests.post("https://api.printify.com/v1/uploads/images.json", headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()["id"]
        except requests.exceptions.HTTPError as e:
            st.error(f"❌ HTTP error uploading {file_obj.name}: {e.response.text}")
            return None

    def create_product(shop_id, title, description, image_id):
        """Create product using Printify Choice with hardcoded S–3XL variants and fixed price."""
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
        body = {
            "title": title,
            "description": description,
            "blueprint_id": BLUEPRINT_ID,
            "print_provider_id": PROVIDER_ID,
            "variants": variants,
            "print_areas": print_areas
        }
        headers = {"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"}
        resp = requests.post(f"https://api.printify.com/v1/shops/{shop_id}/products.json", headers=headers, json=body)
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
            st.stop()

        try:
            shop_id = get_shop_id()
            if not shop_id:
                st.stop()

            # --- User enters colors for reference ---
            color_input = st.text_input(
                "Enter desired colors (for reference in product description, e.g. Red, Black, White)",
                value="White"
            )
            selected_colors = [c.strip() for c in color_input.split(",") if c.strip()]
            if not selected_colors:
                st.error("Please enter at least one color.")
                st.stop()

        except requests.exceptions.HTTPError as e:
            st.error(f"❌ Error fetching shop: {e.response.text}")
            st.stop()

        # --- Upload & Create Products ---
        for file_obj in uploaded_files:
            try:
                st.info(f"Uploading {file_obj.name}...")
                image_id = upload_image(file_obj)
                if not image_id:
                    st.warning(f"Skipping {file_obj.name} due to upload error.")
                    continue

                product_title = os.path.splitext(file_obj.name)[0]
                product_description = f"High-quality Gildan 64000 tee. Selected colors: {', '.join(selected_colors)}"

                st.info(f"Creating product: {product_title}...")
                product = create_product(
                    shop_id,
                    f"{product_title} - Gildan 64000",
                    product_description,
                    image_id
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
