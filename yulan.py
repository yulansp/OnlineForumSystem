# web封装框架
import asyncio
from aiohttp import web
import logging, os, time;
from time import strftime
from jinja2 import Environment, FileSystemLoader
import inspect
from urllib import parse
import functools
from apis import APIError
from middleware import middlewares


# 对函数fn的参数进行分析，从http请求中提取出必要参数

# POSITIONAL_ONLY
# Value must be supplied as a positional argument. Positional only parameters are those
# which appear before a / entry (if present) in a Python function definition.
#
# POSITIONAL_OR_KEYWORD
# Value may be supplied as either a keyword or positional argument (this is the standard
# binding behaviour for functions implemented in Python.)
#
# VAR_POSITIONAL
# A tuple of positional arguments that aren't bound to any other parameter. This corresponds
# to a *args parameter in a Python function definition.
#
# KEYWORD_ONLY
# Value must be supplied as a keyword argument. Keyword only parameters are those which appear
# after a * or *args entry in a Python function definition.
#
# VAR_KEYWORD
# A dict of keyword arguments that aren't bound to any other parameter. This corresponds to
# a **kwargs parameter in a Python function definition.

# 摘自https://docs.python.org/zh-cn/3/library/inspect.html?highlight=inspect#module-inspect


def get_required_keyword(fn):
    # 获取没有包含默认值的 POSITIONAL_OR_KEYWORD 以及 KEYWORD_ONLY
    keyword = []
    paras = inspect.signature(fn).parameters
    for name, para in paras.items():
        if (para.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD or \
            para.kind == inspect.Parameter.KEYWORD_ONLY) \
                and para.default == inspect.Parameter.empty:  # 无默认值
            keyword.append(name)
    return tuple(keyword)


def get_named_keyword(fn):
    # 获取 POSITIONAL_OR_KEYWORD 与 KEYWORD_ONLY (无论是否有默认值)
    keyword = []
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD \
                or param.kind == inspect.Parameter.KEYWORD_ONLY:
            keyword.append(name)
    return tuple(keyword)


def has_var_keyword(fn):
    # 判断是否含有 VAR_KEYWORD (**kwargs)
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            return True
    return False


def has_request(fn):
    # 判断参数中是否需要 request
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if name == 'request':
            return True
    return False


class RequestHandler(object):
    def __init__(self, fn):
        self._fn = fn
        self._kw = {}
        self._request = has_request(fn)  # 是否需要request参数
        self._has_var_keyword = has_var_keyword(fn)  # 是否含有 VAR_KEYWORD (**kwargs)
        self._named_keyword = get_named_keyword(fn)  # 所有有名参数，即 POSITIONAL_OR_KEYWORD 与
        # KEYWORD_ONLY (无论是否有默认值)
        self._required_keyword = get_required_keyword(fn)  # 所有需要有参数值的参数，即没有包含默认值的
        # POSITIONAL_OR_KEYWORD 以及 KEYWORD_ONLY

    async def __call__(self, request):  # aiohttp中注册函数只能有request一个参数，其他参数交给框架来提取
        await self.handelkw(request)
        if not asyncio.iscoroutinefunction(self._fn):
            self._fn = asyncio.coroutine(self._fn)  # 将_fn改造为协程
        try:
            r = await self._fn(**self._kw)
            return r
        except APIError as e:
            return dict(error=e.error, data=e.data, message=e.message)

    async def handelkw(self, request):
        for k, v in request.match_info.items():
            if k in self._kw:
                logging.warning('Duplicate arg name in named arg and kw args: %s' % k)
            self._kw[k] = v

        copy = dict()
        if not self._has_var_keyword and self._named_keyword:
            # 移除掉不需要的参数
            for name in self._named_keyword:
                if name in self._kw:
                    copy[name] = self._kw[name]
        self._kw = copy

        if self._request:  # handler需要request参数
            self._kw['request'] = request

        if self._required_keyword:
            for name in self._required_keyword:
                if not name in self._kw:
                    return web.HTTPBadRequest(text='Missing argument: %s' % name)


