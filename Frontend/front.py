import streamlit as st
import requests
import pandas as pd
import os
from io import StringIO
import time

def get_backend_response(url, payload, max_retries=10, timeout=5):
      for i in range(max_retries):
          try:
              response = requests.post(url, json=payload, timeout=timeout)
              response.raise_for_status()
              return response.json()
          except requests.RequestException:
              if i < max_retries - 1:
                  time.sleep(5)
              else:
                  raise


st.set_page_config(page_title="Fintech App - User Input", layout="centered")

# Get backend URL from environment variable
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000/calculate_advance")

st.title("💸 Fintech App: Advance and Loan Calculator")
st.write("Enter your financial details below to request an advance or calculate a loan.")

# Create a form
with st.form(key="user_input_form"):
    # Gross Salary and Pay Frequency
    st.header("Salary Details")
    gross_salary = st.number_input(
        "Gross Salary ($)",
        min_value=0.0,
        step=100.0,
        format="%.2f",
        help="Enter your gross salary (before taxes)."
    )
    pay_frequency = st.selectbox(
        "Pay Frequency",
        options=["Weekly", "Bi-Weekly", "Monthly", "Annually"],
        help="Select how often you are paid."
    )

    # Requested Advance Amount
    st.header("Advance Request")
    advance_amount = st.number_input(
        "Requested Advance Amount ($)",
        min_value=0.0,
        step=50.0,
        format="%.2f",
        help="Enter the amount you wish to request as an advance."
    )

    # Optional Loan Details
    st.header("Loan Details (Optional)")
    include_loan = st.checkbox("Include Loan Calculation", help="Check to enter loan details.")

    loan_amount = None
    interest_rate = None
    loan_term = None
    include_amortization = False

    if include_loan:
        loan_amount = st.number_input(
            "Loan Amount ($)",
            min_value=0.0,
            step=100.0,
            format="%.2f",
            help="Enter the loan amount."
        )
        interest_rate = st.number_input(
            "Interest Rate (%)",
            min_value=0.0,
            max_value=100.0,
            step=0.1,
            format="%.2f",
            help="Enter the annual interest rate for the loan."
        )
        loan_term = st.number_input(
            "Loan Term (Months)",
            min_value=1,
            step=1,
            help="Enter the loan term in months."
        )
        include_amortization = st.checkbox("Include Amortization Schedule", help="Check to view monthly payment breakdown.")

    # Submit button
    submit_button = st.form_submit_button(label="Submit")

# Handle form submission
if submit_button:
    # Prepare data for backend
    payload = {
        "gross_salary": gross_salary,
        "pay_frequency": pay_frequency,
        "advance_amount": advance_amount,
        "loan_amount": loan_amount,
        "interest_rate": interest_rate,
        "loan_term": loan_term,
        "include_amortization": include_amortization
    }

    try:
        # Send request to FastAPI backend
        response = requests.post(BACKEND_URL, json=payload)
        response.raise_for_status()
        result = response.json()

        # Display advance results
        st.subheader("Advance Calculation Result")
        st.write(f"**Eligibility**: {'Eligible' if result.get('eligible') else 'Not Eligible'}")
        st.write(f"**Advance Approved**: {'Yes' if result.get('advance_approved') else 'No'}")
        st.write(f"**Maximum Advance**: ${result.get('max_advance', 0):,.2f}")
        st.write(f"**Approved Amount**: ${result.get('approved_amount', 0):,.2f}")
        st.write(f"**Fee**: ${result.get('fee', 0):,.2f}")
        st.write(f"**Message**: {result.get('message', '')}")
        if result.get('loan_id'):
            st.write(f"**Loan ID**: {result.get('loan_id')}")

        # Display loan results if applicable
        if result.get('total_repayable'):
            st.subheader("Loan Repayment Details")
            st.write(f"**Total Repayable Amount**: ${result.get('total_repayable'):,.2f}")
            if result.get('amortization_schedule'):
                st.write("**Amortization Schedule**:")
                df = pd.DataFrame(result['amortization_schedule'])
                st.dataframe(df.style.format({
                    "Payment": "${:,.2f}",
                    "Principal": "${:,.2f}",
                    "Interest": "${:,.2f}",
                    "Balance": "${:,.2f}"
                }))

            # Add download button for CSV
                export_payload = payload.copy()
                export_payload["export_csv"] = True
                export_response = requests.post(BACKEND_URL, json=export_payload)
                export_response.raise_for_status()
                export_result = export_response.json()
                if "csv_data" in export_result:
                    csv_data = export_result["csv_data"]
                    csv_file = StringIO(csv_data)
                    st.download_button(
                        label="Download Amortization Schedule as CSV",
                        data=csv_file,
                        file_name=export_result["filename"],
                        mime_type="text/csv"
                )

    except requests.exceptions.RequestException as e:
        st.error(f"Error communicating with backend: {str(e)}")
