#!/usr/bin/env python
# coding:utf8

import time
import sys
reload(sys)
sys.setdefaultencoding( "utf8" )
import json
import itchat
from itchat.content import *
import os

from run import app, connectdb, closedb, Mail, Message

uid = sys.argv[1]
qrcode = sys.argv[2]
FILE_PREFIX = sys.argv[3]

# 上传数据
def upload_msg(uid, username, chatroom, msg_type, content, url):
	(db,cursor) = connectdb()
	cursor.execute("insert into message(uid, username, chatroom, msg_type, content, url, timestamp) values(%s, %s, %s, %s, %s, %s, %s)", [uid, username, chatroom, msg_type, content, url, int(time.time())])
	closedb(db,cursor)

(db,cursor) = connectdb()
cursor.execute("select content from forward where uid=%s", [uid])
forward = cursor.fetchall()
forward = [json.loads(d['content']) for d in forward]

cursor.execute("select * from user where id=%s", [uid])
user = cursor.fetchone()
closedb(db,cursor)

if not os.path.exists(FILE_PREFIX + 'static/data/' + uid + '/'):
	os.makedirs(FILE_PREFIX + 'static/data/' + uid + '/')
	os.makedirs(FILE_PREFIX + 'static/data/' + uid + '/imgs/')
	os.makedirs(FILE_PREFIX + 'static/data/' + uid + '/videos/')
	os.makedirs(FILE_PREFIX + 'static/data/' + uid + '/files/')

@itchat.msg_register([TEXT, MAP, CARD, NOTE, SHARING], isGroupChat=False)
def text_reply(msg):
	itchat.send('你好', msg['FromUserName'])

@itchat.msg_register([PICTURE, RECORDING, ATTACHMENT, VIDEO], isGroupChat=False)
def download_files(msg):
	itchat.send('你好', msg['FromUserName'])

@itchat.msg_register(FRIENDS)
def add_friend(msg):
	itchat.add_friend(**msg['Text'])
	for key, value in chatrooms_dict.items():
		if key == user['invite']:
			itchat.add_member_into_chatroom(value, [msg['RecommendInfo']], useInvitation=True)
			break
    
@itchat.msg_register([TEXT, SHARING, NOTE], isGroupChat=True)
def group_reply_text(msg):
	chatroom_id = msg['FromUserName']
	chatroom_nickname = ''
	username = msg['ActualNickName']

	cell_id = -1
	for x in xrange(0, len(forward)):
		item = forward[x]
		for key in item.keys():
			if chatrooms_dict[key] == chatroom_id:
				chatroom_nickname = item[key]
				cell_id = x
	if cell_id == -1:
		return

	# 上传数据
	if msg['Type'] == TEXT:
		upload_msg(uid, username, chatroom_nickname, msg['Type'], msg['Content'], '')
	elif msg['Type'] == SHARING:
		upload_msg(uid, username, chatroom_nickname, msg['Type'], msg['Text'], msg['Url'])

	if msg['Type'] == TEXT:
		for key in forward[cell_id].keys():
			if not chatrooms_dict[key] == chatroom_id:
				itchat.send('%s\n%s' % (chatroom_nickname + '-' + username, msg['Content']), chatrooms_dict[key])
	elif msg['Type'] == SHARING:
		for key in forward[cell_id].keys():
			if not chatrooms_dict[key] == chatroom_id:
				itchat.send('%s\n%s\n%s' % (chatroom_nickname + '-' + username, msg['Text'], msg['Url']), chatrooms_dict[key])
	elif msg['Type'] == NOTE and msg['Text'][-5:] == u'加入了群聊':
		idx = []
		start = 0
		while msg['Text'].find('"', start) >= 0:
			t = msg['Text'].find('"', start)
			start = t + 1
			idx.append(t)
		itchat.send('%s' % (user['welcome'] % msg['Text'][idx[-2] + 1:idx[-1]]), chatroom_id)
   
@itchat.msg_register([PICTURE, ATTACHMENT, VIDEO], isGroupChat=True)
def group_reply_media(msg):
	chatroom_id = msg['FromUserName']
	chatroom_nickname = ''
	username = msg['ActualNickName']

	cell_id = -1
	for x in xrange(0, len(forward)):
		item = forward[x]
		for key in item.keys():
			if chatrooms_dict[key] == chatroom_id:
				chatroom_nickname = item[key]
				cell_id = x
	if cell_id == -1:
		return

	if msg['FileName'][-4:] == '.gif':
		return

	if msg['Type'] == 'Picture':
		msg['FileName'] = FILE_PREFIX + 'static/data/' + uid + '/imgs/' + msg['FileName']
	elif msg['Type'] == 'Video':
		msg['FileName'] = FILE_PREFIX + 'static/data/' + uid + '/videos/' + msg['FileName']
	else:
		msg['FileName'] = FILE_PREFIX + 'static/data/' + uid + '/files/' + msg['FileName']

	upload_msg(uid, username, chatroom_nickname, msg['Type'], '', msg['FileName'])

	msg['Text'](msg['FileName'])
	for key in forward[cell_id].keys():
		if not chatrooms_dict[key] == chatroom_id:
			itchat.send('@%s@%s' % ({'Picture': 'img', 'Video': 'vid'}.get(msg['Type'], 'fil'), msg['FileName']), chatrooms_dict[key])

itchat.auto_login(hotReload=True, statusStorageDir=FILE_PREFIX + 'static/data/' + uid + '/itchat.pkl', picDir=qrcode)

chatrooms = itchat.get_chatrooms(update=True, contactOnly=False)
chatrooms_dict = {c['NickName']: c['UserName'] for c in chatrooms}

(db,cursor) = connectdb()
cursor.execute("insert into status(uid, event, timestamp) values(%s, %s, %s)", [uid, 'start', int(time.time())])
cursor.execute("update user set status=%s where id=%s", ['start', uid])
closedb(db,cursor)

itchat.run()

(db,cursor) = connectdb()
cursor.execute("insert into status(uid, event, timestamp) values(%s, %s, %s)", [uid, 'stop', int(time.time())])
cursor.execute("update user set status=%s where id=%s", ['stop', uid])
closedb(db,cursor)

if not user['reminder'] == '':
	with app.app_context():
		mail = Mail(app)
		m = Message('机器人掉线提醒', recipients=[user['reminder']])
		m.body = '你的微信机器人已掉线，请重新登录'
		mail.send(m)