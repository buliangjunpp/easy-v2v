import json
import argparse
from datetime import datetime
from v2v.common.encryption import encrypt


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
