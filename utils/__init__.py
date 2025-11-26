from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes

def pad(data):
    pad_len = AES.block_size - (len(data) % AES.block_size)
    return data + bytes([pad_len]) * pad_len

def encrypt_file(filepath, key):
    key = key.encode()[:32].ljust(32, b'\0')  # AES-256 key (32 bytes)
    iv = get_random_bytes(16)  # 16 bytes for AES

    with open(filepath, "rb") as f:
        original_data = f.read()

    padded_data = pad(original_data)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    encrypted_data = iv + cipher.encrypt(padded_data)

    encrypted_path = filepath + ".enc"

    with open(encrypted_path, "wb") as f:
        f.write(encrypted_data)

    return encrypted_path
