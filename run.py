#!/usr/bin/env python
# coding:utf8

import time
import sys
reload(sys)
sys.setdefaultencoding( "utf8" )
from flask import *
from celery import Celery
import warnings
warnings.filterwarnings("ignore")
import MySQLdb
import MySQLdb.cursors
import numpy as np
from config import *
from datetime import timedelta
import itchat
from itchat.content import *
import hashlib
import os
import base64
from flask_mail import Mail, Message
import logging

app = Flask(__name__)
app.config.from_object(__name__)
app.secret_key = SECRETKEY
app.permanent_session_lifetime = timedelta(days=90)

celery = Celery(app.name, broker=CELERY_BROKER_URL)
celery.conf.update(app.config)

# 连接数据库
def connectdb():
	db = MySQLdb.connect(host=HOST, user=USER, passwd=PASSWORD, db=DATABASE, port=PORT, charset=CHARSET, cursorclass = MySQLdb.cursors.DictCursor)
	db.autocommit(True)
	cursor = db.cursor()
	return (db,cursor)

# 关闭数据库
def closedb(db,cursor):
	db.close()
	cursor.close()

# 上传数据
def upload_msg(uid, username, chatroom, msg_type, content, url):
	(db,cursor) = connectdb()
	cursor.execute("insert into message(uid, username, chatroom, msg_type, content, url, timestamp) values(%s, %s, %s, %s, %s, %s, %s)", [uid, username, chatroom, msg_type, content, url, int(time.time())])
	closedb(db,cursor)

# 获取session用户数据
def session_info():
	user = {}
	if 'uid' in session:
		user['login'] = True
		user['uid'] = session['uid']
		user['username'] = session['username']
		user['email'] = session['email']
		user['avatar'] = session['avatar']
	else:
		user['login'] = False
		user['uid'] = ''
		user['username'] = ''
		user['email'] = ''
		user['avatar'] = ''
	return user

# 处理登陆
@app.route('/login', methods=['POST'])
def login():
	data = request.form
	if data['email'] == '' or data['password'] == '':
		return json.dumps({'result': 'error', 'msg': '登陆信息不完善'})
	else:
		(db,cursor) = connectdb()
		password = hashlib.md5()
		password.update(data['password'])
		cursor.execute("select * from user where email=%s and password=%s", [data['email'], password.hexdigest()])
		user = cursor.fetchall()
		if len(user) == 0:
			closedb(db,cursor)
			return json.dumps({'result': 'error', 'msg': '邮箱或密码错误'})
		else:
			cursor.execute("update user set last_login=%s where email=%s and  password=%s", [int(time.time()), data['email'], password.hexdigest()])
			closedb(db,cursor)
			user = user[0]
			session['uid'] = user['id']
			session['username'] = user['username']
			session['email'] = user['email']
			session['avatar'] = user['avatar']
			return json.dumps({'result': 'ok', 'msg': '登陆成功'})

# 处理注册
@app.route('/register', methods=['POST'])
def register():
	data = request.form
	if data['username'] == '' or data['email'] == '' or data['password'] == '':
		return json.dumps({'result': 'error', 'msg': '注册信息不完善'})
	else:
		(db,cursor) = connectdb()
		cursor.execute("select count(*) as count from user where username=%s or email=%s", [data['username'], data['email']])
		count = cursor.fetchone()['count']
		if count > 0:
			closedb(db,cursor)
			return json.dumps({'result': 'error', 'msg': '昵称或邮箱已存在'})
		else:
			password = hashlib.md5()
			password.update(data['password'])
			cursor.execute("insert into user(username, email, password, reg_time, avatar) values(%s, %s, %s, %s, %s)", [data['username'], data['email'], password.hexdigest(), int(time.time()), url_for('static', filename='img/avatar/man.png')])
			cursor.execute("select * from user where email=%s and password=%s", [data['email'], password.hexdigest()])
			user = cursor.fetchone()
			closedb(db,cursor)
			session['uid'] = user['id']
			session['username'] = user['username']
			session['email'] = user['email']
			session['avatar'] = user['avatar']
			return json.dumps({'result': 'ok', 'msg': '注册成功'})

# 退出登录
@app.route('/logout')
def logout():
	session.pop('uid')
	session.pop('username')
	session.pop('email')
	session.pop('avatar')
	return redirect(url_for('index'))

# 首页
@app.route('/')
def index():
	user = session_info()
	return render_template('index.html', user=user)

