print('Continue Statement in Python & Differences')

# Continue Statement in Python

# Example 1: Basic Continue
print('Basic Continue')

for i in range(1, 6):
    if i == 3:
        continue
    print(i)


# Example 2: Skip Even Numbers
print('Skip Even Numbers')

for i in range(1, 11):
    if i % 2 == 0:
        continue
    print(i)


# Example 3: Skip Odd Numbers
print('Skip Odd Numbers')

for i in range(1, 11):
    if i % 2 != 0:
        continue
    print(i)


# Example 4: Continue with List
print('Continue with List')

numbers = [10, 20, 30, 40, 50]

for num in numbers:
    if num == 30:
        continue
    print(num)


# Example 5: Skip Negative Numbers
print('Skip Negative Numbers')

numbers = [10, -5, 20, -8, 30, 40]

for num in numbers:
    if num < 0:
        continue
    print(num)


# Example 6: Continue with While Loop
print('Continue with While Loop')

i = 0

while i < 6:
    i += 1

    if i == 3:
        continue

    print(i)


# Example 7: Skip Specific Characters
print('Skip Specific Characters')

name = 'programming'

for char in name:
    if char == 'm':
        continue
    print(char, end=' ')

print()


# Example 8: Student Marks
print('Student Marks')

marks = [80, 0, 75, 0, 90, 85]

for mark in marks:
    if mark == 0:
        continue
    print('Valid Mark:', mark)
