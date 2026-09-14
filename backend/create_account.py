from utils import hash_password

password = hash_password("gmvccAdmin.26")
print(password)
'''INSERT INTO account (email, name, password, role)
               VALUES (%s, %s, %s, %s, %s)
               RETURNING user_id'''
print(f"INSERT INTO \"account\" (email, name, password, role)\n VALUES (\'admin@gmvcc.edu\', \'GMVCC Admin\', \'{password}\', \'admin\');")