print('Frozen Set in Python')

print('Frozen Set')

set1 = {10, 20, 30, 40}

set2 = frozenset(set1)

print(set2)

print(type(set2))

print(20 in set2)

print(len(set2))


# Create Frozenset
numbers = frozenset([10, 20, 30, 40, 20])

print(numbers)

print(type(numbers))

print(len(numbers))


# Union()
set1 = frozenset({1, 2, 3})

set2 = frozenset({3, 4, 5})

result = set1.union(set2)

print(result)


# Intersection()
set1 = frozenset({10, 20, 30, 40})

set2 = frozenset({30, 40, 50, 60})

print(set1.intersection(set2))


# Membership Test
languages = frozenset({'Python', 'Java', 'JavaScript'})

print('Python' in languages)

print('C++' in languages)