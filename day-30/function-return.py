# 1. Basic Return
def add(a, b):
    return a + b

result = add(10, 20)
print(result)


# 2. Return vs Print
def show():
    print("Hello Python")

def get():
    return "Hello Python"

show()
result = get()
print(result)


# 3. Return a String
def greeting(name):
    return f"Hello, {name}!"

print(greeting("Rafiul"))


# 4. Return a Boolean Value
def is_even(number):
    return number % 2 == 0

print(is_even(10))
print(is_even(7))


# 5. Return with If-Else
def check_age(age):
    if age >= 18:
        return "Adult"
    else:
        return "Minor"

print(check_age(25))
print(check_age(15))


# 6. Return Multiple Values
def calculate(a, b):
    return a + b, a - b, a * b

sum_result, sub_result, mul_result = calculate(20, 10)

print(sum_result)
print(sub_result)
print(mul_result)


# 7. Return a List
def get_numbers():
    return [10, 20, 30, 40, 50]

numbers = get_numbers()
print(numbers)


# 8. Return a Dictionary
def get_student():
    return {
        "name": "Rafiul",
        "age": 25,
        "course": "Python"
    }

student = get_student()
print(student)


# 9. Return Stops Function Execution
def check_number(number):
    if number < 0:
        return "Negative Number"

    print("Checking completed")
    return "Positive Number"

print(check_number(-5))
print(check_number(10))


# 10. Return Inside a Loop
def find_number(numbers, target):
    for number in numbers:
        if number == target:
            return "Found"

    return "Not Found"

print(find_number([10, 20, 30, 40], 30))
print(find_number([10, 20, 30, 40], 50))


# 11. Return from Another Function
def square(number):
    return number ** 2

def cube(number):
    return square(number) * number

print(cube(3))


# 12. Return None
def do_nothing():
    return

result = do_nothing()
print(result)


# 13. Return Without Explicit Value
def test():
    print("Hello")

result = test()
print(result)


# 14. Return with Calculation
def calculate_average(numbers):
    return sum(numbers) / len(numbers)

marks = [80, 90, 75, 85]
print("Average:", calculate_average(marks))


# 15. Return from Recursive Function
def factorial(number):
    if number == 0 or number == 1:
        return 1

    return number * factorial(number - 1)

print("Factorial:", factorial(5))