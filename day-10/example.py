name = "Rafiul"
marks = [70, 80, 65, 90, 75]

total = 0
index = 0

while index < len(marks):
    total = total + marks[index]
    index = index + 1

average = total / len(marks)

print("Name:", name)
print("Total:", total)
print("Average:", average)

for mark in marks:
    print("Mark:", mark)