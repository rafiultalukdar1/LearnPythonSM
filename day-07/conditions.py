# First Example

x = 20
y = 10

if x > y :
    print('X is big number')
else:
    print('Y is big number')

# Second Example

a = 10
b = 5

if a & b:
    print('a & b is True')
elif a | b:
    print('a | b is True')
    print('bitwise operator')
    if a != b:
        print('Not equal')

else:
    print('Out!')

# Third Example

num = float(input('Enter any number : '))

if num % 2 == 0:
    if num % 5 == 0:
        print(num, 'Divisible by 5 and 2')
    else:
        print('No 1')
else:
    print('No 2')


# Fourth Example

amount = 0

net_units = float(input('Enter your unit value : '))

if net_units <= 100:
    amount = 0
    print('amount is ', amount)

elif net_units > 100 and net_units <= 200:
    amount = (net_units - 100) * 5
    print('amount is ', amount)

elif net_units > 200:
    amount = ((net_units - 200) * 10) + 500
    print('amount is ', amount)