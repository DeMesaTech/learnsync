from utils import hash_password

password = hash_password("leanrsync123")
print(password)
'''INSERT INTO account (email, name, password, role)
               VALUES (%s, %s, %s, %s, %s)
               RETURNING user_id'''
print(f"INSERT INTO \"account\" (email, name, password, role)\n VALUES (\'samplemail@gmail.com\', \'teacher 1\', \'{password}\', \'teacher\');")