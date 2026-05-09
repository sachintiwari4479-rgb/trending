import streamlit as st
import requests
import base64
import json
import pandas as pd
from datetime import datetime

# Try importing curl_cffi for advanced TLS fingerprint bypassing (Crucial for Streamlit Cloud)
try:
    from curl_cffi import requests as tls_requests
    HAS_CFFI = True
except ImportError:
    HAS_CFFI = False

# ==========================================
# PAGE CONFIGURATION
# ==========================================
st.set_page_config(
    page_title="Meesho Trend Finder", 
    page_icon="📈", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# SESSION STATE INITIALIZATION
# ==========================================
if "all_products" not in st.session_state:
    st.session_state.all_products = []
    st.session_state.page = 1
    st.session_state.offset = 0
    st.session_state.current_query = ""
    st.session_state.cursor = None
    st.session_state.search_session_id = None
    st.session_state.search_mode = "Keyword Search"
    st.session_state.supplier_id = None
    st.session_state.supplier_handle = ""

# ==========================================
# HELPER FUNCTIONS
# ==========================================
def decode_meesho_metadata(encoded_str):
    if not encoded_str or not isinstance(encoded_str, str):
        return {}
    try:
        clean_str = "".join(encoded_str.split())
        padding_needed = len(clean_str) % 4
        if padding_needed:
            clean_str += "=" * (4 - padding_needed)
        decoded_bytes = base64.b64decode(clean_str)
        return json.loads(decoded_bytes)
    except Exception:
        return {}

def get_clean_headers(referer="", custom_cookie="", custom_ua=""):
    """Generates ultra-strict WAF-friendly headers matching Safari 15.5"""
    # Switching to Safari as its TLS fingerprint is less scrutinized than Chrome's
    default_ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.5 Safari/605.1.15"
    
    headers = {
        "User-Agent": custom_ua if custom_ua else default_ua,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Content-Type": "application/json",
        "MEESHO-ISO-COUNTRY-CODE": "IN",
        "Origin": "https://www.meesho.com",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "Connection": "keep-alive"
    }
    
    if referer:
        headers["Referer"] = referer
    if custom_cookie:
        headers["Cookie"] = custom_cookie
        
    return headers

def fetch_meesho_data(query, limit=20, page=1, offset=0, cursor=None, search_session_id=None, custom_cookie="", custom_ua="", proxies=None):
    url = "https://www.meesho.com/api/v1/products/search"
    referer = f"https://www.meesho.com/search?q={query.replace(' ', '%20')}"
    headers = get_clean_headers(referer, custom_cookie, custom_ua)

    payload = {
        "query": query,
        "type": "text_search",
        "page": page,
        "offset": offset,
        "limit": limit,
        "cursor": cursor,
        "isDevicePhone": False
    }
    if search_session_id:
        payload["search_session_id"] = search_session_id

    try:
        if HAS_CFFI:
            # Changed impersonate to safari15_5 to drastically alter the TLS fingerprint
            response = tls_requests.post(url, headers=headers, json=payload, impersonate="safari15_5", timeout=15, proxies=proxies)
        else:
            response = requests.post(url, headers=headers, json=payload, timeout=10, proxies=proxies)
            
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"API Error: {response.status_code}")
            with st.expander("🔍 View Raw Debug Info (Headers & Response)"):
                st.write("**Request Headers Sent:**")
                st.json(dict(response.request.headers))
                st.write("**Response Headers Received:**")
                st.json(dict(response.headers))
                st.write("**Response Body:**")
                st.code(response.text, language="html")
            return None
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return None

def fetch_supplier_profile(handle, custom_cookie="", custom_ua="", proxies=None):
    url = f"https://www.meesho.com/api/v1/meri-shop/profile?supplierHandle={handle}"
    referer = f"https://www.meesho.com/{handle}?ms=2"
    headers = get_clean_headers(referer, custom_cookie, custom_ua)

    try:
        if HAS_CFFI:
            response = tls_requests.get(url, headers=headers, impersonate="safari15_5", timeout=15, proxies=proxies)
        else:
            response = requests.get(url, headers=headers, timeout=10, proxies=proxies)
            
        if response.status_code == 200:
            data = response.json()
            return data.get("profile", {}).get("masked_id")
        else:
            st.error(f"Profile API Error: {response.status_code}")
            with st.expander("🔍 View Raw Debug Info (Headers & Response)"):
                st.write("**Response Headers Received:**")
                st.json(dict(response.headers))
                st.write("**Response Body:**")
                st.code(response.text, language="html")
            return None
    except Exception:
        return None

