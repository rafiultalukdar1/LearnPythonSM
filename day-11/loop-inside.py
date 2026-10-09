for i in range(3):
    for j in range(2):
        print(i, j)

row = 6

# outer loop
for x in range(1, row+1):
    # inner loop
    for y in range(x):
        print('#', end=' ')
    print('')

# Another Example 

num = [1, 2, 3, 4, 5, 6]

# outer loop
for ele in num:
    # inner loop
    index = 0
    while index<len(num):
        print(num[index], end=' ')
        index = index+1
    print('')