# 用户首页
@app.route('/user')
def user():
	user = session_info()
	if not 'uid' in session:
		return redirect(url_for('index'))
	else:
		(db,cursor) = connectdb()

		cursor.execute("select * from user where id=%s", [user['uid']])
		data = cursor.fetchone()
		data['last_login'] = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(float(data['last_login'])))

		data_html = {}
		data_js = {}
		cursor.execute("select * from message where uid=%s", [session['uid']])
		messages = cursor.fetchall()
		data_html['total'] = len(messages)

		data_js['plot1'] = {'xAxis': [], 'legend': [], 'data': {}}
		for item in messages:
			if not item['msg_type'] in data_js['plot1']['xAxis']:
				data_js['plot1']['xAxis'].append(item['msg_type'])
			if not item['chatroom'] in data_js['plot1']['legend']:
				data_js['plot1']['legend'].append(item['chatroom'])

			if not data_js['plot1']['data'].has_key(item['chatroom']):
				data_js['plot1']['data'][item['chatroom']] = {}
			if not data_js['plot1']['data'][item['chatroom']].has_key(item['msg_type']):
				data_js['plot1']['data'][item['chatroom']][item['msg_type']] = 0
			data_js['plot1']['data'][item['chatroom']][item['msg_type']] += 1

		data_js['plot1']['data'] = [{'name': c, 'type': 'bar', 'data': [data_js['plot1']['data'][c][t] for t in data_js['plot1']['xAxis']]} for c in data_js['plot1']['legend']]

		closedb(db,cursor)
		return render_template('user.html', user=user, data=data, data_html=data_html, data_js=json.dumps(data_js))

# 群聊转发
@app.route('/forward')
def forward():
	user = session_info()
	if not 'uid' in session:
		return redirect(url_for('index'))
	else:
		(db,cursor) = connectdb()
		cursor.execute("select * from user where id=%s", [user['uid']])
		data = cursor.fetchone()
		cursor.execute("select * from forward where uid=%s", [user['uid']])
		forward = cursor.fetchall()
		forward = [[item['id'], [[key, value] for key, value in json.loads(item['content']).items()]] for item in forward]
		data['last_login'] = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(float(data['last_login'])))

		cursor.execute("select status from user where id=%s", [session['uid']])
		status = cursor.fetchone()['status']

		if status == 'start':
			status = True
			cursor.execute("select timestamp from status where uid=%s and event=%s order by timestamp desc limit 1", [session['uid'], 'start'])
			timestamp = cursor.fetchone()['timestamp']
			message = '运行于 ' + time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(float(timestamp)))
		else:
			status = False
			cursor.execute("select timestamp from status where uid=%s and event=%s order by timestamp desc limit 1", [session['uid'], 'stop'])
			timestamps = cursor.fetchall()
			if len(timestamps) == 0:
				message = '开始你的第一次使用'
			else:
				message = '停止于 ' + time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(float(timestamps[0]['timestamp'])))

		closedb(db,cursor)

		return render_template('forward.html', user=user, data=data, forward=forward, status=status, message=message)

# 添加群聊转发
@app.route('/forward_add', methods=['POST'])
def forward_add():
	data = request.form
	(db,cursor) = connectdb()
	cursor.execute("insert into forward(uid, content) values(%s, %s)", [session['uid'], json.dumps(data)])
	closedb(db,cursor)
	return json.dumps({'result': 'ok'})

# 编辑群聊转发
@app.route('/forward_edit', methods=['POST'])
def forward_edit():
	data = request.form
	cid = -1
	tmp = {}
	for key, value in data.items():
		if key == 'edit_cell_id':
			cid = value
		else:
			tmp[key] = value
	data = tmp
	(db,cursor) = connectdb()
	cursor.execute("update forward set content=%s where id=%s and uid=%s", [json.dumps(data), cid, session['uid']])
	closedb(db,cursor)
	return json.dumps({'result': 'ok'})

# 删除群聊转发
@app.route('/forward_delete', methods=['POST'])
def forward_delete():
	data = request.form
	(db,cursor) = connectdb()
	cursor.execute("delete from forward where id=%s and uid=%s", [data['cid'], session['uid']])
	closedb(db,cursor)
	return json.dumps({'result': 'ok'})

# 运行应用
@app.route('/start', methods=['POST'])
def start():
	uid = str(session['uid'])
	qrcode = 'data/' + uid + '/qrcode' + str(int(time.time())) + '.png'
	(db,cursor) = connectdb()
	cursor.execute("select content from forward where uid=%s", [session['uid']])
	forward = cursor.fetchall()
	forward = [json.loads(d['content']) for d in forward]
	closedb(db,cursor)
	new_chat.apply_async(args=[session['uid'], 'static/' + qrcode, forward])
	return json.dumps({'result': 'ok', 'qrcode': qrcode})

