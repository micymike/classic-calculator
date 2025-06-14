from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid
import pandas as pd
import numpy as np
import io

# Initialize FastAPI
app = FastAPI(title="Fintech App - Salary Advance and Loan API")

# Define input model for salary advance and loan request
class AdvanceRequest(BaseModel):
    gross_salary: float
    pay_frequency: str
    advance_amount: float
    loan_amount: Optional[float] = None
    interest_rate: Optional[float] = None
    loan_term: Optional[int] = None
    include_amortization: Optional[bool] = False

# Define response model for advance and loan calculation
class AdvanceResponse(BaseModel):
    eligible: bool  # Salary-based eligibility
    advance_approved: bool  # Whether the specific advance request is approved
    max_advance: float
    approved_amount: float
    fee: float
    total_repayable: Optional[float] = None
    amortization_schedule: Optional[list] = None
    message: str
    loan_id: Optional[str] = None

# In-memory store for loans
loans_db = {}

# Helper function to convert annual salary to monthly
def convert_to_monthly_salary(gross_salary: float, pay_frequency: str) -> float:
    if pay_frequency == "Weekly":
        return gross_salary * 52 / 12
    elif pay_frequency == "Bi-Weekly":
        return gross_salary * 26 / 12
    elif pay_frequency == "Monthly":
        return gross_salary
    elif pay_frequency == "Annually":
        return gross_salary / 12
    else:
        raise ValueError("Invalid pay_frequency")

# Helper function to calculate compound interest using Pandas
def calculate_compound_interest(principal: float, rate: float, term_months: int) -> float:
    n = 12  # Monthly compounding
    t = term_months / 12  # Convert months to years
    rate = rate / 100  # Convert percentage to decimal
    df = pd.DataFrame({
        "principal": [principal],
        "rate_per_period": [rate / n],
        "periods": [n * t]
    })
    df["total_repayable"] = df["principal"] * (1 + df["rate_per_period"]) ** df["periods"]
    return round(df["total_repayable"].iloc[0], 2)

# Helper function to generate amortization schedule using Pandas
def generate_amortization_schedule(principal: float, rate: float, term_months: int) -> pd.DataFrame:
    monthly_rate = rate / 100 / 12
    if monthly_rate == 0:
        monthly_payment = principal / term_months
    else:
        monthly_payment = principal * (monthly_rate * (1 + monthly_rate) ** term_months) / ((1 + monthly_rate) ** term_months - 1)
    monthly_payment = round(monthly_payment, 2)

    # Initialize DataFrame with initial balance
    df = pd.DataFrame({
        "Month": range(1, term_months + 1),
        "Balance": [principal] + [0] * (term_months - 1),
        "Payment": [0] * term_months
    })

    balance = principal
    for i in range(term_months):
        if i > 0:
            df.at[i, "Balance"] = balance
        interest = balance * monthly_rate
        principal_payment = min(monthly_payment - interest, balance)
        balance -= principal_payment
        if i == term_months - 1 and balance > 0:  # Adjust final payment to clear balance
            df.at[i, "Payment"] = principal_payment + balance
            df.at[i, "Interest"] = interest
            df.at[i, "Principal"] = principal_payment + balance - interest
            df.at[i, "Balance"] = 0
        else:
            df.at[i, "Payment"] = monthly_payment
            df.at[i, "Interest"] = interest
            df.at[i, "Principal"] = principal_payment
            df.at[i, "Balance"] = max(0, balance)  # Ensure no negative balance
        balance = df.at[i, "Balance"]

    return df[["Month", "Payment", "Principal", "Interest", "Balance"]].round(2)

# Endpoint to calculate salary advance and loan
@app.post("/calculate_advance")
async def calculate_advance(request: AdvanceRequest, export_csv: Optional[bool] = False):
    try:
        # Step 1: Determine eligibility (based on salary threshold)
        monthly_salary = convert_to_monthly_salary(request.gross_salary, request.pay_frequency)
        min_salary_threshold = 1000
        eligible = monthly_salary >= min_salary_threshold

        if not eligible:
            return {
                "eligible": False,
                "advance_approved": False,
                "max_advance": 0.0,
                "approved_amount": 0.0,
                "fee": 0.0,
                "message": "Ineligible: Monthly salary is below the minimum threshold of $1000."
            }

        # Step 2: Calculate maximum advance (50% of monthly salary)
        max_advance = monthly_salary * 0.5

        # Step 3: Check advance approval
        advance_approved = request.advance_amount <= max_advance
        approved_amount = request.advance_amount if advance_approved else 0.0
        fee = max(10.0, min(50.0, request.advance_amount * 0.05)) if advance_approved else 0.0

        # Step 4: Calculate loan repayment (if provided and advance is approved)
        total_repayable = None
        amortization_schedule = None
        if advance_approved and request.loan_amount and request.interest_rate and request.loan_term:
            total_repayable = calculate_compound_interest(request.loan_amount, request.interest_rate, request.loan_term)
            if request.include_amortization or export_csv:
                amortization_df = generate_amortization_schedule(request.loan_amount, request.interest_rate, request.loan_term)
                amortization_schedule = amortization_df.to_dict("records")
                if export_csv:
                    csv_buffer = io.StringIO()
                    amortization_df.to_csv(csv_buffer, index=False)
                    return {"csv_data": csv_buffer.getvalue(), "filename": "amortization_schedule.csv"}

        # Step 5: Record the loan (if approved)
        loan_id = str(uuid.uuid4()) if advance_approved else None
        if advance_approved:
            loan_record = {
                "loan_id": loan_id,
                "advance_amount": request.advance_amount,
                "fee": fee,
                "timestamp": datetime.now().isoformat(),
                "gross_salary": request.gross_salary,
                "pay_frequency": request.pay_frequency,
                "loan_amount": request.loan_amount,
                "interest_rate": request.interest_rate,
                "loan_term": request.loan_term,
                "total_repayable": total_repayable,
                "amortization_schedule": amortization_schedule
            }
            loans_db[loan_id] = loan_record

        # Step 6: Return response
        message = f"Advance approved! Amount: ${request.advance_amount:,.2f}, Fee: ${fee:,.2f}" if advance_approved else f"Requested advance (${request.advance_amount:,.2f}) exceeds maximum allowed (${max_advance:,.2f})."
        if advance_approved and total_repayable:
            message += f". Loan repayable: ${total_repayable:,.2f} over {request.loan_term} months."

        return {
            "eligible": eligible,
            "advance_approved": advance_approved,
            "max_advance": max_advance,
            "approved_amount": approved_amount,
            "fee": fee,
            "total_repayable": total_repayable,
            "amortization_schedule": amortization_schedule,
            "message": message,
            "loan_id": loan_id
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")

  # Add health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# Endpoint to retrieve loan details
@app.get("/loan/{loan_id}")
async def get_loan(loan_id: str):
    if loan_id not in loans_db:
        raise HTTPException(status_code=404, detail="Loan not found")
    return loans_db[loan_id]