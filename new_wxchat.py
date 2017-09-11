#!/usr/bin/env python
# coding:utf8

import time
import sys
reload(sys)
sys.setdefaultencoding( "utf8" )
import json
from wxpy import *
import itchat
from itchat.content import *
import os
import jieba.analyse
import numpy as np
import math
import random

from run import app, connectdb, closedb, Mail, Message

uid = sys.argv[1]
qrcode = sys.argv[2]
FILE_PREFIX = sys.argv[3]

homedir = FILE_PREFIX + 'static/data/' + uid + '/'

# 上传数据函数
def upload_msg(uid, username, puid, chatroom, msg_type, content, url):
	(db,cursor) = connectdb()
	cursor.execute("insert into message(uid, username, puid, chatroom, msg_type, content, url, timestamp) values(%s, %s, %s, %s, %s, %s, %s, %s)", [uid, username, puid, chatroom, msg_type, content, url, int(time.time())])
	closedb(db,cursor)

(db,cursor) = connectdb()

# 群聊转发
cursor.execute("select content from forward where uid=%s", [uid])
forward = cursor.fetchall()
forward = [json.loads(d['content']) for d in forward]

# 用户信息
cursor.execute("select * from user where id=%s", [uid])
user = cursor.fetchone()

# 群聊监测
records = user['records']
if records == '':
	records = []
else:
	records = records.split('^')

# 群成员分析
members = user['members']
if members == '':
	members = []
else:
	members = members.split('^')

# 创建文件夹
if not os.path.exists(homedir):
	os.makedirs(homedir)
	os.makedirs(homedir + 'imgs/')
	os.makedirs(homedir + 'videos/')
	os.makedirs(homedir + 'files/')
	os.makedirs(homedir + 'avatars/')

# 登陆
bot = Bot(cache_path=homedir + 'wxpy.pkl', 
	qr_path=qrcode, 
	qr_callback=None, 
	login_callback=None, 
	logout_callback=None)
bot.enable_puid(homedir + 'wxpy_puid.pkl')
bot.self.get_avatar(homedir + 'avatar.jpg')
bot.auto_mark_as_read = True

# 更新用户状态 confirm
cursor.execute("update user set status=%s, avatar=%s, puid=%s where id=%s", ['confirm', 'data/' + uid + '/avatar.jpg', bot.self.puid, uid])

# 好友数据
friends = bot.friends()
tmp = []
for f in friends:
	tmp.append([uid, f.puid, f.nick_name, f.remark_name, f.sex, f.province, f.city, f.signature, 'data/' + uid + '/avatars/' + str(f.puid) + '.jpg'])
cursor.execute("delete from friend where uid=%s", [uid])
cursor.executemany("insert into friend(uid, puid, nick_name, remark_name, sex, province, city, signature, avatar) values(%s, %s, %s, %s, %s, %s, %s, %s, %s)", tmp)
cursor.execute("delete from friend where nick_name=%s", [''])
content = []
for f in friends:
	if not f.signature == '':
		content.append(f.signature)
content = ' '.join(content)
tmp = ''
for x in xrange(0, len(content)):
	if content[x] >= u'\u4e00' and content[x] <= u'\u9fa5':
		tmp += content[x]
content = tmp
content = jieba.analyse.extract_tags(content, topK=100, withWeight=True, allowPOS=())
colors = ['rgb(84, 148, 191)', 'rgb(221, 107, 102)', 'rgb(230, 157, 135)', 'rgb(234, 126, 83)', 'rgb(243, 230, 162)']
if len(content) > 2:
	maxn = np.max([c[1] for c in content])
	minn = np.min([c[1] for c in content])
	if maxn == minn:
		data = [{'name': '暂无数据', 'value': 40, 'itemStyle': {'normal': {'color': colors[0]}}}]
	else:
		data = [{'name': c[0], 'value': int((c[1] - minn) / (maxn - minn) * 50), 'itemStyle': {'normal': {'color': colors[int(math.floor(random.random() * len(colors)))]}}} for c in content]
else:
	data = [{'name': '暂无数据', 'value': 40, 'itemStyle': {'normal': {'color': colors[0]}}}]
cursor.execute("update user set signature_cloud=%s where id=%s", [json.dumps(data), uid])

# 群聊数据
groups = bot.groups()
tmp = []
for g in groups:
	g.get_avatar(homedir + 'avatars/' + str(g.puid) + '.jpg')
	tmp.append([uid, g.puid, g.nick_name, g.owner.nick_name, g.is_owner, 'data/' + uid + '/avatars/' + str(g.puid) + '.jpg'])
