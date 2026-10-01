# List

list = [1, 2, 3, True, [1, 2], 'data', (2, 4, 6)]

print(list)
print(list[4][1])
print(type(list))

# Tuples

tuple = (1, 2, 3, 'tuple')

print(type(tuple))
print(tuple[0])
print(tuple[0:4]) # colon means to 

# Range

r = range(10)

print(r)

for i in r:
    print(i)

ra = range(1, 100, 20)

for ii in ra:
    print(ii)

# Array

import array as ar

a = ar.array('i', (1, 2, 3))

print(a)

# Set 

sett = {1, 2, 3}

print(type(sett))

# Dictionary

dic = {
    'Institute' : 'SPI',
    'Dept' : 'Computer'
}

print(type(dic))
print(dic)

# Data Frame (Pandas)

import pandas as pd

data = {
    "Name": ["Rafiul", "Rahim", "Karim"],
    "Age": [25, 22, 24],
    "Roll": [66, 67, 68]
}

df = pd.DataFrame(data)

print(df)