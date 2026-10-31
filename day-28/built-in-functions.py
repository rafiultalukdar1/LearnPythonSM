
# Commonly Used Built-in Functions in Python


# 1. print()
print('Print Function')

print('Hello Python')


# 2. type()
print('Type Function')

name = 'Rafiul'

age = 25

print(type(name))

print(type(age))


# 3. len()
print('Length Function')

data = ['Python', 'Java', 'C++']

print(len(data))


# 4. input()
print('Input Function')

name = input('Enter your name: ')

print('Welcome:', name)


# 5. int()
print('Integer Function')

num = int('100')

print(num)

print(type(num))


# 6. float()
print('Float Function')

num = float('25.50')

print(num)

print(type(num))


# 7. str()
print('String Function')

num = 100

result = str(num)

print(result)

print(type(result))


# 8. bool()
print('Boolean Function')

print(bool(1))

print(bool(0))

print(bool('Python'))


# 9. sum()
print('Sum Function')

numbers = [10, 20, 30, 40]

print(sum(numbers))


# 10. max()
print('Maximum Function')

numbers = [10, 50, 30, 90, 20]

print(max(numbers))


# 11. min()
print('Minimum Function')

numbers = [10, 50, 30, 90, 20]

print(min(numbers))


# 12. sorted()
print('Sorted Function')

numbers = [50, 20, 40, 10, 30]

print(sorted(numbers))


# 13. range()
print('Range Function')

for i in range(1, 6):
    print(i)


# 14. abs()
print('Absolute Function')

num = -50

print(abs(num))


# 15. round()
print('Round Function')

num = 25.6789

print(round(num, 2))


# 16. pow()
print('Power Function')

print(pow(2, 3))


# 17. enumerate()
print('Enumerate Function')

subjects = ['Python', 'Java', 'C++']

for index, subject in enumerate(subjects):
    print(index, subject)


# 18. zip()
print('Zip Function')

names = ['Rafiul', 'Rahim', 'Karim']

marks = [85, 90, 78]

print(list(zip(names, marks)))


# 19. reversed()
print('Reversed Function')

numbers = [10, 20, 30, 40]

print(list(reversed(numbers)))


# 20. any() and all()
print('Any and All Functions')

numbers = [True, False, True]

print(any(numbers))

print(all(numbers))


# 21. map()
print('Map Function')

numbers = [1, 2, 3, 4]

result = list(map(lambda x: x * 2, numbers))

print(result)


# 22. filter()
print('Filter Function')

numbers = [10, 15, 20, 25, 30]

result = list(filter(lambda x: x > 20, numbers))

print(result)


# 23. isinstance()
print('Isinstance Function')

age = 25

print(isinstance(age, int))

print(isinstance(age, str))


# 24. divmod()
print('Divmod Function')

print(divmod(10, 3))