cursor.execute("delete from chatroom where uid=%s", [uid])
cursor.executemany("insert into chatroom(uid, puid, nick_name, owner, is_owner, avatar) values(%s, %s, %s, %s, %s, %s)", tmp)
cursor.execute("delete from chatroom where nick_name=%s", [''])

# 更新用户状态 start
cursor.execute("insert into status(uid, event, timestamp) values(%s, %s, %s)", [uid, 'start', int(time.time())])
cursor.execute("update user set status=%s where id=%s", ['start', uid])

# 获取头像
cursor.execute("select avatars_timestamp from user where id=%s", [uid])
avatars_timestamp = cursor.fetchone()['avatars_timestamp']
if (avatars_timestamp == '') or (int(time.time()) - int(avatars_timestamp) > 3600 * 24 * 7):
	tmp = []
	for f in friends:
		f.get_avatar(homedir + 'avatars/' + str(f.puid) + '.jpg')
	cursor.execute("update user set avatars_timestamp=%s where id=%s", [int(time.time()), uid])

closedb(db,cursor)

# 自动添加好友
@bot.register(msg_types=FRIENDS)
def auto_accept_friends(msg):
	new_friend = bot.accept_friend(msg.card)
	new_friend.send('你好，' + new_friend.nick_name)
	if not user['invite'] == '':
		invite = ensure_one(bot.groups().search(user['invite']))
		invite.add_members(new_friend, use_invitation=True)

# TEXT SHARING NOTE MAP CARD 
# PICTURE RECORDING ATTACHMENT VIDEO
# FRIENDS

# 群聊消息处理
@bot.register(chats=Group, msg_types=[TEXT, SHARING, NOTE, PICTURE, ATTACHMENT, VIDEO])
def group_reply(msg):
	# 上传数据
	if msg.sender.nick_name in records:
		if msg.type == TEXT:
			upload_msg(uid, msg.member.nick_name, msg.member.puid, msg.sender.nick_name, msg.type, msg.text, '')
		if msg.type == SHARING:
			upload_msg(uid, msg.member.nick_name, msg.member.puid, msg.sender.nick_name, msg.type, msg.text, msg.url)
		if (msg.type in [PICTURE, ATTACHMENT, VIDEO]) and (not msg.file_name[-4:] == '.gif'):
			types = {PICTURE: 'imgs', ATTACHMENT: 'files', VIDEO: 'videos'}
			msg.get_file(homedir + types[msg.type] + '/' + msg.file_name)
			upload_msg(uid, msg.member.nick_name, msg.member.puid, msg.sender.nick_name, msg.type, msg.file_name, 'data/' + uid + '/' + types[msg.type] + '/' + msg.file_name)
		# 新人入群
		if (msg.type == NOTE) and (msg.text[-5:] == u'加入了群聊') and (not user['welcome'] == ''):
			idx = []
			start = 0
			while msg.text.find('"', start) >= 0:
				t = msg.text.find('"', start)
				start = t + 1
				idx.append(t)
			msg.reply(user['welcome'] % msg.text[idx[-2] + 1:idx[-1]])

	# 群聊转发
	if msg.type in [SHARING, ATTACHMENT]:
		for f in forward:
			flag = False
			for k, v in f.items():
				if k == msg.sender.nick_name:
					flag = True
			if flag:
				if (msg.type == ATTACHMENT) and (not os.path.exists(homedir + 'files/' + msg.file_name)):
					msg.get_file(homedir + 'files/' + msg.file_name)

				for k, v in f.items():
					if not k == msg.sender.nick_name:
						# 转发消息
						c = ensure_one(bot.groups().search(k))
						if msg.type == ATTACHMENT:
							c.send(f[msg.sender.nick_name] + '-' + msg.member.nick_name + ' 分享')
							c.send_file(homedir + 'files/' + msg.file_name)
						elif msg.type == SHARING:
							c.send(f[msg.sender.nick_name] + '-' + msg.member.nick_name + ' 分享\n' + msg.text + '\n' + msg.url)

# 运行机器人
bot.join()

(db,cursor) = connectdb()

# 更新用户状态 stop
cursor.execute("insert into status(uid, event, timestamp) values(%s, %s, %s)", [uid, 'stop', int(time.time())])
cursor.execute("update user set status=%s where id=%s", ['stop', uid])

if not user['reminder'] == '':
	with app.app_context():
		mail = Mail(app)
		m = Message('机器人掉线提醒', recipients=[user['reminder']])
		m.body = '你的微信机器人已掉线，请重新登录'
		mail.send(m)

closedb(db,cursor)