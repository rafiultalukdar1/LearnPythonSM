print('All About Dictionaries in Python')


# Python Dictionary

student = {
    'name': 'Rafiul',
    'age': 25,
    'roll': 66,
    'course': 'Python'
}

print(student)


# Access Items
print('Access Items')

print(student['name'])

print(student['course'])


# Update Value
print('Update Value')

student['age'] = 26

print(student)


# Add Item
print('Add Item')

student['city'] = 'Dhaka'
print(student)


# Remove Item
print('Remove Item')

student.pop('roll')

print(student)


# Get()
print('Get()')

print(student.get('name'))


# Keys()
print('Keys()')

print(student.keys())


# Values()
print('Values()')

print(student.values())


# Items()
print('Items()')

print(student.items())


# Loop
print('Dictionary Loop')

for key, value in student.items():
    print(key, ':', value)


# Length
print('Length')

print(len(student))