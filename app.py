import streamlit as st
import pandas as pd

# -----------------------------
# PAGE CONFIG
# -----------------------------
st.set_page_config(page_title="Pharma Adjustment Calculator", layout="wide")

st.title("💊 Pharma Adjustment Calculator")
st.markdown("Upload cost file and sales file to calculate adjustment")

# -----------------------------
# HELPER FUNCTIONS
# -----------------------------

def clean_product_name(name):
    return str(name).strip().upper()

def parse_deal(deal):
    try:
        if pd.isna(deal) or str(deal).strip() == "":
            return 1, 0
        deal = str(deal).replace(" ", "")
        x, y = deal.split("+")
        return int(x), int(y)
    except:
        return 1, 0

def calculate_ec(price, qty, free):
    try:
        total = qty + free
        return (price * qty) / total if total != 0 else 0
    except:
        return 0

def calculate_esp(rate, qty, free):
    try:
        total = qty + free
        if free == 0:
            return rate
        return (rate * qty) / total if total != 0 else 0
    except:
        return 0

# -----------------------------
# FILE UPLOAD
# -----------------------------
st.sidebar.header("📁 Upload Files")

cost_file = st.sidebar.file_uploader("Upload COST FILE", type=["xlsx"])
sales_file = st.sidebar.file_uploader("Upload SALES FILE", type=["xlsx"])

# -----------------------------
# MAIN LOGIC
# -----------------------------
if cost_file and sales_file:

    try:
        cost_df = pd.read_excel(cost_file)
        sales_df = pd.read_excel(sales_file)
    except Exception as e:
        st.error(f"Error reading files: {e}")
        st.stop()

    # Clean column names
    cost_df.columns = cost_df.columns.str.strip()
    sales_df.columns = sales_df.columns.str.strip()

    # Required columns check
    cost_required = ["Product Name", "Purchase Price", "Purchase Deal"]
    sales_required = ["Party Name", "Product Name", "Quantity", "Free Qty", "Selling Price"]

    for col in cost_required:
        if col not in cost_df.columns:
            st.error(f"Missing column in COST FILE: {col}")
            st.stop()

    for col in sales_required:
        if col not in sales_df.columns:
            st.error(f"Missing column in SALES FILE: {col}")
            st.stop()

    # Clean product names
    cost_df["Product Name"] = cost_df["Product Name"].apply(clean_product_name)
    sales_df["Product Name"] = sales_df["Product Name"].apply(clean_product_name)

    # Merge
    df = sales_df.merge(cost_df, on="Product Name", how="left", indicator=True)

    # Missing products
    missing = df[df["_merge"] == "left_only"]
    if not missing.empty:
        st.warning("⚠️ These products are missing in COST FILE:")
        st.dataframe(missing[["Product Name"]].drop_duplicates())

    df = df[df["_merge"] == "both"].copy()

    if df.empty:
        st.error("No matching products found. Check product names.")
        st.stop()

    # Parse deal
    df[["p_qty", "p_free"]] = df["Purchase Deal"].apply(lambda x: pd.Series(parse_deal(x)))

    # Convert numeric
    numeric_cols = ["Quantity", "Free Qty", "Selling Price", "Purchase Price"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # -----------------------------
    # CALCULATIONS
    # -----------------------------
    df["EC"] = df.apply(lambda x: calculate_ec(x["Purchase Price"], x["p_qty"], x["p_free"]), axis=1)

    df["ESP"] = df.apply(lambda x: calculate_esp(x["Selling Price"], x["Quantity"], x["Free Qty"]), axis=1)

    df["Required SP"] = df["EC"] * 1.10

    df["Adjustment per unit"] = (df["Required SP"] - df["ESP"]).clip(lower=0)

    df["Total Adjustment"] = df["Adjustment per unit"] * df["Quantity"]

    # Round values
    df["EC"] = df["EC"].round(2)
    df["ESP"] = df["ESP"].round(2)
    df["Required SP"] = df["Required SP"].round(2)
    df["Adjustment per unit"] = df["Adjustment per unit"].round(2)
    df["Total Adjustment"] = df["Total Adjustment"].round(2)

    # -----------------------------
    # DISPLAY TABLE
    # -----------------------------
    st.subheader("📊 Detailed Adjustment Table")

    display_cols = [
        "Product Name",
        "Party Name",
        "EC",
        "ESP",
        "Required SP",
        "Adjustment per unit",
        "Total Adjustment"
    ]

    def highlight(row):
        if row["Total Adjustment"] > 0:
            return ["background-color: #ffcccc"] * len(row)
        return [""] * len(row)

    st.dataframe(
        df[display_cols].style.apply(highlight, axis=1),
        use_container_width=True
    )

    # -----------------------------
    # SUMMARY
    # -----------------------------
    st.subheader("📈 Summary")

    total_adj = df["Total Adjustment"].sum()
    st.metric("💰 Total Adjustment", f"₹ {total_adj:,.2f}")

    col1, col2 = st.columns(2)

    with col1:
        st.write("### Party-wise Adjustment")
        party_summary = df.groupby("Party Name")["Total Adjustment"].sum().reset_index()
        st.dataframe(party_summary, use_container_width=True)

    with col2:
        st.write("### Product-wise Adjustment")
        product_summary = df.groupby("Product Name")["Total Adjustment"].sum().reset_index()
        st.dataframe(product_summary, use_container_width=True)

else:
    st.info("👈 Upload both COST and SALES files from sidebar to start")
