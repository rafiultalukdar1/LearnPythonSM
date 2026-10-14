print('Tuple in Python')

# Example 01
tup1 = ('ab', 12, 5, 5, 'manik', [1, 2, 3], 'python')

print(type(tup1))
print(tup1)

# Example 02
tup2 = ('Manik',) # 1 ta element hole obossoi , dite hobe noyto seta str hoye jabe 

print(type(tup2))

# Tuple to List
list1 = list(tup2)

list1.append('Ratan')

print(type(list1))
print(list1)

tup3 = tuple(list1)

print(tup3)

# Examole 05
tup4 = tup1 + tup3

print(tup4)

tup5 = tup1 * 2

print(tup5)

print(tup5.count(5))

# Membership
mem1 = 'Manik' in tup4

mem2 = 'Manik Miy' in tup4

print(mem1)
print(mem2)