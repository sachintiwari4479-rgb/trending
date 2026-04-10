import streamlit as st
import requests
import base64
import json
import pandas as pd
from datetime import datetime

# ==========================================
# PAGE CONFIGURATION
# ==========================================
st.set_page_config(page_title="Meesho Trend Finder", page_icon="📈", layout="wide")

# ==========================================
# SESSION STATE INITIALIZATION
# ==========================================
# We use session state to hold products so we can append more data (Load More functionality)
if "all_products" not in st.session_state:
    st.session_state.all_products = []
    st.session_state.page = 1
    st.session_state.offset = 0
    st.session_state.current_query = ""


# ==========================================
# HELPER FUNCTIONS
# ==========================================
def decode_meesho_metadata(encoded_str):
    """Decodes the base64 price_metadata field from Meesho API with padding correction."""
    if not encoded_str or not isinstance(encoded_str, str):
        return {}
    try:
        clean_str = "".join(encoded_str.split())
        padding_needed = len(clean_str) % 4
        if padding_needed:
            clean_str += "=" * (4 - padding_needed)

        decoded_bytes = base64.b64decode(clean_str)
        return json.loads(decoded_bytes)
    except Exception as e:
        print(f"Metadata Decode Error: {e}")
        return {}


def fetch_meesho_data(query, limit=10, page=1, offset=0):
    """Fetches data from Meesho API handling pagination (page & offset)."""
    url = "https://www.meesho.com/api/v1/products/search"

    headers = {
        "sec-ch-ua-platform": '"Windows"',
        "MEESHO-ISO-COUNTRY-CODE": "IN",
        "X-WISHLIST-AGGREGATION-REQUIRED": "true",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Origin": "https://www.meesho.com",
        "Referer": f"https://www.meesho.com/search?q={query.replace(' ', '%20')}",
        "Accept-Language": "en-US,en;q=0.9"
    }

    payload = {
        "query": query,
        "type": "text_search",
        "page": page,
        "offset": offset,
        "limit": limit,
        "cursor": None,
        "isDevicePhone": False
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"API Error: {response.status_code}")
            return None
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return None


def process_catalogs(raw_data):
    """Extracts and parses all products from the raw API response."""
    parsed_list = []
    if not raw_data or 'catalogs' not in raw_data:
        return parsed_list

    for item in raw_data['catalogs']:
        name = item.get('name', 'Unknown')
        created_date_str = item.get('created_iso', '').split('+')[0]
        is_ad = item.get('isAdProduct', False)
        image_url = item.get('image', '')
        product_id = item.get('product_id', '')
        product_url = f"https://www.meesho.com/s/p/{product_id}" if product_id else None

        # STRICT SPLIT LOGIC
        cat_reviews = item.get('catalog_reviews_summary', {}) or {}
        sup_reviews = item.get('supplier_reviews_summary', {}) or {}

        cat_rating_count = cat_reviews.get('rating_count', 0)
        sup_rating_count = sup_reviews.get('rating_count', 0)

        is_genuine_product_trend = cat_rating_count > 0
        active_reviews = cat_reviews if is_genuine_product_trend else sup_reviews

        rating_count = active_reviews.get('rating_count', 0)
        review_count = active_reviews.get('review_count', 0)
        avg_rating = active_reviews.get('average_rating', 0.0)

        rating_map = active_reviews.get('rating_count_map', {})
        five_star_count = rating_map.get('5', rating_map.get(5, 0))

        meta_encoded = item.get('app_event_data', {}).get('price_metadata', '')
        meta_decoded = decode_meesho_metadata(meta_encoded)

        supplier_price = meta_decoded.get('supplierPrice')
        serving_price = meta_decoded.get('servingPrice', item.get('min_product_price'))
        logistics_charge = meta_decoded.get('logisticsCharge')
        shipping_adjustment = meta_decoded.get('shippingChargesAdjustment')
        rto_cod_percent = meta_decoded.get('rtoPercentageCod')

        rto_risk = round(rto_cod_percent, 3) if rto_cod_percent is not None else None
        profit_gap = (serving_price - supplier_price) if (
                    serving_price is not None and supplier_price is not None) else None

        age_days = 1
        if created_date_str:
            try:
                created_date = datetime.fromisoformat(created_date_str)
                age_days = max(1, (datetime.now() - created_date).days)
            except ValueError:
                pass

        velocity = round(rating_count / age_days, 2)
        safe_rto = rto_risk if rto_risk is not None else 0.50
        trend_score = round(velocity * (avg_rating / 5.0) * (1 - safe_rto), 2)

        parsed_list.append({
            "Image": image_url,
            "Product Name": name,
            "Trend Score": trend_score,
            "Velocity (Ratings/Day)": velocity,
            "Total Ratings": rating_count,
            "Total Reviews": review_count,
            "5-Star Ratings": five_star_count,
            "Avg Rating": avg_rating,
            "Supplier Set Price (₹)": supplier_price,
            "Selling Price (₹)": serving_price,
            "Profit Gap (₹)": profit_gap,
            "Logistics Cost (₹)": logistics_charge,
            "Shipping Adjustment (₹)": shipping_adjustment,
            "RTO Risk": rto_risk,
            "Is Ad?": "Yes 📢" if is_ad else "No 🟢",
            "Age (Days)": age_days,
            "Product URL": product_url,
            "is_genuine": is_genuine_product_trend,
            "sup_rating_count": sup_rating_count
        })

    return parsed_list


