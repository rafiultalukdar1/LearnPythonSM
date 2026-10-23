print('Enumerate(): More on Unpacking in Python')

# 1. Basic Example
fruits = ["apple", "mango", "banana"]

for index, fruit in enumerate(fruits):
    print(index, fruit)


# 2. Start Index from 1
names = ["Rafi", "Sakib", "Rahim"]

for index, name in enumerate(names, start=1):
    print(index, name)


# 3. Enumerate with Numbers
numbers = [10, 20, 30, 40]

for index, number in enumerate(numbers):
    print(f"Index: {index}, Value: {number}")


# 4. Enumerate with If Condition
students = ["Rafi", "Sakib", "Nabil"]

for index, student in enumerate(students, start=1):
    if student == "Sakib":
        print(f"Found at position {index}")


# 5. Enumerate with Unpacking
data = [("Rafi", 25), ("Sakib", 22), ("Nabil", 24)]

for index, (name, age) in enumerate(data, start=1):
    print(index, name, age)