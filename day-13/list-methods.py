# List 

list1 = ['ai', 'ds', 'se', 880, 7, True, [7, 10], (4, 9)]

print(list1[-1])

# Copy()
print('Copy()')

list2 = list1.copy()

list2[0] = 'data'

print(list2)


# Append()
print('Append()')

list2 = list1.copy()

list2.append('python')

print(list2)


# Extend()
print('Extend()')

list2 = list1.copy()

list2.extend(['python', 'java'])

print(list2)


# Insert()
print('Insert()')

list2 = list1.copy()

list2.insert(1, 'python')

print(list2)


# Index()
print('Index()')

list2 = list1.copy()

print(list2.index('se'))


# Count()
print('Count()')

list2 = [10, 20, 10, 30, 10, 40]

print(list2.count(10))


# Sort()
print('Sort()')

list2 = [50, 10, 40, 20, 30]

list2.sort()

print(list2)


# Reverse()
print('Reverse()')

list2 = list1.copy()

list2.reverse()

print(list2)


# Remove()
print('Remove()')

list2 = list1.copy()

list2.remove('ds')

print(list2)


# Pop()
print('Pop()')

list2 = list1.copy()

removed = list2.pop(3)

print('Removed:', removed)

print('Final:', list2)


# Clear()
print('Clear()')

list2 = list1.copy()

list2.clear()

print(list2)