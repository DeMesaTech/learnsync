from utils import hash_password

password = hash_password("leanrsync123")
email = ["admin@gmvcc.edu.ph", "mohammadhassan.demesa@cbsua.edu.ph", "hassandm16@gmail.com"]
name = ["GMVCC Learnsync Admin", "Mohammad Hassan Demesa", "Hassan Demesa"]
print(password)
role = ["admin", "student", "teacher"]

# user_id | name | email | password | role | created_at | activation_token_hash | activation_expires_at | is_activated
#---------+------+-------+----------+------+------------+-----------------------+-----------------------+--------------

print(
    f"\nINSERT INTO account (user_id, email, name, password, role, created_at, activation_token_hash, activation_expires_at, is_activated) VALUES"
)
for index, account in enumerate(zip(email, name, role), start=1):
    suffix = "," if index < len(email) else ";"
    print(
        f"({index}, '{account[0]}', '{account[1]}', '{password}', '{account[2]}', CURRENT_TIMESTAMP, NULL, NULL, FALSE){suffix}"
    )
print(f"\n")

    