import json
import argparse
from datetime import datetime
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import base64
import hashlib

KEY = 'youknownothingaboutit'


def encrypt(plaintext):
    # 使用 SHA-256 对密钥进行哈希，并取前 32 个字节作为 AES 密钥
    key_bytes = hashlib.sha256(KEY.encode()).digest()[:32]
    cipher = AES.new(key_bytes, AES.MODE_CBC)
    ciphertext_bytes = cipher.encrypt(pad(plaintext.encode(), AES.block_size))
    iv = base64.b64encode(cipher.iv).decode()
    ciphertext = base64.b64encode(ciphertext_bytes).decode()
    return iv + ciphertext


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('uuid', type=str, help='the agent host uuid')
    parser.add_argument('server', type=int, help='the max server number')
    parser.add_argument('--time', default='-1', help='YYYY-MM-DD HH:MM:SS')
    args = parser.parse_args()
    expired_at = args.time
    expired_at = expired_at if expired_at == '-1' else str(datetime.strptime(expired_at, '%Y-%m-%d %H:%M:%S'))

    license = {
        'uuid': args.uuid,
        'server': args.server,
        'expired_at': expired_at
    }
    print(encrypt(json.dumps(license)))
