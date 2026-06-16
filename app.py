import streamlit as st
import pandas as pd
import io

st.title("💊 Pharma Margin + Claim System")

# ----------- DEAL PARSER -----------
def parse_deal(deal):
    try:
        if pd.isna(deal) or deal == "":
            return 0, 0
        buy, free = deal.split("+")
        return float(buy), float(free)
    except:
        return 0, 0

# ----------- FILE UPLOADS -----------
cost_file = st.file_uploader("Upload Product Cost File", type=["xlsx"])
bill_file = st.file_uploader("Upload Bill File", type=["xlsx","csv"])

if cost_file and bill_file:

    # ----------- LOAD COST FILE -----------
    cost_df = pd.read_excel(cost_file)
    cost_df["Product"] = cost_df["Product"].str.strip().str.lower()

    # Ensure Deal column exists
    cost_df["Deal"] = cost_df.get("Deal", "")

    # Parse cost deal
    cost_df[["Buy_qty_cost", "Free_qty_cost"]] = cost_df["Deal"].apply(
        lambda x: pd.Series(parse_deal(x))
    )

    # Effective Cost
    cost_df["Effective Cost"] = cost_df.apply(
        lambda row: row["Cost Price"] / (1 + row["Free_qty_cost"] / row["Buy_qty_cost"])
        if row["Buy_qty_cost"] > 0 else row["Cost Price"],
        axis=1
    )

    # ----------- LOAD BILL FILE -----------
    if bill_file.name.endswith(".csv"):
        bill_df = pd.read_csv(bill_file)
    else:
        bill_df = pd.read_excel(bill_file)

    bill_df["Product"] = bill_df["Product"].str.strip().str.lower()

    # Ensure columns exist
    bill_df["Deal"] = bill_df.get("Deal", "")
    bill_df["Type"] = bill_df.get("Type", "NET")

    # Parse selling deal
    bill_df[["Buy_qty_sell", "Free_qty_sell"]] = bill_df["Deal"].apply(
        lambda x: pd.Series(parse_deal(x))
    )

    # ----------- MERGE -----------
    data = bill_df.merge(cost_df, on="Product", how="left")

    # Fill missing cost
    data["Effective Cost"] = data["Effective Cost"].fillna(0)

    # ----------- EFFECTIVE SELLING -----------
    def calculate_effective_selling(row):
        if row["Type"] == "DEAL" and row["Buy_qty_sell"] > 0:
            return row["Selling Price"] / (1 + row["Free_qty_sell"] / row["Buy_qty_sell"])
        else:
            return row["Selling Price"]

    data["Effective Selling"] = data.apply(calculate_effective_selling, axis=1)

    # ----------- LOSS CALCULATION -----------
    data["Loss per unit"] = data["Effective Cost"] - data["Effective Selling"]
    data["Loss per unit"] = data["Loss per unit"].apply(lambda x: x if x > 0 else 0)

    data["Total Loss"] = data["Loss per unit"] * data["Quantity"]

    # ----------- ADJUSTMENT -----------
    data["Adjustment Units"] = data.apply(
        lambda row: row["Total Loss"] / row["Effective Cost"]
        if row["Effective Cost"] > 0 else 0,
        axis=1
    )

    # ----------- DETAILED TABLE -----------
    st.subheader("📋 Detailed Loss Report")

    detailed = data[[
        "Party",
        "Product",
        "Effective Cost",
        "Effective Selling",
        "Selling Price",
        "Quantity",
        "Total Loss",
        "Adjustment Units"
    ]]

    st.dataframe(detailed)

    # ----------- PARTY SUMMARY -----------
    st.subheader("📊 Party-wise Summary")

    party_summary = data.groupby("Party")[["Total Loss","Adjustment Units"]].sum().reset_index()
    st.dataframe(party_summary)

    # ----------- COMPANY CLAIM -----------
    st.subheader("🏢 Company Claim Sheet")

    company_claim = data.groupby("Product")[["Total Loss","Adjustment Units"]].sum().reset_index()
    st.dataframe(company_claim)

    # ----------- TOTALS -----------
    st.success(f"💰 Total Loss: ₹{data['Total Loss'].sum():.2f}")
    st.success(f"📦 Total Adjustment Units: {data['Adjustment Units'].sum():.2f}")

    # ----------- DOWNLOAD BUTTON -----------
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        detailed.to_excel(writer, index=False, sheet_name='Detailed')
        party_summary.to_excel(writer, index=False, sheet_name='Party Summary')
        company_claim.to_excel(writer, index=False, sheet_name='Company Claim')

    st.download_button(
        label="📥 Download Report",
        data=output.getvalue(),
        file_name="pharma_claim_report.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
