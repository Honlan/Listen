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

# 用户页
@app.route('/user')
def user():
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

		return render_template('user.html', user=user, data=data, forward=forward, status=status, message=message)

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
	cursor.execute("update forward set content=%s where id=%s", [json.dumps(data), cid])
	closedb(db,cursor)
	return json.dumps({'result': 'ok'})

# 删除群聊转发
@app.route('/forward_delete', methods=['POST'])
def forward_delete():
	data = request.form
	(db,cursor) = connectdb()
	cursor.execute("delete from forward where id=%s", [data['cid']])
	closedb(db,cursor)
	return json.dumps({'result': 'ok'})

# 运行应用
@app.route('/start', methods=['POST'])
def start():
	uid = str(session['uid'])
	qrcode = 'data/' + uid + '/qrcode' + str(int(time.time())) + '.png'
	new_chat.apply_async(args=[session['uid'], 'static/' + qrcode])
	return json.dumps({'result': 'ok', 'qrcode': qrcode})

@celery.task
def new_chat(uid, qrcode):
	uid = str(uid)
	if not os.path.exists('static/data/' + uid + '/'):
		os.makedirs('static/data/' + uid + '/')
		os.makedirs('static/data/' + uid + '/imgs/')
		os.makedirs('static/data/' + uid + '/videos/')
		os.makedirs('static/data/' + uid + '/files/')

	itchat.auto_login(hotReload=True, 
		statusStorageDir='static/data/' + uid + '/itchat.pkl',
		picDir=qrcode)

	(db,cursor) = connectdb()
	cursor.execute("insert into status(uid, event, timestamp) values(%s, %s, %s)", [uid, 'start', int(time.time())])
	cursor.execute("update user set status=%s where id=%s", ['start', uid])
	closedb(db,cursor)

	@itchat.msg_register(TEXT)
	def reply(msg):
		return msg['Text']

	itchat.run()

	(db,cursor) = connectdb()
	cursor.execute("insert into status(uid, event, timestamp) values(%s, %s, %s)", [uid, 'stop', int(time.time())])
	cursor.execute("update user set status=%s where id=%s", ['stop', uid])
	closedb(db,cursor)

	return

# 获取二维码
@app.route('/qrcode', methods=['POST'])
def qrcode():
	data = request.form
	uid = str(session['uid'])
	while True:
		time.sleep(1)
		if os.path.exists('static/' + data['qrcode']):
			break
	time.sleep(1)
	return json.dumps({'result': 'ok'})

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

if __name__ == '__main__':
	app.run(debug=True)