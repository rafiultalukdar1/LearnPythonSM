
# Python Set Methods

set1 = {10, 20, 30, 40}
set2 = {30, 40, 50, 60}


# 1. Add()
print('Add()')

s = set1.copy()
s.add(70)
print(s)


# 2. Update()
print('Update()')

s = set1.copy()
s.update([50, 60])
print(s)


# 3. Remove()
print('Remove()')

s = set1.copy()
s.remove(20)
print(s)


# 4. Discard()
print('Discard()')

s = set1.copy()
s.discard(100)
print(s)


# 5. Pop()
print('Pop()')

s = set1.copy()
removed = s.pop()
print('Removed:', removed)
print('Remaining:', s)


# 6. Clear()
print('Clear()')

s = set1.copy()
s.clear()
print(s)


# 7. Union()
print('Union()')

print(set1.union(set2))


# 8. Intersection()
print('Intersection()')

print(set1.intersection(set2))


# 9. Difference()
print('Difference()')

print(set1.difference(set2))


# 10. Symmetric Difference()
print('Symmetric Difference()')

print(set1.symmetric_difference(set2))


# 11. Intersection Update()
print('Intersection Update()')

s = set1.copy()
s.intersection_update(set2)
print(s)


# 12. Difference Update()
print('Difference Update()')

s = set1.copy()
s.difference_update(set2)
print(s)


# 13. Symmetric Difference Update()
print('Symmetric Difference Update()')

s = set1.copy()
s.symmetric_difference_update(set2)
print(s)


# 14. Is Disjoint()
print('Is Disjoint()')

print(set1.isdisjoint(set2))


# 15. Issubset()
print('Issubset()')

print({10, 20}.issubset(set1))


# 16. Issuperset()
print('Issuperset()')

print(set1.issuperset({10, 20}))
