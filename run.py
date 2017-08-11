#!/usr/bin/env python
# coding:utf8

import time
import sys
reload(sys)
sys.setdefaultencoding( "utf8" )
from flask import *
import warnings
warnings.filterwarnings("ignore")
import MySQLdb
import MySQLdb.cursors
import numpy as np
from config import *
from datetime import timedelta
import hashlib
import os
import base64
from flask_mail import Mail, Message
from subprocess import Popen

app = Flask(__name__)
app.config.from_object(__name__)
app.secret_key = SECRETKEY
app.permanent_session_lifetime = timedelta(days=90)

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
			cursor.execute("select count(*) as count from user")
			count = cursor.fetchone()['count']
			if count >= USER_LIMIT:
				closedb(db,cursor)
				return json.dumps({'result': 'error', 'msg': '用户数量已达内测上限'})
			else:
				password = hashlib.md5()
				password.update(data['password'])
				cursor.execute("insert into user(username, email, password, reg_time, avatar, last_login) values(%s, %s, %s, %s, %s, %s)", [data['username'], data['email'], password.hexdigest(), int(time.time()), url_for('static', filename='img/avatar/man.png'), int(time.time())])
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
	(db,cursor) = connectdb()
	stat = {}
	cursor.execute("select count(*) as count from user")
	stat['user'] = cursor.fetchone()['count']
	cursor.execute("select count(*) as count from message")
	stat['message'] = cursor.fetchone()['count']
	closedb(db,cursor)
	return render_template('index.html', user=user, stat=stat)

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

		for c in data_js['plot1']['legend']:
			if not data_js['plot1']['data'].has_key(c):
				data_js['plot1']['data'][c] = {}
			for t in data_js['plot1']['xAxis']:
				if not data_js['plot1']['data'][c].has_key(t):
					data_js['plot1']['data'][c][t] = 0
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
	qrcode = FILE_PREFIX + 'static/data/' + uid + '/qrcode' + str(int(time.time())) + '.png'
	Popen('python ' + FILE_PREFIX + 'new_chat.py ' + str(session['uid']) + ' ' + qrcode + ' ' + FILE_PREFIX, shell=True)
	return json.dumps({'result': 'ok', 'qrcode': qrcode})

# 获取二维码
@app.route('/qrcode', methods=['POST'])
def qrcode():
	data = request.form
	uid = str(session['uid'])
	qrcode = ''
	(db,cursor) = connectdb()
	qrpath = data['qrcode']
	while True:
		time.sleep(1)
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