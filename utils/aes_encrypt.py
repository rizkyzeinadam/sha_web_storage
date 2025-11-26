from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes

def pad(data):
    pad_len = AES.block_size - (len(data) % AES.block_size)
    return data + bytes([pad_len]) * pad_len

def encrypt_file(filepath, key):
    key = key.encode()[:32].ljust(32, b'\0')  # AES-256 key
    iv = get_random_bytes(16)

    with open(filepath, "rb") as f:
        original_data = f.read()

    padded_data = pad(original_data)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    encrypted = iv + cipher.encrypt(padded_data)

    encrypted_path = filepath + ".enc"

    with open(encrypted_path, "wb") as f:
        f.write(encrypted)

    return encrypted_path

def unpad(data):
    pad_len = data[-1]
    return data[:-pad_len]

def decrypt_file(filepath, key):
    key = key.encode()[:32].ljust(32, b'\0')  # AES-256 key

    with open(filepath, "rb") as f:
        encrypted_data = f.read()

    iv = encrypted_data[:16]
    ciphertext = encrypted_data[16:]

    cipher = AES.new(key, AES.MODE_CBC, iv)
    decrypted_padded = cipher.decrypt(ciphertext)
    decrypted_data = unpad(decrypted_padded)

    return decrypted_data
