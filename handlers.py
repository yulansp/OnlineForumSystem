from sendmail import sendemail
import time
import uuid
import json
import os
import random
import re
import hashlib
import os
import logging
from aiohttp import web
from lxml import etree
from time import strftime

from yulan import get, post, file_post
from models import User, Blog, Comment, Timeline, ThumbUps
from aiomyorm import Count
from apis import APIError, APIValueError, APIResourceNotFoundError, APIPermissionError
import rds
from cookies import _COOKIE_KEY, COOKIE_NAME, user_to_cookie, cookie_to_user

item_per_page = 15
_RE_EMAIL = re.compile(
    r'^[a-z0-9\.\-\_]+\@[a-z0-9\-\_]+(\.[a-z0-9\-\_]+){1,4}$')


def next_id():
    return '%s' % (uuid.uuid4().hex)


########################################################################################
#   For show blog_list
########################################################################################
# 默认主页
@get('/')
async def index(page=1):
    page = int(page)
    total = (await Blog.aggregate(t=Count()))['t']
    page_count = total // item_per_page + \
                 (1 if total % item_per_page > 0 else 0)
    if page < 1 or page > page_count:
        page = 1
    blogs = await Blog.order_by('-created_at').limit((page - 1) * item_per_page,
                                                     item_per_page).find()
    # blogs = await Blog.FindAll(orderBy='created_at desc', limit=((page - 1) * item_per_page, item_per_page))
    return {
        '__template__': 'mainpage.html',
        'blogs': blogs,
        'classfication': 'main',
        'total_item': total,
        'current_page': page,
        'title': '首页'
    }


@get('/skill')
async def skill(page=1):
    page = int(page)
    total = (await Blog.filter(classfication='skill').aggregate(t=Count()))['t']
    # total = await Blog.FindNumber('count(*)', where='classfication', args='skill')
    page_count = total // item_per_page + \
                 (1 if total % item_per_page > 0 else 0)
    if page < 1 or page > page_count:
        page = 1
    blogs = await Blog.filter(classfication='skill').order_by('-created_at').limit(
        (page - 1) * item_per_page, item_per_page).find()
    # blogs = await Blog.FindAll(where='classfication', args='skill', orderBy='created_at desc')
    return {
        '__template__': 'mainpage.html',
        'blogs': blogs,
        'classfication': 'skill',
        'total_item': total,
        'current_page': page,
        'title': '技术'
    }


@get('/read')
async def read(page=1):
    page = int(page)
    total = (await Blog.filter(classfication='read').aggregate(t=Count()))['t']
    # total = await Blog.FindNumber('count(*)', where='classfication', args='read')
    page_count = total // item_per_page + \
                 (1 if total % item_per_page > 0 else 0)
    if page < 1 or page > page_count:
        page = 1
    blogs = await Blog.filter(classfication='read').order_by('-created_at').limit(
        (page - 1) * item_per_page, item_per_page).find()
    # blogs = await Blog.FindAll(where='classfication', args='read', orderBy='created_at desc')
    return {
        '__template__': 'mainpage.html',
        'blogs': blogs,
        'classfication': 'read',
        'total_item': total,
        'current_page': page,
        'title': '读书'
    }


@get('/something')
async def something(page=1):
    page = int(page)
    total = (await Blog.filter(classfication='something').aggregate(t=Count()))['t']
    # total = await Blog.FindNumber('count(*)', where='classfication', args='something')
    page_count = total // item_per_page + \
                 (1 if total % item_per_page > 0 else 0)
    if page < 1 or page > page_count:
        page = 1
    blogs = await Blog.filter(classfication='something').order_by('-created_at').limit(
        (page - 1) * item_per_page, item_per_page).find()
    # blogs = await Blog.FindAll(where='classfication', args='something', orderBy='created_at desc')
    return {
        '__template__': 'mainpage.html',
        'blogs': blogs,
        'classfication': 'something',
        'total_item': total,
        'current_page': page,
        'title': '杂谈'
    }


@get('/about')
async def about():
    timeline = await Timeline.order_by('-release_time').find()
    # timeline = await Timeline.FindAll(orderBy='release_time desc')
    return {
        '__template__': 'about.html',
        'timeline': timeline,
    }


