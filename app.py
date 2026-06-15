import streamlit as st
import pandas as pd

st.title("💊 Pharma Margin Calculator (Party-wise Control)")

cost_file = st.file_uploader("Upload Product Cost File", type=["xlsx"])
bill_file = st.file_uploader("Upload Bill File", type=["xlsx","csv"])

tax = st.number_input("Tax %", value=5.0)/100
margin = st.number_input("Margin %", value=10.0)/100

if cost_file and bill_file:

    cost_df = pd.read_excel(cost_file)
    cost_df["Product"] = cost_df["Product"].str.strip().str.lower()

    if bill_file.name.endswith(".csv"):
        bill_df = pd.read_csv(bill_file)
    else:
        bill_df = pd.read_excel(bill_file)

    bill_df["Product"] = bill_df["Product"].str.strip().str.lower()

    data = bill_df.merge(cost_df, on="Product", how="left")

    # Minimum price calculation
    data["Cost After Tax"] = data["Cost Price"]*(1+tax)
    data["Min Selling"] = data["Cost After Tax"]*(1+margin)

    # Loss calculation
    data["Loss per unit"] = data["Min Selling"] - data["Selling Price"]
    data["Loss per unit"] = data["Loss per unit"].apply(lambda x: x if x>0 else 0)

    data["Total Loss"] = data["Loss per unit"] * data["Quantity"]

    # Party-wise summary
    party_summary = data.groupby("Party")["Total Loss"].sum().reset_index()

    st.subheader("📊 Party-wise Loss")
    st.dataframe(party_summary)

    st.success(f"💰 Total Loss: ₹{data['Total Loss'].sum():.2f}")
