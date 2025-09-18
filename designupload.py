import os
import requests
import streamlit as st

def main():
    st.title("📦 Gildan 64000 Printify Uploader")

    # --- User Inputs ---
    api_token = st.text_input("Printify API Token", type="password")
    shop_id = st.text_input("Printify Shop ID")
    uploaded_files = st.file_uploader(
        "Upload design files (PNG/JPG)", 
        type=["png", "jpg", "jpeg"], 
        accept_multiple_files=True
    )
    markup = st.number_input("Markup in cents (e.g. 1000 = $10)", min_value=0, value=1000)

    # --- Constants for Gildan 64000 ---
    BLUEPRINT_ID = 57       # Gildan 64000 (verify with Printify Catalog)
    PRINT_PROVIDER_ID = 18  # Example provider, verify in Printify

    HEADERS = {"Authorization": f"Bearer {api_token}"}

    # --- Helper Functions ---
    def upload_image(file_obj):
        url = "https://api.printify.com/v1/uploads/images.json"
        # Explicit MIME type
        mime_type = "image/png" if file_obj.name.lower().endswith(".png") else "image/jpeg"
        files = {"file": (file_obj.name, file_obj.getvalue(), mime_type)}
        resp = requests.post(url, headers={"Authorization": f"Bearer {api_token}"}, files=files)
        resp.raise_for_status()
        return resp.json()["id"]

    def get_variants():
        url = f"https://api.printify.com/v1/catalog/blueprints/{BLUEPRINT_ID}/print_providers/{PRINT_PROVIDER_ID}.json"
        resp = requests.get(url, headers=HEADERS)
        resp.raise_for_status()
        data = resp.json()
        return [{"id": v["id"], "price": v["cost"] + markup} for v in data["variants"] if v["enabled"]]

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

    def create_product(title, description, image_id):
        variants = get_variants()
        print_areas = build_print_area(image_id, variants)
        url = f"https://api.printify.com/v1/shops/{shop_id}/products.json"
        body = {
            "title": title,
            "description": description,
            "blueprint_id": BLUEPRINT_ID,
            "print_provider_id": PRINT_PROVIDER_ID,
            "variants": variants,
            "print_areas": print_areas
        }
        resp = requests.post(url, headers={**HEADERS, "Content-Type": "application/json"}, json=body)
        resp.raise_for_status()
        return resp.json()

    def publish_product(product_id):
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
        resp = requests.post(url, headers={**HEADERS, "Content-Type": "application/json"}, json=body)
        resp.raise_for_status()
        return resp.json()

    # --- Main Upload & Publish Button ---
    if st.button("Upload & Publish"):
        if not api_token or not shop_id or not uploaded_files:
            st.error("Please enter API token, Shop ID, and upload at least one design.")
        else:
            for file_obj in uploaded_files:
                try:
                    st.info(f"Uploading {file_obj.name}...")
                    image_id = upload_image(file_obj)

                    product_title = os.path.splitext(file_obj.name)[0]
                    st.info(f"Creating product: {product_title}...")
                    product = create_product(
                        f"{product_title} - Gildan 64000",
                        "High-quality Gildan 64000 tee with centered design.",
                        image_id
                    )
                    product_id = product["id"]

                    st.info(f"Publishing product: {product_title}...")
                    publish_product(product_id)

                    st.success(f"✅ {product_title} published! Product ID: {product_id}")

                except requests.exceptions.HTTPError as e:
                    st.error(f"❌ HTTP error for {file_obj.name}: {e.response.text}")
                except Exception as e:
                    st.error(f"❌ Error processing {file_obj.name}: {e}")

if __name__ == "__main__":
    main()
