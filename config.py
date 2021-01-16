# 配置文件

configs = {
    'debug': True,
    'rds': {
        'host': '127.0.0.1',
        'port': 6379,
        'db': 1
    },
    'web': {
        'host': '0.0.0.0',
        'port': 8016,
    },
    'tencent_cloud': {
        'SecretId': 'AKID9AfwDEihAWesraqGEwTnLjrlThgjuFdk',
        'token': 'qingpingyue',
    },
    'session': {
        'secret': 'shiqingbo'
    }
}

aiomyorm = {
    'host': '127.0.0.1',
    'port': 3306,
    'user': 'root',
    'password': '@wht990125',
    'db': 'web_project',
    'engine': 'mysql'
}
