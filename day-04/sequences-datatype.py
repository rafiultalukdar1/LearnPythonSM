# List

list = [1, 2, 3, True, [1, 2], 'data', (2, 4, 6)]
print(list)
print(list[4][1])
print(type(list))

# Tuples
tuple = (1, 2, 3, 'tuple')
print(type(tuple))
print(tuple[0])
print(tuple[0:4]) # colon means to 

# Range
# r = range(10)
# print(r)

# for i in r:
#     print(i)

# ra = range(1, 100, 20)

# for ii in ra:
#     print(ii)

# Array

import array as ar

a = ar.array('i', (1, 2, 3))

print(a)