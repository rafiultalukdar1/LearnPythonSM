# Numeric datatype

x = 10 # int
y = 5.5 # float
z = 7 + 5j # 7 is real number, 5j is imaginary

print(type(x))
print(type(y))
print(type(z))
print(isinstance(z, complex))
print(isinstance(10, float))

# int to float
n = float(x)
print(n)

# complex
m = complex(input('Enter your complex number : '))

print(m)

# Boolean
manik = True
ratan = False

print('Manik :', manik)
print('Ratan :', ratan)