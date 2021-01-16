import time, uuid
import aiomyorm
from aiomyorm import IntField,FloatField,TextField,BoolField,StringField,DoubleField
import asyncio

def next_id():
    return '%015d%s000' % (int(time.time() * 1000), uuid.uuid4().hex)


class User(aiomyorm.Model):
    __table__ = 'users'

    id = StringField(primary_key=True, default=next_id, length=50,null=False)
    email = StringField(length=50)
    passwd = StringField(length=50)
    admin = BoolField()
    name = StringField(length=50)
    img = StringField(length=50)
    created_at = DoubleField(default=time.time)


class Blog(aiomyorm.Model):
    __table__ = 'blogs'

    id = StringField(primary_key=True, default=next_id, length=50)
    uid = StringField(length=50,null=False)
    name = StringField(length=50)
    summary = StringField(length=200)
    content = TextField()
    content_html = TextField()
    created_at = DoubleField(default=time.time)
    revised_at = DoubleField(default=time.time)
    page_view = IntField()
    classfication = StringField(length=20)
    thumbs = IntField()
    top = IntField()


class Comment(aiomyorm.Model):
    __table__ = 'comments'
    id = StringField(primary_key=True, default=next_id, length=50)
    blog_id = StringField(length=50)
    user_id = StringField(length=50)
    user_name = StringField(length=50)
    user_img = StringField(length=50)
    reply_to = StringField(length=50)
    parent_id = StringField(length=50)
    content = TextField()
    created_at = DoubleField(default=time.time)
    blog_name = StringField(length=50)


class Timeline(aiomyorm.Model):
    __table__ = 'timeline'
    version = StringField(primary_key=True, length=30)
    content = StringField(length=200)
    release_time = StringField(length=30)

class ThumbUps(aiomyorm.Model):
    __table__ = 'thumbups'
    blogid_uid = StringField(primary_key=True,length=100) # 以blogid与uid组合可以唯一标记一个赞

if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(User.create_table())
    asyncio.get_event_loop().run_until_complete(Blog.create_table())
    asyncio.get_event_loop().run_until_complete(Comment.create_table())
    asyncio.get_event_loop().run_until_complete(Timeline.create_table())
    asyncio.get_event_loop().run_until_complete(ThumbUps.create_table())