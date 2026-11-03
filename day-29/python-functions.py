# 1. Basic Function
def greet():
    print("Hello, Python!")

greet()


# 2. Function with Parameter
def greet_user(name):
    print(f"Hello, {name}!")

greet_user("Rafiul")


# 3. Function with Multiple Parameters
def add(a, b):
    print("Sum:", a + b)

add(10, 20)


# 4. Function with Return
def multiply(a, b):
    return a * b

result = multiply(5, 4)
print("Result:", result)


# 5. Default Parameter
def student(name, age=20):
    print(f"Name: {name}, Age: {age}")

student("Rafiul")
student("Rahim", 25)


# 6. Keyword Arguments
def information(name, age):
    print(f"Name: {name}")
    print(f"Age: {age}")

information(age=25, name="Rafiul")


# 7. Arbitrary Arguments (*args)
def total(*numbers):
    print("Total:", sum(numbers))

total(10, 20, 30, 40)


# 8. Arbitrary Keyword Arguments (**kwargs)
def profile(**details):
    print(details)

profile(name="Rafiul", age=25, country="Bangladesh")


# 9. Function with Condition
def check_even_odd(number):
    if number % 2 == 0:
        print("Even Number")
    else:
        print("Odd Number")

check_even_odd(7)


# 10. Function with Loop
def multiplication_table(number):
    for i in range(1, 11):
        print(f"{number} x {i} = {number * i}")

multiplication_table(5)


# 11. Recursive Function
def factorial(number):
    if number == 1 or number == 0:
        return 1
    return number * factorial(number - 1)

print("Factorial:", factorial(5))


# 12. Lambda Function
square = lambda number: number ** 2

print("Square:", square(5))


# 13. Function Returning Multiple Values
def calculate(a, b):
    return a + b, a - b, a * b

sum_result, sub_result, mul_result = calculate(20, 10)

print("Sum:", sum_result)
print("Subtraction:", sub_result)
print("Multiplication:", mul_result)


# 14. Function with List
def find_max(numbers):
    return max(numbers)

my_numbers = [10, 25, 5, 40, 15]

print("Maximum:", find_max(my_numbers))


# 15. Function Calling Another Function
def add(a, b):
    return a + b

def calculate_total():
    result = add(10, 20)
    print("Total:", result)

calculate_total()