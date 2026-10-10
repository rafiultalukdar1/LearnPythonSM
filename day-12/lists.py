list = [1, 2, 3, 4, 5]

list[0] = 'start'

list.append('end')

print(list)

import sys

print(sys.getsizeof(list))


# input list from user
l3 = []

n = int(input('Enter your total index: '))

for i in range(n):
    new = input()
    l3.append(new)

print(l3)  # final