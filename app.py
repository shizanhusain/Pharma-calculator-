import streamlit as st
import pandas as pd

st.set_page_config(layout="wide")

st.title("💊 Pharma Adjustment Calculator")

# Inputs
margin_percent = st.number_input("Margin %", value=10.0)

cost_file = st.file_uploader("Upload Cost File", type=["xlsx"])
sales_file = st.file_uploader("Upload Sales File", type=["xlsx"])

def parse_deal(deal):
    try:
        x, y = deal.split("+")
        return float(x), float(y)
    except:
        return None, None

if st.button("Calculate Adjustment"):

    if cost_file is None or sales_file is None:
        st.error("❌ Upload both files")
        st.stop()

    cost_df = pd.read_excel(cost_file)
    sales_df = pd.read_excel(sales_file)

    # REQUIRED COLUMNS
    required_cost_cols = ["Product Name", "Cost Price", "Deal"]
    required_sales_cols = ["Party Name", "Product Name", "Qty", "Free", "Rate"]

    if not all(col in cost_df.columns for col in required_cost_cols):
        st.error("❌ Cost file format incorrect")
        st.stop()

    if not all(col in sales_df.columns for col in required_sales_cols):
        st.error("❌ Sales file format incorrect")
        st.stop()

    # Merge
    df = pd.merge(
        sales_df,
        cost_df,
        on="Product Name",
        how="left"
    )

    if df["Cost Price"].isna().any():
        missing = df[df["Cost Price"].isna()]
        st.error("❌ Product not found in cost file")
        st.dataframe(missing)
        st.stop()

    results = []

    for _, row in df.iterrows():

        party = row["Party Name"]
        product = row["Product Name"]
        qty = row["Qty"]
        free = row["Free"]
        rate = row["Rate"]
        cost = row["Cost Price"]
        deal = row["Deal"]

        base, deal_free = parse_deal(deal)

        if base is None:
            st.error(f"❌ Invalid deal format for {product}")
            st.stop()

        # DEFAULTS
        allowed_free = (qty / base) * deal_free if base != 0 else 0
        extra_free = max(0, free - allowed_free)

        # Effective cost
        effective_cost = cost / (1 + (deal_free / base)) if base != 0 else cost

        expected_price = effective_cost * (1 + margin_percent / 100)

        # LOSSES
        scheme_loss = extra_free * cost
        margin_loss = 0

        # NET SALE LOGIC
        if free == 0:
            if rate < expected_price:
                margin_loss = (expected_price - rate) * qty

        # SCHEME SALE LOGIC
        else:
            if extra_free > 0:
                scheme_loss = extra_free * cost

        total_loss = scheme_loss + margin_loss

        results.append({
            "Party Name": party,
            "Product Name": product,
            "Quantity Sold": qty,
            "Free Given": free,
            "Allowed Free": round(allowed_free, 2),
            "Extra Free": round(extra_free, 2),
            "Effective Cost": round(effective_cost, 2),
            "Expected Selling Price": round(expected_price, 2),
            "Actual Selling Price": rate,
            "Margin Loss": round(margin_loss, 2),
            "Scheme Loss": round(scheme_loss, 2),
            "Total Adjustment": round(total_loss, 2)
        })

    result_df = pd.DataFrame(results)

    st.subheader("📊 Detailed Report")
    st.dataframe(result_df)

    total_loss = result_df["Total Adjustment"].sum()

    st.success(f"💰 Total Adjustment Loss: ₹ {round(total_loss,2)}")

    # Download
    st.download_button(
        "⬇ Download Excel",
        result_df.to_csv(index=False).encode("utf-8"),
        "adjustment_report.csv",
        "text/csv"
    )
