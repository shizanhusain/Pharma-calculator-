import streamlit as st
import pandas as pd

st.title("Pharma Margin Calculator")

cost_file = st.file_uploader("Upload Product Cost File", type=["xlsx"])
bill_file = st.file_uploader("Upload Bill File", type=["xlsx","csv"])

tax = st.number_input("Tax %", value=5.0)/100
margin = st.number_input("Margin %", value=10.0)/100

if cost_file and bill_file:

    cost_df = pd.read_excel(cost_file)

    if bill_file.name.endswith(".csv"):
        bill_df = pd.read_csv(bill_file)
    else:
        bill_df = pd.read_excel(bill_file)

    data = bill_df.merge(cost_df, on="Product")

    data["Cost After Tax"] = data["Cost Price"]*(1+tax)
    data["Min Selling"] = data["Cost After Tax"]*(1+margin)

    data["Expected"] = data["Min Selling"]*data["Quantity"]
    data["Actual"] = data["Selling Price"]*data["Quantity"]

    data["Loss"] = data["Expected"] - data["Actual"]
    data["Loss"] = data["Loss"].apply(lambda x: x if x>0 else 0)

    data["Adjustment"] = data["Loss"]/data["Cost Price"]

    st.dataframe(data)

    st.success(f"Total Loss: ₹{data['Loss'].sum():.2f}")
    st.success(f"Total Adjustment Units: {data['Adjustment'].sum():.2f}")