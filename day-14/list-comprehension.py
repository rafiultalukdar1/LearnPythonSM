print('List comprehension')

squre = [x**2 for x in range(10)]

print(squre)


event = [x**2 for x in range(10) if x % 2 == 0]

print(event)


data = 'I love data scienc'

print([x for x in data if x != ' '])


matrix = [[j for j in range(5)] for i in range(3)]

print(matrix)


words = ['data', 'scienc', 'pyton', 'comprehension', 'list']

lengths = [len(word) for word in words]

print(lengths)