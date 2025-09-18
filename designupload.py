# streamlit run printify_auto_uploader.py
import os, re, time, base64, hashlib, requests, streamlit as st

# ================== CONSTANTS ==================
API_BASE = "https://api.printify.com/v1"
VARIANT_PRICE_CENTS = 2999          # $29.99
WANTED_SIZES = ["S", "M", "L", "XL", "2XL", "3XL"]
TITLE_SUFFIX = " - Selected Garment"
CENTER_X, CENTER_Y, SCALE, ANGLE = 0.5, 0.5, 0.9, 0

# ================== UI SETUP ==================
st.set_page_config(page_title="Printify Auto Uploader — Blueprint/Provider Picker", page_icon="📦", layout="centered")
st.title("📦 Printify Auto Uploader")

# ---- Token cleaning/diagnostics ----
ZERO_WIDTH = "".join(["\u200B", "\u200C", "\u200D", "\uFEFF"])
def clean_token(raw: str) -> str:
    if not raw: return ""
    t = raw.strip()
    if t.lower().startswith("bearer "): t = t[7:]
    t = t.strip().strip('"').strip("'")
    t = re.sub(r"\s+", "", t)
    for z in ZERO_WIDTH: t = t.replace(z, "")
    return t

def mask_token(t: str) -> str:
    if not t: return ""
    return f"{t[:6]}…{t[-6:]} (len={len(t)})" if len(t) > 12 else f"{t[:2]}…{t[-2:]} (len={len(t)})"

