data = 'Day-3.0 - 60 Days of Python'

print(data.find('of'))
# print(data.find('s', 10, 20))
# print(data.index('y', 10, 20))

print(data.lower()) # convert all char into lowercase
print(data.upper()) # convert all char into uppercase

data_second = 'The Bangladesh national football team is the national recognised football team of Bangladesh'

print(data_second.casefold()) # convert all char into lowercase
print(data_second.capitalize()) # convert only first char uppercase
print(data_second.title()) # convert all word's first char uppercase