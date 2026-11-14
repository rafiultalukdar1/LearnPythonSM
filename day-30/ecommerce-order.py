# E-commerce Order Management System

def check_stock(stock, quantity):
    if quantity > stock:
        return False, "Insufficient Stock"

    return True, "Stock Available"


def calculate_discount(total):
    if total >= 5000:
        return total * 0.15
    elif total >= 3000:
        return total * 0.10
    elif total >= 1000:
        return total * 0.05

    return 0


def process_order(product, price, quantity, stock, payment):
    # Check Stock
    available, message = check_stock(stock, quantity)

    if not available:
        return {"status": "Failed", "message": message}

    # Validate Payment
    if payment not in ["Cash", "Card", "Bkash"]:
        return {"status": "Failed", "message": "Invalid Payment Method"}

    # Calculate Total
    subtotal = price * quantity
    discount = calculate_discount(subtotal)
    final_amount = subtotal - discount

    # Generate Invoice
    return {
        "status": "Success",
        "product": product,
        "quantity": quantity,
        "subtotal": subtotal,
        "discount": discount,
        "final_amount": final_amount,
        "payment": payment
    }


# Customer Order
order = process_order(
    product="Laptop",
    price=55000,
    quantity=2,
    stock=5,
    payment="Bkash"
)

print(order)