class GETHandler(RequestHandler):
    async def __call__(self, request):
        if self._has_var_keyword or self._named_keyword:
            qs = request.query_string # get方法，可以从 query_string 中提取参数
            if qs:
                for k, v in parse.parse_qs(qs, True).items():
                    self._kw[k] = v[0]

        return await super().__call__(request)


class POSTHandler(RequestHandler):
    async def __call__(self, request): # 对于post方法，屏蔽json格式与表单格式处理的差异性
        if self._has_var_keyword or self._named_keyword:
            if not request.content_type:
                return web.HTTPBadRequest(text='Missing Content-Type.')
            ct = request.content_type.lower()
            if ct.startswith('application/json'): # json格式
                params = await request.json()
                if not isinstance(params, dict):
                    return web.HTTPBadRequest(text='JSON body must be object.')
                self._kw = dict(**params)
            elif ct.startswith('application/x-www-form-urlencoded') or ct.startswith(
                    'multipart/form-data'): # 表单格式
                params = await request.post()
                self._kw = dict(**params)
            else:
                return web.HTTPBadRequest(
                    text='Unsupported Content-Type: %s' % request.content_type)
        return await super().__call__(request)


class FilePostHandler(RequestHandler):
    # 专用于处理文件上传
    async def __call__(self, request):
        if not request.content_type:
            return web.HTTPBadRequest(text='Missing Content-Type.')
        ct = request.content_type.lower()
        if ct.startswith('multipart/form-data'):
            reader = await request.multipart()
            self._kw['reader'] = reader
        else:
            return web.HTTPBadRequest(text='Unsupported Content-Type: %s' % request.content_type)
        return await super().__call__(request)


routes = []


# get、post方法的装饰器
def get(path):
    def decorator(fun):
        fn = GETHandler(fun)
        routes.append(web.get(path, fn))  # 将函数添加到routes中，以便向web(aiohttp) app注册

        @functools.wraps(fun)
        def wraps(request):
            return fn(request)

        return wraps

    return decorator


def post(path):
    def decorator(fun):
        fn = POSTHandler(fun)
        routes.append(web.post(path, fn))

        @functools.wraps(fun)
        def wraps(request):
            return fn(request)

        return wraps

    return decorator


def file_post(path):
    def decorator(fun):
        fn = FilePostHandler(fun)
        routes.append(web.post(path, fn))

        @functools.wraps(fun)
        def wraps(request):
            return fn(request)

        return wraps

    return decorator


def add_static(app, static_path='static'):
    # 添加静态文件路径
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), static_path)
    app.router.add_static('/static/', path)
    logging.info('add static %s => %s' % ('/static/', path))


def init_jinja2(app, **kw):
    # init jinja2,kw: the config as same as jinja2
    # 对jinja2进行初始化
    logging.info('init jinja2...')
    options = dict(
        autoescape=kw.get('autoescape', True),
        block_start_string=kw.get('block_start_string', '{%'),
        block_end_string=kw.get('block_end_string', '%}'),
        variable_start_string=kw.get('variable_start_string', '{{'),
        variable_end_string=kw.get('variable_end_string', '}}'),
        auto_reload=kw.get('auto_reload', True)
    )
    path = kw.get('path', None)
    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
    logging.info('set jinja2 template path: %s' % path)
    env = Environment(loader=FileSystemLoader(path), **options)
    filters = kw.get('filters', None)
    if filters is not None:
        for name, f in filters.items():
            env.filters[name] = f
    app['__templating__'] = env


def datetime_filter(t):
    return strftime('%Y-%m-%d %H:%M:%S', time.localtime(t))


def runapp(jinja2=True, host='127.0.0.1', port=5000, static='static'):
    app = web.Application(middlewares=middlewares)
    app.add_routes(routes)
    add_static(app, static)
    if jinja2:
        init_jinja2(app, filters=dict(datetime=datetime_filter))
    web.run_app(app, host=host, port=port)
