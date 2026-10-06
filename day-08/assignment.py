# 01. Take values of length and breadth of a rectangle from user and check if it is square or not.

#Input the length from user
length = float(input('Enter the length : '))

#Input the breadth from user
breadth = float(input('Enter the breadth : '))

#square is a rectangle whose length and breadth are equal and commonly called as sides which are of equal length.

if breadth == length :
    print('Yes, It is Square')
    
else:
    print('It is not Square')


# 02. Take three int values from user and print greatest among them.
# take three integer numbers from user input

num1 = int(input("Enter first number: "))
num2 = int(input("Enter second number: "))
num3 = int(input("Enter third number: "))
 
if (num1 > num2) and (num1 > num3):
    largest = num1
    
elif (num2 > num1) and (num2 > num3):
    largest = num2
    
else:
    largest = num3

print("The largest number is",largest)


# 03. A student will not be allowed to sit in exam if his/her attendence is less than 75%.

held = int(input('Number of classes held : '))
attended = int(input('Number of classes attended : '))

attended_ratio = (attended/held) * 100

if attended_ratio >= 75:
    print('You are allowed')
else:
    print('You are not allowed')