@celery.task
def new_chat(uid, qrcode, forward):
	uid = str(uid)

	(db,cursor) = connectdb()
	cursor.execute("select * from user where id=%s", [uid])
	user = cursor.fetchone()
	closedb(db,cursor)

	if not os.path.exists('static/data/' + uid + '/'):
		os.makedirs('static/data/' + uid + '/')
		os.makedirs('static/data/' + uid + '/imgs/')
		os.makedirs('static/data/' + uid + '/videos/')
		os.makedirs('static/data/' + uid + '/files/')

	@itchat.msg_register([TEXT, MAP, CARD, NOTE, SHARING], isGroupChat=False)
	def text_reply(msg):
		itchat.send('你好', msg['FromUserName'])

	@itchat.msg_register([PICTURE, RECORDING, ATTACHMENT, VIDEO], isGroupChat=False)
	def download_files(msg):
		itchat.send('你好', msg['FromUserName'])

	@itchat.msg_register(FRIENDS)
	def add_friend(msg):
		itchat.add_friend(**msg['Text'])
		# itchat.send_msg(u'你好', msg['RecommendInfo']['UserName'])
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
			msg['FileName'] = 'static/data/' + uid + '/imgs/' + msg['FileName']
		elif msg['Type'] == 'Video':
			msg['FileName'] = 'static/data/' + uid + '/videos/' + msg['FileName']
		else:
			msg['FileName'] = 'static/data/' + uid + '/files/' + msg['FileName']

		upload_msg(uid, username, chatroom_nickname, msg['Type'], '', msg['FileName'])

		msg['Text'](msg['FileName'])
		for key in forward[cell_id].keys():
			if not chatrooms_dict[key] == chatroom_id:
				itchat.send('@%s@%s' % ({'Picture': 'img', 'Video': 'vid'}.get(msg['Type'], 'fil'), msg['FileName']), chatrooms_dict[key])

	itchat.auto_login(hotReload=True, statusStorageDir='static/data/' + uid + '/itchat.pkl', picDir=qrcode)

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
	
	return

# 获取二维码
@app.route('/qrcode', methods=['POST'])
def qrcode():
	data = request.form
	uid = str(session['uid'])
	qrcode = ''
	(db,cursor) = connectdb()
	logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
	logger = logging.getLogger('tcpserver')
	qrpath = FILE_PREFIX + 'static/' + data['qrcode']
	while True:
		time.sleep(1)
		logger.warning(qrpath + ' ' + str(os.path.exists(qrpath)))
		if os.path.exists(qrpath):
			with open(qrpath, 'rb') as f:
				qrcode = base64.b64encode(f.read())
			break

		cursor.execute("select status from user where id=%s", [session['uid']])
		status = cursor.fetchone()['status']
		if status == 'start':
			break
	closedb(db,cursor)
	return json.dumps({'result': 'ok', 'qrcode': qrcode})

# 检查是否已登陆微信
@app.route('/weixin', methods=['POST'])
def weixin():
	(db,cursor) = connectdb()
	while True:
		time.sleep(1)
		cursor.execute("select status from user where id=%s", [session['uid']])
		status = cursor.fetchone()['status']
		if status == 'start':
			break
	closedb(db,cursor)
	return json.dumps({'result': 'ok'})

# 保存入群欢迎消息
@app.route('/welcome', methods=['POST'])
def welcome():
	data = request.form
	(db,cursor) = connectdb()
	cursor.execute("update user set welcome=%s where id=%s", [data['welcome'], session['uid']])
	closedb(db,cursor)
	return json.dumps({'result': 'ok'})

# 保存自动群聊邀请
@app.route('/invite', methods=['POST'])
def invite():
	data = request.form
	(db,cursor) = connectdb()
	cursor.execute("update user set invite=%s where id=%s", [data['invite'], session['uid']])
	closedb(db,cursor)
	return json.dumps({'result': 'ok'})

# 保存掉线提醒邮箱
@app.route('/reminder', methods=['POST'])
def reminder():
	data = request.form
	(db,cursor) = connectdb()
	cursor.execute("update user set reminder=%s where id=%s", [data['reminder'], session['uid']])
	closedb(db,cursor)
	return json.dumps({'result': 'ok'})

if __name__ == '__main__':
	app.run(debug=True)