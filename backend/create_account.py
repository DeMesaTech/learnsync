from utils import hash_password

password = hash_password("Capstone.26")
print(password)
'''INSERT INTO "user" (email, name, password, role)
               VALUES (%s, %s, %s, %s, %s)
               RETURNING user_id'''
print(f"INSERT INTO \"user\" (email, name, password, role)\n VALUES (\'hassandm@gmail.com\', \'Dan DM\', \'{password}\', \'student\');")