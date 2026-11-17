# Smart Bank Transaction System

def check_transaction(balance, amount):
    if amount <= 0:
        return False, "Invalid Transaction Amount"

    if amount > balance:
        return False, "Insufficient Balance"

    if amount > 50000:
        return False, "Transaction Limit Exceeded"

    return True, "Transaction Approved"


def calculate_fee(amount):
    if amount >= 10000:
        return amount * 0.02

    return amount * 0.01


def process_transaction(account, balance, amount):

    # Transaction Validation
    approved, message = check_transaction(balance, amount)

    if not approved:
        return {
            "status": "Rejected",
            "message": message
        }

    # Calculate Transaction Fee
    fee = calculate_fee(amount)

    # Calculate Remaining Balance
    remaining_balance = balance - amount - fee

    # Return Transaction Details
    return {
        "account": account,
        "status": "Successful",
        "transaction_amount": amount,
        "transaction_fee": fee,
        "remaining_balance": remaining_balance
    }


# Transaction
result = process_transaction(
    account="AC-1025",
    balance=75000,
    amount=20000
)

print(result)