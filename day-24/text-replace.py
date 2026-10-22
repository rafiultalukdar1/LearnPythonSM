print('How to Search and Replace Text in a File in Python')


# Search and Replace Text in a File

# Example 1: Search a Word

print('Search a Word')

with open('data.txt', 'r') as file:
    text = file.read()

if 'Python' in text:
    print('Word Found!')
else:
    print('Word Not Found!')


# Example 2: Replace a Word

print('Replace a Word')

text = text.replace('Python', 'Java')

with open('data.txt', 'w') as file:
    file.write(text)

print('Text Replaced!')


# Example 3: Count a Word

print('Count a Word')

with open('data.txt', 'r') as file:
    text = file.read()

print('Python Count:', text.count('Python'))


# Example 4: Case-Insensitive Search

print('Case-Insensitive Search')

with open('data.txt', 'r') as file:
    text = file.read()

if 'python' in text.lower():
    print('Python Found!')
else:
    print('Python Not Found!')


# Example 5: Replace Multiple Words

print('Replace Multiple Words')

with open('data.txt', 'r') as file:
    text = file.read()

text = text.replace('Python', 'Java')

text = text.replace('easy', 'powerful')

with open('data.txt', 'w') as file:
    file.write(text)

print('Multiple Words Replaced!')


# Example 6: Replace Text in a New File

print('Replace Text in a New File')

with open('data.txt', 'r') as file:
    text = file.read()

text = text.replace('Java', 'JavaScript')

with open('updated.txt', 'w') as file:
    file.write(text)

print('New File Created!')