def fetch_supplier_feed(supplier_id, handle, limit=20, offset=0, custom_cookie="", custom_ua="", proxies=None):
    url = "https://www.meesho.com/api/v1/meri-shop/feed"
    referer = f"https://www.meesho.com/{handle}?ms=2&Sort[sort_by]=created&Sort[sort_order]=desc"
    headers = get_clean_headers(referer, custom_cookie, custom_ua)

    payload = {
        "limit": limit,
        "offset": offset,
        "supplier_id": supplier_id,
        "featured_collection_type": None,
        "filter": {
            "selected_filter_ids": [],
            "type": "shop",
            "sort_option": {"sort_by": "created", "sort_order": "desc"},
            "session_state": None
        }
    }
    try:
        if HAS_CFFI:
            response = tls_requests.post(url, headers=headers, json=payload, impersonate="safari15_5", timeout=15, proxies=proxies)
        else:
            response = requests.post(url, headers=headers, json=payload, timeout=10, proxies=proxies)
            
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Feed API Error: {response.status_code}")
            with st.expander("🔍 View Raw Debug Info (Headers & Response)"):
                st.write("**Response Headers Received:**")
                st.json(dict(response.headers))
                st.write("**Response Body:**")
                st.code(response.text, language="html")
            return None
    except Exception:
        return None

def process_catalogs(raw_data):
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
        state_code = item.get('state_code', 'N/A')

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
        profit_gap = (serving_price - supplier_price) if (serving_price is not None and supplier_price is not None) else None

        age_days = 1
        if created_date_str:
            try:
                created_date = datetime.fromisoformat(created_date_str)
                age_days = max(1, abs((datetime.now() - created_date).days))
            except ValueError:
                pass

        # Calculations
        velocity = round(rating_count / age_days, 2)
        est_orders_per_day = round(velocity / 0.15, 2)
        safe_rto = rto_risk if rto_risk is not None else 0.50
        
        # Improved Trend Score: Higher emphasis on Velocity and Avg Rating
        trend_score = round(velocity * avg_rating * (1 - safe_rto), 2)

        # Restored your exact details
        parsed_list.append({
            "Image": image_url,
            "Product Name": name,
            "Trend Score": trend_score,
            "Velocity (Ratings/Day)": velocity,
            "Est. Orders/Day": est_orders_per_day,
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
            "State Code": state_code,
            "is_genuine": is_genuine_product_trend,
            "sup_rating_count": sup_rating_count
        })

    return parsed_list

# ==========================================
# MAIN APP UI & SIDEBAR
# ==========================================
st.title("🚀 Meesho Trending Product Finder")
st.markdown("Discover winning products automatically by analyzing **Velocity, Ratings, and RTO Risks**.")