# ==========================================
# MAIN APP UI
# ==========================================
st.title("🚀 Meesho Trending Product Finder")
st.markdown("Discover winning products automatically by analyzing **Velocity, Supplier Costs, and RTO Risks**.")

# Sidebar Filters
with st.sidebar:
    st.header("Search Parameters")
    auto_category = st.selectbox("Auto-Discover Categories",
                                 ["Custom Search...", "Smartwatches", "Home Decor", "Sarees", "Kitchen Gadgets",
                                  "Makeup", "Toys", "Mens T-shirts"])

    if auto_category == "Custom Search...":
        search_query = st.text_input("Product Keyword", value="Gift item")
    else:
        search_query = auto_category

    # Increased max products to 500
    fetch_limit = st.slider("Products Per Batch (Fetch Size)", min_value=10, max_value=300, value=250, step=10)
    min_velocity = st.number_input("Minimum Velocity Filter (Ratings/Day)", min_value=0.0, value=0.0, step=0.5)

    st.divider()
    st.markdown("**How we calculate the Best Product (Trend Score):**")
    st.markdown(
        "We combine High Velocity, High Ratings, and Low RTO Risk to automatically rank the absolute best products.")

# ------------------------------------------
# INITIAL SEARCH ACTION
# ------------------------------------------
if st.button(f"🔍 Analyze '{search_query}' Trends", type="primary"):
    # Reset session state for new search
    st.session_state.all_products = []
    st.session_state.page = 1
    st.session_state.offset = 0
    st.session_state.current_query = search_query

    with st.spinner(f"Fetching first {fetch_limit} products and calculating Scores..."):
        raw_data = fetch_meesho_data(search_query, fetch_limit, 1, 0)

        if raw_data:
            print("\n" + "=" * 50)
            print(f"RAW API RESPONSE FOR '{search_query}' (Page 1):")
            print("=" * 50)
            print(json.dumps(raw_data, indent=2))
            print("=" * 50 + "\n")

            parsed_data = process_catalogs(raw_data)
            st.session_state.all_products.extend(parsed_data)
        else:
            st.error("Failed to retrieve valid catalog data from Meesho.")

