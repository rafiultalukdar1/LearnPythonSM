print('Python Array')


# Python Array

import array

arr = array.array('i', [10, 20, 30, 40])

print(arr)
print(type(arr))


# Append()
print('Append()')

arr = array.array('i', [10, 20, 30])
arr.append(40)
print(arr)


# Insert()
print('Insert()')

arr = array.array('i', [10, 20, 30])
arr.insert(1, 15)
print(arr)


# Remove()
print('Remove()')

arr = array.array('i', [10, 20, 30, 40])
arr.remove(20)
print(arr)


# Indexing
print('Indexing')

arr = array.array('i', [10, 20, 30, 40])
print(arr[0])
print(arr[-1])


# Array Loop
print('Array Loop')

arr = array.array('i', [10, 20, 30, 40])

for num in arr:
    print(num)


# Sum and Average
print('Sum and Average')

marks = array.array('i', [70, 80, 90, 60, 100])

total = sum(marks)
average = total / len(marks)

print('Total:', total)
print('Average:', average)


# Reverse()
print('Reverse()')

arr = array.array('i', [10, 20, 30, 40])
arr.reverse()
print(arr)


# Index()
print('Index()')

arr = array.array('i', [10, 20, 30, 40])
print(arr.index(30))


# Count()
print('Count()')

arr = array.array('i', [10, 20, 10, 30, 10])
print(arr.count(10))


# Extend()
print('Extend()')

arr = array.array('i', [10, 20, 30])
arr.extend([40, 50])
print(arr)


# Pop()
print('Pop()')

arr = array.array('i', [10, 20, 30, 40])
removed = arr.pop()

print('Removed:', removed)
print('Final:', arr)


# Length
print('Length')

arr = array.array('i', [10, 20, 30, 40])
print(len(arr))
