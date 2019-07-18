import requests
import binascii
from requests.adapters import HTTPAdapter


def hex_prefix(value):
    if value[:2] == b'0x':
        return value
    return b'0x'+value


def to_hex(value):
    if isinstance(value, bytes):
        return hex_prefix(binascii.hexlify(value))
    if isinstance(value, str):
        return hex_prefix(binascii.hexlify(value.encode('utf-8')))
    if isinstance(value, int):
        return value


def convert_args(args):
    args = args or {}
    for k,v in args.items():
        args[k] = to_hex(v)
    return args


class TRY(object):
    def __init__(self, url=None):
        if url and not url[-1] == '/':
            url = url+'/'
        self.url = url or "http://localhost:46657/"

    def call(self, name, args=None):
        # TODO 判断超时时间
        endpoint = '{}{}'.format(self.url, name)
        payload = convert_args(args)
        s = requests.Session()
        s.mount('http://', HTTPAdapter(max_retries=3, pool_connections=100, pool_maxsize=100))
        s.keep_alive = False
        try:
            result = s.get(endpoint, params=payload, timeout=5)
            return result.json()
        except Exception as e:
            print('trias_rpc_client ,call ,Error parsing response: {}'.format(e))
            return {'error': e}

    def broadcast_tx_commit(self, tx):
        return self.call('tri_bc_tx_commit', {'tx': tx})

    def block(self, height):
        return self.call('tri_block_info', {'height': height})

    def tx(self, hash):
        return self.call('tri_block_tx', {'hash': hash})

    def commit(self, height):
        return self.call('tri_bc_tx_commit', {'height': height})

    def query(self, path, data, prove):
        return self.call('tri_abci_query', {'path': path, 'data': data, 'prove': prove})

    def broadcast_tx_async(self, tx):
        return self.call('tri_bc_tx_async', {'tx': tx})

    def broadcast_txs_async(self, txs):
        return self.call('tri_bc_txs_async', {'tx': txs})


if __name__ == "__main__":
    tm = TRY(url='http://192.168.1.206:46657')
    jsonData = {'name':'zhangsan','age':'4'}
    import json
    import base64
    re = tm.broadcast_tx_commit(json.dumps(jsonData))
    print(re['result']['hash'])
    tx = tm.tx(hash=bytes.fromhex(re['result']['hash']))['result']['tx']

    txBytes = base64.decodebytes(bytes(tx, 'utf-8'))
    print(str(txBytes)[14:])