# ------------------------------------------
# RENDER PRODUCTS (FROM SESSION STATE)
# ------------------------------------------
if st.session_state.all_products:
    # Convert all stored products to DataFrame
    df_all = pd.DataFrame(st.session_state.all_products)

    # Apply user Velocity Filter
    df_all = df_all[df_all['Velocity (Ratings/Day)'] >= min_velocity]

    # Split into genuine vs supplier metrics based on our stored flags
    df_genuine = df_all[df_all['is_genuine'] == True].copy()
    df_supplier = df_all[(df_all['is_genuine'] == False) & (df_all['sup_rating_count'] > 0)].copy()

    # RENDER DASHBOARD TABS
    tab_main, tab_suppliers = st.tabs(["🔥 Genuine Trending Products", "👑 Top Suppliers (Manual Check)"])

    # TAB 1: GENUINE PRODUCTS
    with tab_main:
        if not df_genuine.empty:
            df_genuine = df_genuine.sort_values(by="Trend Score", ascending=False)

            # ULTIMATE TOP PICK
            best_product = df_genuine.iloc[0]
            st.subheader("🏆 Automatic Top Pick (Best Overall Trend)")

            tc1, tc2 = st.columns([1, 3])
            with tc1:
                st.image(best_product['Image'], use_container_width=True)
            with tc2:
                st.markdown(f"### {best_product['Product Name']}")
                st.markdown(f"**Trend Score: {best_product['Trend Score']}** 🔥")
                st.markdown(
                    f"This product was automatically selected as the best opportunity because it balances high daily sales velocity (**{best_product['Velocity (Ratings/Day)']} ratings/day**) with a strong average rating (**{best_product['Avg Rating']}⭐**) and manageable return risks.")

                st.markdown(f"""
                * 💰 **Supplier Set Price:** ₹{best_product['Supplier Set Price (₹)']} | 🛒 **Selling Price:** ₹{best_product['Selling Price (₹)']}
                * 🌟 **Total Ratings:** {best_product['Total Ratings']} ({best_product['5-Star Ratings']} Five-Star)
                * 📈 **RTO Risk:** {best_product['RTO Risk']}
                """)
                if pd.notna(best_product['Product URL']):
                    st.link_button("🛍️ View Top Pick on Meesho", best_product['Product URL'])

            st.divider()

            st.subheader(f"📋 Searched Products ({len(df_genuine)} Results Ranked by Trend Score)")

            # Display Grid
            num_cols = 3
            for i in range(0, len(df_genuine), num_cols):
                cols = st.columns(num_cols)
                for j in range(num_cols):
                    if i + j < len(df_genuine):
                        row = df_genuine.iloc[i + j]
                        with cols[j]:
                            with st.container(border=True):
                                st.image(row['Image'], use_container_width=True)
                                st.markdown(f"**{row['Product Name']}**")

                                st.markdown(f"🔥 **Trend Score: {row['Trend Score']}**")
                                st.caption(f"{row['Is Ad?']} | {row['Age (Days)']} Days Old")

                                sup_cost_str = f"₹{row['Supplier Set Price (₹)']}" if pd.notna(
                                    row['Supplier Set Price (₹)']) else "N/A"
                                sell_price_str = f"₹{row['Selling Price (₹)']}" if pd.notna(
                                    row['Selling Price (₹)']) else "N/A"
                                log_cost_str = f"₹{row['Logistics Cost (₹)']}" if pd.notna(
                                    row['Logistics Cost (₹)']) else "N/A"
                                ship_adj_str = f"₹{row['Shipping Adjustment (₹)']}" if pd.notna(
                                    row['Shipping Adjustment (₹)']) else "N/A"

                                st.markdown(f"""
                                * ⚡ **Velocity:** {row['Velocity (Ratings/Day)']} ratings/day
                                * ⭐ **Avg Rating:** {row['Avg Rating']}
                                * 📊 **Total Ratings:** {row['Total Ratings']}
                                * 📝 **Total Reviews:** {row['Total Reviews']}
                                * 🌟 **5-Star Ratings:** {row['5-Star Ratings']}
                                * 💰 **Supplier Set Price:** {sup_cost_str}
                                * 🛒 **Selling Price:** {sell_price_str}
                                * 🚚 **Logistics:** {log_cost_str}
                                * ⚖️ **Shipping Adj:** {ship_adj_str}
                                """)

                                if pd.isna(row['RTO Risk']):
                                    st.info("RTO Data Unavailable")
                                elif row['RTO Risk'] > 0.80:
                                    st.error(f"High RTO Risk: {row['RTO Risk']}")
                                else:
                                    st.success(f"Safe RTO Level: {row['RTO Risk']}")

                                if pd.notna(row['Product URL']) and row['Product URL']:
                                    st.link_button("🛍️ View on Meesho", row['Product URL'], use_container_width=True)
        else:
            st.warning(
                "No genuine product trends found in this search. Try fetching more products or adjusting the velocity filter.")

    # TAB 2: TOP SUPPLIERS (SUPPLIER METRICS)
    with tab_suppliers:
        if not df_supplier.empty:
            st.info(
                "💡 **NOTE:** These are completely new or unrated products. The huge velocity and ratings shown below belong to the **Supplier's entire account**, not the specific item. Use these to manually spot new uploads from successful sellers!")
            df_supplier = df_supplier.sort_values(by="Velocity (Ratings/Day)", ascending=False)

            st.subheader(f"👑 Found {len(df_supplier)} New Products from Big Suppliers")

            num_cols = 3
            for i in range(0, len(df_supplier), num_cols):
                cols = st.columns(num_cols)
                for j in range(num_cols):
                    if i + j < len(df_supplier):
                        row = df_supplier.iloc[i + j]
                        with cols[j]:
                            with st.container(border=True):
                                st.image(row['Image'], use_container_width=True)
                                st.markdown(f"**{row['Product Name']}**")

                                st.markdown(f"👑 **Supplier Account Stats**")
                                st.caption(f"{row['Is Ad?']} | Listed {row['Age (Days)']} Days Ago")

                                sup_cost_str = f"₹{row['Supplier Set Price (₹)']}" if pd.notna(
                                    row['Supplier Set Price (₹)']) else "N/A"
                                sell_price_str = f"₹{row['Selling Price (₹)']}" if pd.notna(
                                    row['Selling Price (₹)']) else "N/A"
                                log_cost_str = f"₹{row['Logistics Cost (₹)']}" if pd.notna(
                                    row['Logistics Cost (₹)']) else "N/A"

                                st.markdown(f"""
                                * ⚡ **Sup. Velocity:** {row['Velocity (Ratings/Day)']}/day
                                * ⭐ **Sup. Avg Rating:** {row['Avg Rating']}
                                * 📊 **Sup. Total Ratings:** {row['Total Ratings']}
                                * 💰 **Supplier Set Price:** {sup_cost_str}
                                * 🛒 **Selling Price:** {sell_price_str}
                                * 🚚 **Logistics:** {log_cost_str}
                                """)

                                if pd.isna(row['RTO Risk']):
                                    st.info("RTO Data Unavailable")
                                elif row['RTO Risk'] > 0.80:
                                    st.error(f"High RTO Risk: {row['RTO Risk']}")
                                else:
                                    st.success(f"Safe RTO Level: {row['RTO Risk']}")

                                if pd.notna(row['Product URL']) and row['Product URL']:
                                    st.link_button("🛍️ Open for Manual Check", row['Product URL'],
                                                   use_container_width=True)
        else:
            st.warning("No high-rated supplier accounts found uploading new products in this batch.")

    # ------------------------------------------
    # INFINITE SCROLL / LOAD MORE BUTTON
    # ------------------------------------------
    st.divider()
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("⬇️ Fetch More Products (Load Next Page)", use_container_width=True, type="primary"):
            st.session_state.page += 1
            st.session_state.offset += fetch_limit

            with st.spinner(f"Fetching next {fetch_limit} products..."):
                raw_data = fetch_meesho_data(st.session_state.current_query, fetch_limit, st.session_state.page,
                                             st.session_state.offset)
                if raw_data:
                    parsed_data = process_catalogs(raw_data)
                    if parsed_data:
                        st.session_state.all_products.extend(parsed_data)
                        st.rerun()  # Immediately refresh the UI to show the new items
                    else:
                        st.info("No more products found on Meesho for this query.")