with st.sidebar:
    st.header("Search Mode")
    search_mode = st.radio("Search Mode", ["Keyword Search", "Store/Supplier Search"], horizontal=True, label_visibility="collapsed")

    search_query = ""
    supplier_handle = ""

    if search_mode == "Keyword Search":
        auto_category = st.selectbox("Quick Niche", ["Custom Search...", "Smartwatches", "Home Decor", "Sarees", "Kitchen Gadgets", "Makeup", "Toys", "Mens T-shirts"])
        if auto_category == "Custom Search...":
            search_query = st.text_input("Product Keyword", value="photo sketch")
        else:
            search_query = auto_category
    else:
        supplier_handle = st.text_input("Supplier Handle", value="ShreeRadhaRaniPrints", help="Found in the Meesho URL (e.g. www.meesho.com/ShreeRadhaRaniPrints)")

    # Button moved directly below inputs
    btn_label = f"🔍 Analyze '{search_query}' Trends" if search_mode == "Keyword Search" else f"🏪 Analyze Store '{supplier_handle}'"
    analyze_clicked = st.button(btn_label, type="primary", use_container_width=True)

    st.divider()

    st.header("Security & Authentication")
    
    if not HAS_CFFI:
        st.error("🚨 **CRITICAL FIX FOR STREAMLIT CLOUD:**\nStandard Python requests get blocked by Meesho's WAF (TLS Fingerprinting). To fix this permanently:\n1. Create a **`requirements.txt`** file in your GitHub repository.\n2. Add this exact line: `curl_cffi==0.7.1`\n\nThis makes your app perfectly impersonate Google Chrome.")
    else:
        st.success("✅ **Advanced Browser Spoofing Active! (curl_cffi loaded)**")
        
    st.warning("☁️ **Cookies:** Even with spoofing, providing a cookie below improves success rates on cloud servers.")
    cookie_input = st.text_input("Meesho Cookie", type="password", help="Go to Meesho -> F12 (Network) -> Search something -> Click 'search' request -> Copy 'Cookie' from Request Headers.")
    ua_input = st.text_input("Browser User-Agent (Optional)", help="If the cookie alone fails on Streamlit, copy your browser's exact User-Agent string here.")

    st.divider()
    st.header("Deep Search Settings")
    fetch_limit = st.slider("Products Per Page", min_value=20, max_value=200, value=50, step=10)

    auto_fetch_deep = st.toggle("🤖 Auto-Fetch Multiple Pages", value=False, help="Automatically scrolls and fetches next pages until no more products are found or limit is reached.")
    max_pages = 1
    if auto_fetch_deep:
        max_pages = st.slider("Max Pages to Auto-Fetch", min_value=2, max_value=50, value=5)

    st.divider()
    st.header("Viral Product Filters")
    max_age_filter = st.number_input("Max Product Age (Days)", min_value=0, value=0, help="Find new viral products! E.g. Set to 30 to only show products listed in the last month. 0 = No limit.")
    min_velocity = st.number_input("Minimum Velocity Filter (Ratings/Day)", min_value=0.0, value=0.0, step=0.5)

    st.divider()
    st.header("🌐 Cloud Bypass (Proxies)")
    st.warning("If hosted on Streamlit Cloud, Meesho's Akamai Firewall will block the server IP. Use a Residential Proxy to bypass this.")
    proxy_url = st.text_input("Proxy URL", help="Format: http://username:password@ip:port (e.g., from Webshare or BrightData)")
    
    proxy_dict = {"http": proxy_url, "https": proxy_url} if proxy_url else None

# ------------------------------------------
# SEARCH ACTION LOGIC
# ------------------------------------------
if analyze_clicked:
    st.session_state.all_products = []
    st.session_state.page = 1
    st.session_state.offset = 0
    st.session_state.current_query = search_query
    st.session_state.cursor = None
    st.session_state.search_session_id = None
    st.session_state.search_mode = search_mode
    st.session_state.supplier_id = None
    st.session_state.supplier_handle = supplier_handle

    if search_mode == "Store/Supplier Search":
        masked_id = fetch_supplier_profile(supplier_handle, cookie_input, ua_input, proxy_dict)
        if masked_id:
            st.session_state.supplier_id = masked_id
        else:
            st.error(f"Could not find the Store ID. Ensure the handle '{supplier_handle}' is correct.")
            st.stop()

    with st.status(f"Fetching up to {max_pages} pages of products...", expanded=True) as status:
        for p in range(1, max_pages + 1):
            st.write(f"Fetching page {p}...")

            if search_mode == "Keyword Search":
                raw_data = fetch_meesho_data(
                    search_query, 
                    fetch_limit, 
                    st.session_state.page, 
                    st.session_state.offset, 
                    st.session_state.cursor, 
                    st.session_state.search_session_id, 
                    cookie_input, 
                    ua_input,
                    proxy_dict # Pass proxy here
                )
                if raw_data:
                    st.session_state.cursor = raw_data.get('cursor')
                    st.session_state.search_session_id = raw_data.get('search_session_id')
            else:
                raw_data = fetch_supplier_feed(
                    st.session_state.supplier_id, 
                    supplier_handle, 
                    fetch_limit, 
                    st.session_state.offset, 
                    cookie_input, 
                    ua_input,
                    proxy_dict # Pass proxy here
                )

            if not raw_data:
                st.write("Stopped due to API constraints or no more data.")
                break

            parsed_data = process_catalogs(raw_data)
            if not parsed_data:
                st.write("No more products found.")
                break

            st.session_state.all_products.extend(parsed_data)
            st.session_state.page += 1
            st.session_state.offset += fetch_limit

            if search_mode == "Keyword Search" and not st.session_state.cursor:
                st.write("Reached the end of search results.")
                break

        status.update(label=f"Done! Fetched {len(st.session_state.all_products)} products total.", state="complete", expanded=False)

