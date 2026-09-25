# -----Data Type-----

# integer data type
x = 7

# sring data type
a = "Abdullah"

# float data type
y = 3.20

# boolean data type
z = True

# complex data type
ab = 2 + 5j

print(type(x))
print(type(a))
print(type(y))
print(type(z))
print(type(ab))


# Input Function

manik = input()
print(type(manik))

first_number = int(input('Enter your first number: '))
second_number = int(input('Enter your second number: '))
print('Total number:', first_number + second_number)

# Batter hoy float use korle

third_number = float(input('Enter your third number: '))
fourth_number = float(input('Enter your fourth number: '))
print('Total number:', third_number + fourth_number)


data = 'Day-3.0 - 60 Days of Python'
print(type(data))
print(len(data))
import sys
print(sys.getsizeof(data))
sub_data = 'Python'
print(data.count(sub_data))