import hashlib
# Hash password using SHA-3
def hash_password(password):
    return hashlib.sha3_256(password.encode()).hexdigest()