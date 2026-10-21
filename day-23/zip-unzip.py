print('Zip & UnZip File with 2 Lines of Python Code')


# Zip & Unzip Files in Python

import shutil
import zipfile
import os


# Example 1: Zip a Folder
print('Zip a Folder')

shutil.make_archive('backup', 'zip', 'my_folder')


# Example 2: Unzip a File
print('Unzip a File')

shutil.unpack_archive('backup.zip', 'extracted_folder')


# Example 3: Create a Zip File
print('Create a Zip File')

with zipfile.ZipFile('data.zip', 'w') as zip_file:
    zip_file.write('example.txt')


# Example 4: Read Zip File Contents
print('Read Zip Contents')

with zipfile.ZipFile('data.zip', 'r') as zip_file:
    print(zip_file.namelist())


# Example 5: Extract All Files
print('Extract All Files')

with zipfile.ZipFile('data.zip', 'r') as zip_file:
    zip_file.extractall('output_folder')


# Example 6: Check Zip File
print('Check Zip File')

print(zipfile.is_zipfile('data.zip'))


# Example 7: List Folder Files
print('List Folder Files')

print(os.listdir('my_folder'))
