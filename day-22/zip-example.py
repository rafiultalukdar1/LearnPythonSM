# Zip() in Python

print('Zip() in Python')

# Example 1: Zip Two Lists
print('Zip Two Lists')

names = ['Rafiul', 'Rahim', 'Karim']

marks = [85, 90, 78]

result = zip(names, marks)

print(list(result))


# Example 2: Zip() with Loop
print('Zip with Loop')

names = ['Rafiul', 'Rahim', 'Karim']

marks = [85, 90, 78]

for name, mark in zip(names, marks):
    print(name, mark)


# Example 3: Zip Three Lists
print('Zip Three Lists')

names = ['Rafiul', 'Rahim', 'Karim']

marks = [85, 90, 78]

rolls = [101, 102, 103]

result = list(zip(names, marks, rolls))

print(result)


# Example 4: Different Length Lists
print('Different Length Lists')

a = [1, 2, 3, 4]

b = ['a', 'b']

print(list(zip(a, b)))


# Example 5: Unzip

print('Unzip')

data = [('Python', 90), ('Java', 85), ('C++', 80)]

subjects, marks = zip(*data)

print(subjects)

print(marks)


# Example 6: Zip into Dictionary

print('Zip into Dictionary')

keys = ['name', 'age', 'city']

values = ['Rafiul', 25, 'Dhaka']

student = dict(zip(keys, values))

print(student)