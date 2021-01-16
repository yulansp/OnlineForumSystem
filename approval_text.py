# 用来做文本审核的，还未上线
import urllib.parse
import binascii
import hashlib
import hmac
import time
import aiohttp
from config import configs
import sys
import codecs

sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())


async def approval_text(text=''):
    param = {'Action': 'ContentApproval', 'Language': 'zh-CN', 'Nonce': '4075', 'Region': 'ap-guangzhou',
             'SecretId': configs['tencent_cloud']['SecretId'], 'Text': text, "Timestamp": int(time.time()),
             'Token': configs['tencent_cloud']['token'], 'Version': '2019-04-08'}
    sign_str = "GETnlp.tencentcloudapi.com/?"
    sign_str += "&".join("%s=%s" % (k, param[k]) for k in sorted(param))
    secret_key = "WnqdCPN66vNrBGhtufAw3vXC9sOiyax4"
    sign_str = bytes(sign_str, "utf-8")
    secret_key = bytes(secret_key, "utf-8")
    hashed = hmac.new(secret_key, sign_str, hashlib.sha1)
    signature = binascii.b2a_base64(hashed.digest())[:-1]
    signature = signature.decode()
    param['Signature'] = signature
    url = 'https://nlp.tencentcloudapi.com/?'
    url = url + urllib.parse.urlencode(param)
    async with aiohttp.request('GET', url) as resp:
        json_r = await resp.json()
    print(json_r)
    return json_r


import asyncio

asyncio.get_event_loop().run_until_complete(approval_text(''))
