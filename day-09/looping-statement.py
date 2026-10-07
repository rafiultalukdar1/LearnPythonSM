py = 'python'

for p in py:
    print(p)

# Range Function

for p in range(len(py)):
    print('Range :',py[p])

# Example

data = 'I love data scince so much'

data = data.split()

for i in range(len(data)):
    print(data[i], i)


# Example 

n = [2, 3, 4, 55, 60, 77, 100]

total = 0

for x in n:
    total = total + x
    print(total, x)

# Example 

for i in range(100, 0, -2):
    print(i)