# ------------------------------------------
# RENDER UI FROM SESSION STATE
# ------------------------------------------
if st.session_state.all_products:
    df_all = pd.DataFrame(st.session_state.all_products)

    # Apply user Filters
    df_all = df_all[df_all['Velocity (Ratings/Day)'] >= min_velocity]
    if max_age_filter > 0:
        df_all = df_all[df_all['Age (Days)'] <= max_age_filter]

    df_genuine = df_all[df_all['is_genuine'] == True].copy()
    df_supplier = df_all[(df_all['is_genuine'] == False) & (df_all['sup_rating_count'] > 0)].copy()

    # --- KPI METRICS DASHBOARD ---
    st.markdown("### 📊 Market Overview")
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Products Found", len(df_all))
    col2.metric("Filtered Valid Trends", len(df_genuine))
    
    if not df_genuine.empty:
        max_vel = df_genuine['Velocity (Ratings/Day)'].max()
        col3.metric("Highest Daily Velocity", f"{max_vel} / day")
    
    st.divider()

    tab_main, tab_data, tab_suppliers = st.tabs([
        "🔥 Top Products Grid", "🗄️ Interactive Data Table", "👑 Top Suppliers (Manual Check)"
    ])

    # TAB 1: GENUINE PRODUCTS (Sorted by Highest Selling / Velocity)
    with tab_main:
        if not df_genuine.empty:
            # Sorted strictly from High Selling to Low Selling
            df_genuine = df_genuine.sort_values(by="Velocity (Ratings/Day)", ascending=False)

            st.subheader(f"📋 {len(df_genuine)} Products (Sorted by Highest Velocity/Sales)")

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

                                sup_cost_str = f"₹{row['Supplier Set Price (₹)']}" if pd.notna(row['Supplier Set Price (₹)']) else "N/A"
                                sell_price_str = f"₹{row['Selling Price (₹)']}" if pd.notna(row['Selling Price (₹)']) else "N/A"
                                log_cost_str = f"₹{row['Logistics Cost (₹)']}" if pd.notna(row['Logistics Cost (₹)']) else "N/A"
                                ship_adj_str = f"₹{row['Shipping Adjustment (₹)']}" if pd.notna(row['Shipping Adjustment (₹)']) else "N/A"

                                state_display = f"📍 **Local (RJ)**" if row['State Code'] == 'RJ' else f"🗺️ **State:** {row['State Code']}"

                                st.markdown(f"""
                                * ⚡ **Velocity:** **{row['Velocity (Ratings/Day)']}** ratings/day
                                * 📦 **Est. Orders/Day:** ~{row['Est. Orders/Day']}
                                * ⭐ **Avg Rating:** {row['Avg Rating']}
                                * 📊 **Total Ratings:** {row['Total Ratings']}
                                * 💬 **Total Reviews:** {row['Total Reviews']}
                                * 🌟 **5-Star Ratings:** {row['5-Star Ratings']}
                                * 💰 **Supplier Price:** {sup_cost_str} | 🛒 **Sell Price:** {sell_price_str}
                                * 🚚 **Logistics:** {log_cost_str} | ⚖️ **Ship Adj:** {ship_adj_str}
                                * {state_display}
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
            st.warning("No genuine product trends found matching your filters.")

    # TAB 2: INTERACTIVE DATA TABLE
    with tab_data:
        st.markdown("### 🗄️ Raw Data Explorer")
        if not df_genuine.empty:
            display_cols = ['Product Name', 'Velocity (Ratings/Day)', 'Trend Score', 'Est. Orders/Day', 'Total Ratings', 
                            'Total Reviews', '5-Star Ratings', 'Avg Rating', 'Supplier Set Price (₹)', 
                            'Selling Price (₹)', 'Logistics Cost (₹)', 'Shipping Adjustment (₹)', 'Age (Days)', 'Product URL']
            
            st.dataframe(
                df_genuine[display_cols],
                use_container_width=True,
                height=600,
                column_config={
                    "Product URL": st.column_config.LinkColumn("Product URL", display_text="View on Meesho")
                }
            )
            
            csv = df_genuine.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Data as CSV", data=csv, file_name=f"meesho_trends_{search_query.replace(' ', '_')}.csv", mime="text/csv")
        else:
            st.info("No data available to display.")

    # TAB 3: TOP SUPPLIERS (SUPPLIER METRICS)
    with tab_suppliers:
        if not df_supplier.empty:
            st.info("💡 **NOTE:** These are completely new or unrated products. The huge velocity and ratings shown below belong to the **Supplier's entire account**.")
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

                                sup_cost_str = f"₹{row['Supplier Set Price (₹)']}" if pd.notna(row['Supplier Set Price (₹)']) else "N/A"
                                sell_price_str = f"₹{row['Selling Price (₹)']}" if pd.notna(row['Selling Price (₹)']) else "N/A"
                                log_cost_str = f"₹{row['Logistics Cost (₹)']}" if pd.notna(row['Logistics Cost (₹)']) else "N/A"

                                state_display = f"📍 **Local (RJ)**" if row['State Code'] == 'RJ' else f"🗺️ **State:** {row['State Code']}"

                                st.markdown(f"""
                                * ⚡ **Sup. Velocity:** {row['Velocity (Ratings/Day)']}/day
                                * 📦 **Sup. Est. Orders/Day:** ~{row['Est. Orders/Day']}
                                * ⭐ **Sup. Avg Rating:** {row['Avg Rating']}
                                * 📊 **Sup. Total Ratings:** {row['Total Ratings']}
                                * 💰 **Supplier Set Price:** {sup_cost_str}
                                * 🛒 **Selling Price:** {sell_price_str}
                                * 🚚 **Logistics:** {log_cost_str}
                                * {state_display}
                                """)

                                if pd.isna(row['RTO Risk']):
                                    st.info("RTO Data Unavailable")
                                elif row['RTO Risk'] > 0.80:
                                    st.error(f"High RTO Risk: {row['RTO Risk']}")
                                else:
                                    st.success(f"Safe RTO Level: {row['RTO Risk']}")

                                if pd.notna(row['Product URL']) and row['Product URL']:
                                    st.link_button("🛍️ Open for Manual Check", row['Product URL'], use_container_width=True)
        else:
            st.warning("No high-rated supplier accounts found uploading new products in this batch.")

    # ------------------------------------------
    # MANUAL LOAD MORE BUTTON (Fallback)
    # ------------------------------------------
    if not st.session_state.get('auto_fetch_deep', False):
        st.divider()
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("⬇️ Manually Fetch 1 More Page", use_container_width=True):
                with st.spinner(f"Fetching next {fetch_limit} products..."):
                    if st.session_state.search_mode == "Keyword Search":
                        raw_data = fetch_meesho_data(st.session_state.current_query, fetch_limit, st.session_state.page, st.session_state.offset, st.session_state.cursor, st.session_state.search_session_id, cookie_input, ua_input, proxy_dict)
                        if raw_data:
                            st.session_state.cursor = raw_data.get('cursor')
                            st.session_state.search_session_id = raw_data.get('search_session_id')
                            parsed_data = process_catalogs(raw_data)
                            if parsed_data:
                                st.session_state.all_products.extend(parsed_data)
                                st.session_state.page += 1
                                st.session_state.offset += fetch_limit
                                st.rerun()
                            else:
                                st.info("No more products found on Meesho for this query.")
                    elif st.session_state.search_mode == "Store/Supplier Search":
                        raw_data = fetch_supplier_feed(st.session_state.supplier_id, st.session_state.supplier_handle, fetch_limit, st.session_state.offset, cookie_input, ua_input, proxy_dict)
                        if raw_data:
                            parsed_data = process_catalogs(raw_data)
                            if parsed_data:
                                st.session_state.all_products.extend(parsed_data)
                                st.session_state.page += 1
                                st.session_state.offset += fetch_limit
                                st.rerun()
                            else:
                                st.info("No more products found in this store's catalog.")
