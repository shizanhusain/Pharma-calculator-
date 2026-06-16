import streamlit as st
import pandas as pd

st.title("💊 Pharma Adjustment Calculator")

tax = st.number_input("Tax %", value=5.0)
margin = st.number_input("Margin %", value=10.0)

bill_file = st.file_uploader("Upload Sales Excel", type=["xlsx"])
cost_file = st.file_uploader("Upload Cost Excel", type=["xlsx"])

if bill_file and cost_file:
    
    # Load files
    bill_df = pd.read_excel(bill_file)
    cost_df = pd.read_excel(cost_file)

    # 🔍 Show columns (VERY IMPORTANT)
    st.write("📄 Bill Columns:", bill_df.columns)
    st.write("📄 Cost Columns:", cost_df.columns)

    # 🔧 AUTO FIX COLUMN NAMES
    def find_column(df, possible_names):
        for col in df.columns:
            for name in possible_names:
                if name.lower() in col.lower():
                    return col
        return None

    bill_product_col = find_column(bill_df, ["product", "item", "description"])
    cost_product_col = find_column(cost_df, ["product", "item", "description"])
    cost_price_col = find_column(cost_df, ["cost", "price", "rate"])

    if not bill_product_col or not cost_product_col or not cost_price_col:
        st.error("❌ Could not detect required columns automatically")
        st.stop()

    # ✅ Rename columns safely
    bill_df = bill_df.rename(columns={bill_product_col: "Product"})
    cost_df = cost_df.rename(columns={
        cost_product_col: "Product",
        cost_price_col: "Cost Price"
    })

    # Clean text
    bill_df["Product"] = bill_df["Product"].astype(str).str.strip().str.lower()
    cost_df["Product"] = cost_df["Product"].astype(str).str.strip().str.lower()

    # Merge
    df = pd.merge(bill_df, cost_df, on="Product", how="left")

    st.subheader("📊 Merged Data")
    st.dataframe(df)

    # Check missing matches
    missing = df[df["Cost Price"].isna()]
    if not missing.empty:
        st.warning("⚠️ Some products not matched")
        st.dataframe(missing)

    # Calculate
    df["Final Price"] = df["Cost Price"] * (1 + tax/100) * (1 + margin/100)

    st.subheader("✅ Final Output")
    st.dataframe(df)
