# Assigning the veriable

x = 10
y = 5
z = 20

# Power
print(x ** y)

# Floor Division
print(z // 3)

# Normal Division
print(z / 3)

# Floor
import math
print(math.floor(z / 3))

# Ceil
print(math.ceil(z / 3))

# Python Identity Operator

x = [1, 2, 3]
y = x
z = [1, 2, 3]

print(x == y)
print(x is y)

print(x == z)
print(x is z)

print(x is not z)

# Membership Operator

numbers = [10, 20, 30, 40]

# in
print(20 in numbers)
print(50 in numbers)

# not in
print(20 not in numbers)
print(50 not in numbers)

# String
name = "Rafiul"

print("R" in name)
print("z" in name)

print("R" not in name)
print("z" not in name)

# Bitwise Operators

a = 10
b = 5

print(a & b)   # AND
print(a | b)   # OR
print(a ^ b)   # XOR
print(~a)      # NOT
print(a << 1)  # Left Shift
print(a >> 1)  # Right Shift