c = 0

while (c <= 10):
    print(c)
    c = c + 1

# Example

data = 'python'

index = 0

while index<len(data):
    print(data[index])
    index = index + 1

# Example

value = 'I love data scienc'

value = value.split()
index = 0

while index<len(value):
    print(value[index])
    index = index + 1

# Example

numbers = [5, 10, 15, 20, 25, 30]

total = 0
index = 0

while index < len(numbers):
    total = total + numbers[index]
    print(total, numbers[index])
    index = index + 1