def token_fingerprint(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()[:8] if t else ""

raw_token = st.text_input("Printify Merchant API Token", type="password",
                          help="Create in Printify → Settings → API tokens (Merchant token, not OAuth/publishable). Paste exactly.")
api_token = clean_token(raw_token)
st.caption(f"Token preview: {mask_token(api_token)}  •  sha256:{token_fingerprint(api_token)}")

HEADERS = {
    "Authorization": f"Bearer {api_token}" if api_token else "",
    "Content-Type": "application/json",
}

# ---- HTTP helpers with debug ----
def api_get(path, params=None, retries=2, backoff=1.25, timeout=30):
    url = f"{API_BASE}{path}"
    for i in range(retries):
        r = requests.get(url, headers=HEADERS, params=params, timeout=timeout)
        if r.status_code == 429 and i < retries - 1:
            time.sleep(backoff * (i + 1)); continue
        if r.status_code >= 400:
            # show exact URL that failed
            st.error(f"HTTP {r.status_code} GET {url}  •  params={params}  •  body={r.text}")
            r.raise_for_status()
        r.raise_for_status()
        return r

def api_post(path, json=None, retries=2, backoff=1.25, timeout=30):
    url = f"{API_BASE}{path}"
    for i in range(retries):
        r = requests.post(url, headers=HEADERS, json=json, timeout=timeout)
        if r.status_code == 429 and i < retries - 1:
            time.sleep(backoff * (i + 1)); continue
        if r.status_code >= 400:
            st.error(f"HTTP {r.status_code} POST {url}  •  json={json}  •  body={r.text}")
            r.raise_for_status()
        r.raise_for_status()
        return r

# ================== VERIFY TOKEN & SHOP ==================
col1, col2 = st.columns(2)
with col1:
    if st.button("🔑 Verify token"):
        if not api_token:
            st.error("Enter your Merchant API token first.")
        else:
            try:
                r = api_get("/shops.json")
                shops = r.json()
                if not shops: st.warning("Token accepted, but no shops found on this account.")
                else: st.success(f"✅ Token OK. Found {len(shops)} shop(s). Using: {shops[0].get('title', shops[0]['id'])}")
            except requests.HTTPError:
                pass
with col2:
    st.write("")

if not api_token:
    st.info("Paste your **Merchant API** token to continue.")
    st.stop()

try:
    shops = api_get("/shops.json").json()
    if not shops:
        st.error("Token valid, but no shops linked to this account.")
        st.stop()
    shop_id = shops[0]["id"]
    shop_title = shops[0].get("title", shop_id)
    st.caption(f"Connected to shop: {shop_title} ({shop_id})")
except requests.HTTPError:
    st.stop()

# ================== PICK BLUEPRINT (dynamic) ==================
st.subheader("1) Choose a Blueprint (Garment)")
# Pull all blueprints and let user search/select (some accounts have many; filter by keyword)
try:
    all_blueprints = api_get("/catalog/blueprints.json").json()  # [{id, title, brand, model, ...}]
    # Build readable labels like "Gildan 64000 (ID 145)"
    labels = []
    for b in all_blueprints:
        brand = b.get("brand") or ""
        model = b.get("model") or ""
        title = b.get("title") or f"{brand} {model}".strip()
        labels.append((f"{title}  •  {brand} {model}".strip(), b["id"]))
    # sort alphabetically
    labels.sort(key=lambda x: x[0].lower())
    options = [f"{name}  (ID {bid})" for name, bid in labels]
    default_idx = 0
    # try to preselect Gildan 64000 if present
    for i, (name, bid) in enumerate(labels):
        if "gildan" in name.lower() and "64000" in name.lower():
            default_idx = i
            break
    chosen_bp_display = st.selectbox("Blueprint", options, index=default_idx)
    BLUEPRINT_ID = int(chosen_bp_display.split("ID")[-1].strip(") ").strip())
    st.caption(f"Using blueprint ID: {BLUEPRINT_ID}")
except requests.HTTPError:
    st.stop()

# ================== PICK PROVIDER FOR BLUEPRINT ==================
st.subheader("2) Choose a Print Provider for that Blueprint")
try:
    providers = api_get(f"/catalog/blueprints/{BLUEPRINT_ID}/print_providers.json").json()
    if not providers:
        st.error("No print providers found for this blueprint. Try a different blueprint.")
        st.stop()
    provider_labels = [f"{p.get('title','?')} (ID {p['id']})" for p in providers]
    # prefer Monster Digital if present
    default_idx = 0
    for i, p in enumerate(providers):
        if p.get("title","").lower() == "monster digital":
            default_idx = i
            break
    chosen_provider_display = st.selectbox("Print Provider", provider_labels, index=default_idx)
    provider_id = int(chosen_provider_display.split("ID")[-1].strip(") "))
    st.caption(f"Using provider ID: {provider_id}")
except requests.HTTPError:
    st.stop()

# ================== FETCH VARIANTS (with 404 handling) ==================
def fetch_catalog_variants(blueprint_id: int, provider_id: int, include_oos=False):
    params = {"show-out-of-stock": 1} if include_oos else None
    # show the actual URL for debugging
    st.caption(f"Fetching variants from: /catalog/blueprints/{blueprint_id}/print_providers/{provider_id}/variants.json")
    raw = api_get(f"/catalog/blueprints/{blueprint_id}/print_providers/{provider_id}/variants.json", params=params).json()
    norm = []
    for v in raw:
        size = v.get("title") or v.get("size") or ""
        color = (v.get("options", {}).get("color", {}) or {}).get("title", "")
        if not size or not color: continue
        norm.append({"id": v["id"], "size": size, "color": color, "is_available": v.get("is_available", True)})
    return norm

include_oos = st.checkbox("Show out-of-stock colors", value=False,
                          help="For planning; OOS variants are skipped during creation.")
try:
    catalog = fetch_catalog_variants(BLUEPRINT_ID, provider_id, include_oos=include_oos)
except requests.HTTPError as e:
    st.stop()

# ================== COLOR PICKER ==================
available_colors = sorted({v["color"] for v in catalog if v["size"] in WANTED_SIZES and (include_oos or v["is_available"])})
if not available_colors:
    st.warning("No colors available for these sizes with this provider. Try another provider or toggle 'Show out-of-stock'.")
    st.stop()

st.subheader("3) Select Colors (applies to ALL uploaded designs)")
selected_colors = st.multiselect("Colors:", options=available_colors, default=available_colors)
if not selected_colors:
    st.info("Select at least one color to continue.")
    st.stop()

chosen_variants = [
    {"id": v["id"], "size": v["size"], "color": v["color"]}
    for v in catalog
    if v["size"] in WANTED_SIZES and v["color"] in selected_colors and v["is_available"]
]
if not chosen_variants:
    st.warning("No available variants match your selection. Pick different colors or provider.")
    st.stop()

# ================== UTILITIES ==================
def upload_image(file_obj) -> str:
    file_bytes = file_obj.read()
    encoded = base64.b64encode(file_bytes).decode("utf-8")
    payload = {"file_name": file_obj.name, "contents": encoded}
    r = api_post("/uploads/images.json", json=payload)
    return r.json()["id"]

def human_size_sort_key(s: str) -> int:
    order = ["XS","S","M","L","XL","2XL","3XL","4XL","5XL"]
    return order.index(s) if s in order else 999

# ================== UPLOAD & PUBLISH ==================
st.subheader("4) Upload Designs")
uploaded_files = st.file_uploader("Upload PNG/JPG", type=["png","jpg","jpeg"], accept_multiple_files=True)

if uploaded_files and st.button("🚀 Upload & Publish All"):
    for file_obj in uploaded_files:
        try:
            # 1) Upload art
            image_id = upload_image(file_obj)
            base_title = os.path.splitext(file_obj.name)[0]

            # 2) Build product
            sizes_str  = ", ".join(sorted({v["size"] for v in chosen_variants}, key=human_size_sort_key))
            colors_str = ", ".join(sorted({v["color"] for v in chosen_variants}))
            product_body = {
                "title": f"{base_title}{TITLE_SUFFIX}",
                "description": f"{chosen_provider_display.split(' (ID')[0]} • {chosen_bp_display.split('  (ID')[0]} — Colors: {colors_str}. Sizes: {sizes_str}.",
                "blueprint_id": BLUEPRINT_ID,
                "print_provider_id": provider_id,
                "variants": [{"id": v["id"], "price": VARIANT_PRICE_CENTS} for v in chosen_variants],
                "print_areas": [{
                    "variant_ids": [v["id"] for v in chosen_variants],
                    "placeholders": [{
                        "position": "front",
                        "images": [{"id": image_id, "x": CENTER_X, "y": CENTER_Y, "scale": SCALE, "angle": ANGLE}]
                    }]
                }]
            }

            # 3) Create product
            pr = api_post(f"/shops/{shop_id}/products.json", json=product_body)
            product_id = pr.json()["id"]

            # 4) Publish
            api_post(
                f"/shops/{shop_id}/products/{product_id}/publish.json",
                json={"title": True, "description": True, "images": True, "variants": True}
            )

            st.success(f"✅ Published: {base_title}  •  {len(chosen_variants)} variants")

        except requests.HTTPError as http_err:
            try: detail = http_err.response.json()
            except Exception: detail = http_err.response.text if http_err.response is not None else str(http_err)
            st.error(f"❌ HTTP error for {file_obj.name}: {http_err} | Detail: {detail}")
        except Exception as e:
            st.error(f"❌ Error processing {file_obj.name}: {e}")

elif not uploaded_files:
    st.info("Upload at least one PNG/JPG to enable publishing.")