########################################################################################
#   For show blog page
########################################################################################
@get('/blog')
async def show_blog(request, id):
    blog = await Blog.pk_find(id)
    # blog = await Blog.Find(id)
    if not blog:
        return web.HTTPNotFound()
    blog.page_view = blog.page_view + 1
    await blog.save()
    has_thumbs = 'false'
    if request.__user__:
        r = await ThumbUps.pk_find(id + request.__user__.id)
        if r:
            has_thumbs = 'true'
    return {
        '__template__': 'show_blog.html',
        'blog': blog,
        'has_thumbs': has_thumbs,
        'classfication': blog.classfication
    }


########################################################################################
#   in show blog page get all comment belong to it
########################################################################################
def time_filtter(t):
    delta = int(time.time() - t)
    if delta < 60:
        return u'1分钟前'
    if delta < 3600:
        return u'%s分钟前' % (delta // 60)
    if delta < 86400:
        return u'%s小时前' % (delta // 3600)
    if delta < 604800:
        return u'%s天前' % (delta // 86400)
    else:
        return strftime('%Y-%m-%d', time.localtime(t))


@get('/api/thumbs_up')
async def thumbs_up(request, blog_id):
    if request.__user__:
        uid = request.__user__.id
        buid = blog_id + uid  # blogid与uid组合唯一标记一个赞
        thumb = await ThumbUps.pk_find(buid)
        if thumb:
            return web.HTTPForbidden(text="您已赞过该文章")
        await ThumbUps(blogid_uid=buid).save()

        blog = await Blog.pk_find(blog_id)
        blog.thumbs = blog.thumbs + 1
        await blog.save()
        # 此处可以硬编码sql优化

        return web.HTTPOk()
    return web.HTTPForbidden(text="请先登录")


@get('/api/thumbs_down')
async def thumbs_down(request, blog_id):
    if request.__user__:
        uid = request.__user__.id
        buid = blog_id + uid  # blogid与uid组合唯一标记一个赞
        thumb = await ThumbUps.pk_find(buid)
        if not thumb:
            return web.HTTPForbidden(text="您未赞过该文章")
        await thumb.remove()

        blog = await Blog.pk_find(blog_id)
        blog.thumbs = blog.thumbs - 1
        await blog.save()
        # 此处可以硬编码sql优化

        return web.HTTPOk()
    return web.HTTPForbidden("请先登录")


@get('/api/commentlist')
async def get_comment_list(blog_id):
    blog_id = str(blog_id)
    comments = await Comment.filter(blog_id=blog_id).order_by('-created_at').find()
    # comments = await Comment.FindAll(where='blog_id', args=blog_id, orderBy='created_at desc')
    parentcomment = []
    id_to_index = {}
    index = 0
    for comment in comments:
        if comment.parent_id == '0':  # 没有父级评论
            id_to_index[comment.id] = index
            index = index + 1
            r_comment = {
                'id': comment.id,
                'content': comment.content,
                'name': comment.user_name,
                'img': '../static/imgs/' + comment.user_img,
                'time': time_filtter(comment.created_at),
                'reply_to': comment.reply_to,
                'subcomment': []
            }
            parentcomment.append(r_comment)
    for comment in comments:
        if comment.parent_id == '0':  # 跳过没有父级评论的，只处理有父级评论的
            continue
        r_comment = {
            'id': comment.id,
            'content': comment.content,
            'name': comment.user_name,
            'img': '../static/imgs/' + comment.user_img,
            'time': time_filtter(comment.created_at),
            'reply_to': comment.reply_to,
            'subcomment': []
        }
        parentcomment[id_to_index[comment.parent_id]
        ]['subcomment'].append(r_comment)
    return web.json_response(parentcomment)


########################################################################################
#   in blog page for ereryone to comment
########################################################################################
@post('/api/comment')
async def comment(request, blog_id, parent_id, content, reply_to, blog_name):
    if request.__user__:
        user_id = request.__user__.id
        name = request.__user__.name
        img = request.__user__.img
    else:
        logging.warning('Try comment without authorize')
        return web.HTTPForbidden(text="请先登录")
    id = next_id()
    comment = Comment(id=id, blog_id=blog_id, user_id=user_id, user_name=name, reply_to=reply_to,
                      parent_id=parent_id,
                      content=content, blog_name=blog_name, user_img=img)
    await comment.save()
    return {
        'id': id,
        'name': name,
        'img': '../static/imgs/' + img,
    }


########################################################################################
#   to set user's cookie
########################################################################################


########################################################################################
#   user register
########################################################################################
@post('/api/register')
async def register(email, name, passwd, code):
    if not name:
        raise APIValueError('name', '缺少昵称')
    if not email or not _RE_EMAIL.match(email):
        raise APIValueError('email', '请输入正确的邮箱')
    if not passwd:
        raise APIValueError('passwd', '缺少密码')
    truecode = await rds.execute('get', email)
    truecode = str(truecode.decode('utf-8'))
    if not truecode or truecode != code:
        raise APIValueError('code', '请输入正确的验证码')
    users = await User.filter(email=email).find()
    # users = await User.FindAll(where='email', args=email)
    if len(users) > 0:
        raise APIError('register:failed', 'email', '邮箱已存在,请直接登录')
    img = random.randint(1, 10)
    uid = next_id()
    sha1_passwd = '%s:%s' % (uid, passwd)
    user = User(id=uid, name=name.strip(), img='default_' + str(img) + '.png', email=email,
                passwd=hashlib.sha1(sha1_passwd.encode('utf-8')).hexdigest())
    await user.save()
    r = web.Response(content_type='application/json')
    r.set_cookie(COOKIE_NAME, user_to_cookie(
        user, 864000), max_age=864000, httponly=True)
    return r


@post('/api/emailcode')
async def get_email_code(email):
    code = random.randint(100000, 999999)
    await rds.execute('set', email, code)
    await rds.execute('expire', email, 1200)
    await sendemail(email, code)
    return web.json_response()


########################################################################################
#   user sign in
########################################################################################
@post('/api/signin')
async def signin(email, passwd):
    if not email or not _RE_EMAIL.match(email):
        raise APIValueError('email', '请输入正确的邮箱')
    if not passwd:
        raise APIValueError('passwd', '缺少密码')
    user = await User.filter(email=email).find()
    # user = await User.FindAll(where='email', args=email)
    if len(user) == 0:
        raise APIValueError('email', '邮箱不存在')
    u = user[0]
    uid = u.id
    sha1_passwd = '%s:%s' % (uid, passwd)
    if u.passwd != str(hashlib.sha1(sha1_passwd.encode('utf-8')).hexdigest()):
        raise APIValueError('passwd', '密码错误')
    r = web.Response(content_type='application/json')
    r.set_cookie(COOKIE_NAME, user_to_cookie(
        u, 864000), max_age=864000, httponly=True)
    return r


########################################################################################
#   user sign out
########################################################################################
@get('/api/signout')
def signout(request):
    referer = request.headers.get('Referer')
    r = web.HTTPFound(referer or '/')
    r.set_cookie(COOKIE_NAME, '-deleted-', max_age=0, httponly=True)
    return r


########################################################################################
#   get to administrators's page
########################################################################################
@get('/admin')
def admin(request):
    if request.__user__:
        if request.__user__.admin:
            token = user_to_cookie(request.__user__, 30000)
            return {
                '__template__': 'admin.html',
                'upload_token': token
            }
        else:
            token = user_to_cookie(request.__user__, 30000)
            return {
                '__template__': 'user_backstage.html',
                'upload_token': token
            }
    logging.warning('Try get admin page without authorize')
    return web.HTTPForbidden(text="请先登录")


########################################################################################
#   edit blog
########################################################################################
@get('/edit')
async def edit(request):
    if request.__user__:
        template = 'edit.html'
        r = {}
        r['user'] = request.__user__
        token = user_to_cookie(request.__user__, 30000)
        r['upload_token'] = token
        resp = web.Response(
            body=request.app['__templating__'].get_template(
                template).render(**r).encode('utf-8'),
            content_type='text/html', charset='utf-8')
        resp.set_cookie('blog_id', '1', max_age=86400, httponly=True)
        return resp

    logging.warning('Try edit without authorize')
    return web.HTTPForbidden(text="请先登录")


########################################################################################
#   revise blog
########################################################################################
@get('/revise')
async def revise_blog(request, blog_id):
    if request.__user__:
        uid = request.__user__.id
        blog = await Blog.pk_find(blog_id)
        if not blog:
            resp = web.Response(
                body=json.dumps({'message': '您的文件消失在了火星'}, ensure_ascii=False,
                                default=lambda o: o.__dict__).encode('utf-8'),
                content_type='application/json', charset='utf-8')
            return resp
        if blog.uid != uid and not request.__user__.admin:
            resp = web.Response(
                body=json.dumps({'message': '这似乎不是您的文章'}, ensure_ascii=False,
                                default=lambda o: o.__dict__).encode('utf-8'),
                content_type='application/json', charset='utf-8')
            return resp
        template = 'edit.html'
        blog.content = blog.content.replace('\n', '\\n')
        blog.content = blog.content.replace('"', '\\"')
        blog.content = blog.content.replace("'", "\\'")
        blog.name = blog.name.replace('\n', '\\n')
        blog.name = blog.name.replace('"', '\\"')
        blog.name = blog.name.replace("'", "\\'")
        r = {'blog': blog}
        r['user'] = request.__user__
        r['upload_token'] = user_to_cookie(request.__user__, 6000)
        resp = web.Response(
            body=request.app['__templating__'].get_template(
                template).render(**r).encode('utf-8'),
            content_type='text/html', charset='utf-8')
        resp.set_cookie('blog_id', blog.id, max_age=86400, httponly=True)
        return resp

    logging.warning('Try revise without authorize')
    return web.HTTPForbidden(text="请先登录")


########################################################################################
#   release blog
########################################################################################
@post('/api/release')
async def release(request, name, content, content_html, classfication):
    if request.__user__:
        uid = request.__user__.id
        blog_id = request.cookies.get('blog_id')
        if not blog_id:
            raise APIPermissionError('您的cookie已过期')
        if not content_html:
            return web.json_response({'message': '内容不能为空'})
        et = etree.HTML(content_html)
        summary = ''
        ss = et.xpath('//text()')
        if not classfication:
            classfication = 'main'
        for s in ss:
            summary = summary + s.replace('\n', '')
            summary = summary + ' '
            if len(summary) >= 80:
                break
        if len(summary) > 100:
            summary = summary[0:80]
        summary += '...'
        if blog_id == '1':
            blog = Blog(name=name, uid=uid, content=content,
                        content_html=content_html, classfication=classfication,
                        summary=summary)
            # blog = Blog(name=name, summary=summary, content=content, content_html=content_html,
            #             classfication=classfication)
            r = await blog.save()
            resp = web.Response(content_type='application/json')
            resp.set_cookie('blog_id', '-deleted-',
                            max_age=0, httponly=True)
            return resp
        else:
            blog = await Blog.pk_find(blog_id)
            if not blog:
                resp = web.json_response({'message': '您的文件消失在了火星'})
                resp.set_cookie('blog_id', '-deleted-',
                                max_age=0, httponly=True)
                return resp
            if blog.uid != uid:
                resp = web.Response(
                    body=json.dumps({'message': '这似乎不是您的文章'}, ensure_ascii=False,
                                    default=lambda o: o.__dict__).encode('utf-8'),
                    content_type='application/json', charset='utf-8')
                return resp
            else:
                blog.name = name
                blog.summary = summary
                blog.content = content
                blog.content_html = content_html
                blog.classfication = classfication
                blog.revised_at = time.time()
                await blog.save()
                resp = web.Response(content_type='application/json')
                resp.set_cookie('blog_id', '-deleted-',
                                max_age=0, httponly=True)
                return resp

    logging.warning('Try release without authorize')
    return web.HTTPForbidden(text="请先登录")


########################################################################################
#   in administrator's page to get blog list
########################################################################################
item_per_page_manage = 20


@get('/api/blogmanage')
async def blog_manage(request, page=1):
    if request.__user__:
        if request.__user__.admin:
            page = int(page)
            total = (await Blog.aggregate(t=Count()))['t']
            page_count = total // item_per_page_manage + \
                         (1 if total % item_per_page > 0 else 0)
            if page < 1 or page > page_count:
                page = 1
            blogs = await Blog.order_by('-created_at'). \
                limit((page - 1) * item_per_page_manage, item_per_page_manage).find()
            # blogs = await Blog.FindAll(orderBy='revised_at desc',
            #                            limit=((page - 1) * item_per_page_manage, item_per_page_manage))
            return {
                'total_item': total,
                'blogdata': [
                    {'name': blog.name,
                     'date': strftime('%Y-%m-%d', time.localtime(blog.revised_at)),
                     'hot': blog.page_view,
                     'id': blog.id}
                    for blog in blogs
                ]
            }
        else:
            uid = request.__user__.id
            page = int(page)
            total = (await Blog.filter(uid=uid).aggregate(t=Count()))['t']
            page_count = total // item_per_page_manage + \
                         (1 if total % item_per_page > 0 else 0)
            if page < 1 or page > page_count:
                page = 1
            blogs = await Blog.filter(uid=uid).order_by('-created_at'). \
                limit((page - 1) * item_per_page_manage, item_per_page_manage).find()
            # blogs = await Blog.FindAll(orderBy='revised_at desc',
            #                            limit=((page - 1) * item_per_page_manage, item_per_page_manage))
            return {
                'total_item': total,
                'blogdata': [
                    {'name': blog.name,
                     'date': strftime('%Y-%m-%d', time.localtime(blog.revised_at)),
                     'hot': blog.page_view,
                     'id': blog.id}
                    for blog in blogs
                ]
            }

    logging.warning('Try blogmanage without authorize')
    return web.HTTPForbidden(text="请先登录")


########################################################################################
#   in administrator's page to get comment list
########################################################################################
@get('/api/commentmanage')
async def comment_manage(request, page=1):
    if request.__user__:
        if request.__user__.admin:
            page = int(page)
            total = (await Comment.aggregate(t=Count()))['t']
            page_count = total // item_per_page_manage + \
                         (1 if total % item_per_page > 0 else 0)
            if page < 1 or page > page_count:
                page = 1
            comments = await Comment.order_by('-created_at'). \
                limit((page - 1) * item_per_page_manage, item_per_page_manage).find()
            # comments = await Comment.FindAll(orderBy='created_at desc',
            #                                  limit=((page - 1) * item_per_page_manage, item_per_page_manage))
            return {
                'total_item': total,
                'commentdata': [
                    {'content': comment.content,
                     'date': strftime('%Y-%m-%d', time.localtime(comment.created_at)),
                     'comefrom': comment.blog_name,
                     'id': comment.id}
                    for comment in comments
                ]
            }
        else:
            uid = request.__user__.id
            page = int(page)
            total = (await Comment.filter(user_id=uid).aggregate(t=Count()))['t']
            page_count = total // item_per_page_manage + \
                         (1 if total % item_per_page > 0 else 0)
            if page < 1 or page > page_count:
                page = 1
            comments = await Comment.filter(user_id=uid).order_by('-created_at'). \
                limit((page - 1) * item_per_page_manage, item_per_page_manage).find()
            # comments = await Comment.FindAll(orderBy='created_at desc',
            #                                  limit=((page - 1) * item_per_page_manage, item_per_page_manage))
            return {
                'total_item': total,
                'commentdata': [
                    {'content': comment.content,
                     'date': strftime('%Y-%m-%d', time.localtime(comment.created_at)),
                     'comefrom': comment.blog_name,
                     'id': comment.id}
                    for comment in comments
                ]
            }
    logging.warning('Try commentmanage without authorize')
    return web.HTTPForbidden(text="请先登录")


########################################################################################
#   in administrator's page to get user list
########################################################################################
@get('/api/usermanage')
async def user_manage(request, page=1):
    if request.__user__:
        if request.__user__.admin:
            page = int(page)
            total = (await User.aggregate(t=Count()))['t']
            page_count = total // item_per_page_manage + \
                         (1 if total % item_per_page > 0 else 0)
            if page < 1 or page > page_count:
                page = 1
            # users = await User.FindAll(orderBy='created_at desc',
            #                            limit=((page - 1) * item_per_page_manage, item_per_page_manage))
            users = await User.order_by('-created_at'). \
                limit((page - 1) * item_per_page_manage, item_per_page_manage).find()
            return {
                'total_item': total,
                'userdata': [
                    {'name': user.name,
                     'created_at': strftime('%Y-%m-%d', time.localtime(user.created_at))}
                    for user in users
                ]
            }
    logging.warning('Try usermanage without authorize')
    return web.HTTPForbidden(text="请先登录")


########################################################################################
#   in administrator's page delete a blog or comment
########################################################################################
@get('/api/delete')
async def delete(request, id, operation):
    if request.__user__:
        if request.__user__.admin:
            if operation == 'blog':
                r = await Blog.filter(id=id).delete()
                await Comment.filter(blog_id=id).delete()
                # TODO删除相关点赞
                return web.Response(content_type='application/json')
            elif operation == 'comment':
                delete_id = [id]
                parent_comment = await Comment.pk_find(id)
                # parent_comment是要删除的评论，被叫做父评论是因为要一并删除他的全部子评论
                if not parent_comment:
                    return web.HTTPNotFound()
                if parent_comment.parent_id == '0':
                    # comments = await Comment.FindAll(where='parent_id', args=id)
                    comments = await Comment.filter(parent_id=id).find()
                    for comment in comments:
                        delete_id.append(comment.id)
                        await comment.remove()
                await parent_comment.remove()
                return web.json_response(delete_id)
            else:
                logging.warning('Wrong Delete Method')
                return web.HTTPForbidden()
        else:
            uid = request.__user__.id
            if operation == 'blog':
                blog = await Blog.pk_find(id)
                if uid != blog.uid:
                    return web.HTTPForbidden(text="请先登录")
                await blog.remove()
                await Comment.filter(blog_id=id).delete()
                # TODO删除相关点赞
                return web.Response(content_type='application/json')
            elif operation == 'comment':
                delete_id = [id]
                parent_comment = await Comment.pk_find(id)
                # parent_comment是要删除的评论，被叫做父评论是因为要一并删除他的全部子评论
                if not parent_comment:
                    return web.HTTPNotFound()
                elif parent_comment.user_id != uid:
                    return web.HTTPForbidden()
                if parent_comment.parent_id == '0':
                    # comments = await Comment.FindAll(where='parent_id', args=id)
                    comments = await Comment.filter(parent_id=id).find()
                    for comment in comments:
                        delete_id.append(comment.id)
                        await comment.remove()
                await parent_comment.remove()
                return web.json_response(delete_id)
            else:
                logging.warning('Wrong Delete Method')
                return web.HTTPForbidden()

    logging.warning('Try delete without permission')
    return web.HTTPForbidden(text="请先登录")


########################################################################################
#   in administrator's page to reply a comment
########################################################################################
@post('/api/manage_reply')
async def manage_reply(request, reply_to_id, content):
    if request.__user__:
        reply_to_comment = await Comment.pk_find(reply_to_id)
        comment = Comment(blog_id=reply_to_comment.blog_id,
                          user_id=request.__user__.id,
                          user_name=request.__user__.name,
                          reply_to=reply_to_comment.user_name,
                          parent_id=reply_to_id if reply_to_comment.parent_id == '0' else reply_to_comment.parent_id,
                          content=content,
                          blog_name=reply_to_comment.blog_name)
        await comment.save()
        return web.json_response()
    logging.warning('Try reply without permission')
    return web.HTTPForbidden(text="请先登录")


########################################################################################
#   photo upload
########################################################################################
@file_post('/api/upload')
async def file_upload(reader):
    a = await reader.next()
    upload_token = await a.read_chunk()
    upload_token = upload_token.decode('utf-8')
    user = await cookie_to_user(upload_token)
    if user:
        field = await reader.next()
        filename = next_id() + '.' + field.filename.split('.')[-1]
        size = 0
        current_dir = os.path.abspath(os.path.dirname(__file__))
        parent_path = os.path.dirname(current_dir)
        with open(os.path.join('static/files/upload', filename), 'wb') as f:
            while True:
                chunk = await field.read_chunk()
                if not chunk:
                    break
                size += len(chunk)
                f.write(chunk)
        return os.path.join('static/files/upload/', filename)
    logging.warning('Try uploadphoto without permission')
    return web.HTTPForbidden(text="请先登录")


@get('/api/shicichange')
async def shicichange(request):
    if request.__user__:
        if request.__user__.admin:
            os.system('python3 ./shici_change.py')
            return 'ok'
    return web.HTTPForbidden(text="请先登录")
