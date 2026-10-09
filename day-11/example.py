# Number Pattern Art Generator

num = [1, 2, 3, 4, 5, 6]

# Outer loop
for ele in num:
    # Inner loop
    index = 0

    while index < ele:
        print(ele, end=' ')
        index = index + 1

    print()

# Another Pattern
print("\n--- Pattern Art ---")

for x in range(1, 7):
    for y in range(x):
        print('#', end=' ')

    print()