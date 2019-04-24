#!/usr/bin/env python
# encoding: utf-8
import bigchaindb_driver
from bigchaindb_driver import BigchainDB
from bigchaindb_driver.crypto import generate_keypair

from time import sleep, time
from urllib import request, parse
import json

# 需要安装python包: pip3 install bigchaindb_driver==0.4.0

DATA_KEY_KEY = 'data'
DATA_VALUE_KEY = 'data_value'


def exec_write(data, meta_data, bdb_host, bdb_port=10070, wait_for_valid=True):
    """
    获取bigchaindb的连接对象
    :param bdb_host:host
    :param bdb_port:端口,默认10070可以不写
    :param data: 交易数据,必须是dict或者是None,例如{
        'planet': 'earth',
        'function': 'test create'
    }
    :param meta_data:必须是dict或者是None,例如:{
        'planet': 'earth',
        'function': 'test create'
    }
    :param wait_for_valid:默认是True,等证实完成再返回
    :return:交易ID,拥有者私钥
    """
    user = generate_keypair()
    try:
        tx_id = exec_write_with_key(data, meta_data, user.private_key,
                                    user.public_key, bdb_host, bdb_port,
                                    wait_for_valid)
        return tx_id, user.private_key, user.public_key
    except Exception as e:
        raise e


def exec_write_with_key(data, meta_data, private_key, public_key, bdb_host, bdb_port=10070, wait_for_valid=True):
    """
    获取bigchaindb的连接对象
    :param bdb_host:host
    :param bdb_port:端口,默认10070可以不写
    :param data: 交易数据,必须是dict或者是None,例如{
        'planet': 'earth',
        'function': 'test create'
    }
    :param meta_data:必须是dict或者是None,例如:{
        'planet': 'earth',
        'function': 'test create'
    }
    :param wait_for_valid:默认是True,等证实完成再返回
    :return:交易ID,拥有者私钥
    """

    bdb = BigchainDB('http://' + bdb_host + ':' + str(bdb_port))  # bdp默认端口10070
    data['time'] = int(time())
    # 必须把数据放到这个value中,否则会报错
    _asset = {
        DATA_KEY_KEY: {DATA_VALUE_KEY: data}
    }

    # 准备交易数据
    try:
        prepared_creation_tx = bdb.transactions.prepare(
            operation='CREATE',
            signers=public_key,
            asset=_asset,
            metadata=meta_data
        )
        # 执行交易,这个只是本地"运算"交易数据,需要发送到BDP,并且经过所有节点或者大部分节点证实,才算真正的交易
        fulfilled_creation_tx = bdb.transactions.fulfill(
            prepared_creation_tx,
            private_keys=private_key
        )

        # 发送交易给BDP
        bdb.transactions.send(fulfilled_creation_tx)
        # 执行后,会吧ID赋值
        tx_id = fulfilled_creation_tx['id']
        if wait_for_valid:
            """
            每隔一秒钟请求一次交易状态,因为"去中心化",需要所有的节点把交易数据证实并插入才算证实完成,这个有一个延迟

            """
            trials = 0
            time_unit = 0.1  # 时间单元
            total_trails = 60 / time_unit

            while trials < total_trails:
                print(trials)
                try:
                    if bdb.transactions.status(tx_id).get('status') == 'valid':
                        print('Tx valid in:', trials, 'secs')
                        break
                    else:
                        trials += 1
                        sleep(time_unit)
                except bigchaindb_driver.exceptions.NotFoundError as error:
                    print(error)
                    trials += 1
                    sleep(time_unit)
            # 如果超过60秒证实失败,退出
            if trials == total_trails:
                print('Tx is still being processed... Bye!')
                return ''
        print('[octa_bdp_api] write successfully, the tx_id is : ' + tx_id)
        return tx_id
    except Exception as e:
        raise e


def query_by_tx_id(tx_id, bdb_host, bdb_port=10070):
    """
    根据交易ID查询资产数据
    :param tx_id:
    :param bdb_host:host
    :param bdb_port:端口,默认10070可以不写
    :return:交易数据
    """
    t1 = time()
    bdb = BigchainDB('http://' + bdb_host + ':' + str(bdb_port))  # bdp默认端口10070
    query_data = bdb.transactions.retrieve(tx_id)
    t2 = time()
    print('time used:', t2 - t1)
    _opt = query_data['operation']
    # print('operate type :', _opt)
    if _opt == 'TRANSFER':
        assert_data = query_data['asset']['id']
        return assert_data
    if _opt == 'CREATE':
        assert_data = query_data['asset'][DATA_KEY_KEY][DATA_VALUE_KEY]
        return assert_data


def query_transaction_by_id(tx_id, bdb_host, bdb_port=10070):
    """
    根据交易ID查询交易信息
    :param tx_id:
    :param bdb_host:host
    :param bdb_port:端口,默认10070可以不写
    :return:交易数据
    """
    bdb = BigchainDB('http://' + bdb_host + ':' + str(bdb_port))  # bdp默认端口10070
    query_data = bdb.transactions.retrieve(tx_id)
    return query_data


def query_by_assert_id(assert_id, bdb_host, bdb_port=10070):
    """
    根据资产ID查询数据
    :param assert_id:资产ID
    :param bdb_host:host
    :param bdb_port:端口,默认10070可以不写
    :return:交易数据
    """
    t1 = time()
    bdb = BigchainDB('http://' + bdb_host + ':' + str(bdb_port))  # bdp默认端口10070
    query_data = bdb.transactions.get(asset_id=assert_id)
    t2 = time()
    print('time used:', t2 - t1)
    return query_data


def query_asset_by_key(key, bdb_host, limit, bdb_port=10070):
    """
    返回资产集合
    :param key:资产关键字
    :param bdb_host:
    :param bdb_port:
    :param limit 条数
    :return: []
    """
    _url = 'http://' + bdb_host + ':' + str(bdb_port)\
           + '/api/v1/assets?search=' + key + '&limit=' + str(limit)
    req = request.Request(parse.quote(_url, safe='/:?=&'))
    opener = request.build_opener()
    response = opener.open(req)
    _res = json.loads(response.read().decode('utf-8'))
    return _res


def query_tx_status(tx_id, bdb_host, bdb_port, max_trials=60):
    """
    查询交易ID是否已经合法,尝试次数默认为60次,每次为1秒
    :param tx_id:
    :param bdb_host:
    :param bdb_port:
    :param max_trials: 最大查询次数,默认60
    :return:
    """
    bdb = BigchainDB('http://' + bdb_host + ':' + str(bdb_port))  # bdp默认端口10070
    trials = 0
    while trials < max_trials:
        try:
            if bdb.transactions.status(tx_id).get('status') == 'valid':
                return 'valid'
            else:
                trials += 1
                sleep(1)
        except bigchaindb_driver.exceptions.NotFoundError:
            trials += 1
            sleep(1)
    if trials == max_trials:
        return 'unvalid'


if __name__ == '__main__':
    # ip = '123.56.124.137'
    ip = '192.168.1.231'
    port = 10070
    if __name__ == '__main__':
        dict = {'asset': 'test'}

        key_pair_1 = generate_keypair()
        tx_id = exec_write_with_key(dict, None, key_pair_1.private_key,
                                    key_pair_1.public_key, ip, port, True)
        print('交易ID ', tx_id, '用户1的私钥 ', key_pair_1.private_key, 'public key:', key_pair_1.public_key)
        print("---------create successful---------")

