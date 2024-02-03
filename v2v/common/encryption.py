from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import base64
import hashlib

KEY = 'youknownothingaboutit'


# 加密函数
def encrypt(plaintext):
    # 使用 SHA-256 对密钥进行哈希，并取前 32 个字节作为 AES 密钥
    key_bytes = hashlib.sha256(KEY.encode()).digest()[:32]
    cipher = AES.new(key_bytes, AES.MODE_CBC)
    ciphertext_bytes = cipher.encrypt(pad(plaintext.encode(), AES.block_size))
    iv = base64.b64encode(cipher.iv).decode()
    ciphertext = base64.b64encode(ciphertext_bytes).decode()
    return iv + ciphertext


# 解密函数
def decrypt(ciphertext):
    iv = base64.b64decode(ciphertext[:24])
    ciphertext_bytes = base64.b64decode(ciphertext[24:])
    # 使用 SHA-256 对密钥进行哈希，并取前 32 个字节作为 AES 密钥
    key_bytes = hashlib.sha256(KEY.encode()).digest()[:32]
    cipher = AES.new(key_bytes, AES.MODE_CBC, iv=iv)
    decrypted_bytes = unpad(cipher.decrypt(ciphertext_bytes), AES.block_size)
    decrypted_text = decrypted_bytes.decode()
    return decrypted_text


if __name__ == '__main__':
    plaintext = 'Hello, World!'

    encrypted_text = encrypt(plaintext)
    print("Encrypted Text:", encrypted_text)

    decrypted_text = decrypt(encrypted_text)
    print("Decrypted Text:", decrypted_text)
