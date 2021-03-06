from aiohttp import web
import os
from cookies import _COOKIE_KEY, COOKIE_NAME, cookie_to_user


# 处理cookie，于 handler 之前运行
@web.middleware
async def cookie_middleware(request, handler):
    request.__user__ = None
    cookie_str = request.cookies.get(COOKIE_NAME)
    if cookie_str:
        user = await cookie_to_user(cookie_str)
        if user:
            request.__user__ = user
    return await handler(request)


# 返回中间件，处理返回值
@web.middleware
async def res_middleware(request, handler):
    r = await handler(request) # 于 handler 之后运行该中间件
    if isinstance(r, web.StreamResponse):
        return r
    if isinstance(r, bytes):
        resp = web.Response(body=r, content_type='application/octet-stream')
        return resp
    if isinstance(r, str): # 直接返回文本
        if r.startswith('redirect:'): # 重定向
            return web.HTTPFound(r[9:])
        resp = web.Response(body=r.encode('utf-8'), content_type='text/html', charset='utf-8')
        return resp
    if isinstance(r, dict): # 经过 template 渲染， 或返回json
        template = r.get('__template__')
        if template is None: # 无 template， 返回json
            return web.json_response(r)
        else:
            r['user'] = request.__user__
            shicifile = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     'templates', 'shici.html')
            with open(shicifile, 'rb') as f:
                r['poetry'] = f.read().decode('utf-8')  # 载入右侧诗词
            resp = web.Response(
                body=request.app['__templating__'].get_template(template).render(**r).encode('utf-8'),
                content_type='text/html', charset='utf-8')  # 模板渲染
            return resp
    if isinstance(r, int) and r >= 100 and r < 600:
        return web.Response(r)
    if isinstance(r, tuple) and len(r) == 2:
        t, m = r
        if isinstance(t, int) and t >= 100 and t < 600:
            return web.Response(t, str(m))
    # default:
    resp = web.Response(body=str(r).encode('utf-8'), content_type='text/html', charset='utf-8')
    return resp


middlewares = [res_middleware, cookie_middleware]
