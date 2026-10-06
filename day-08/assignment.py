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