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
				cursor.execute("insert into user(username, email, password, reg_time, avatar, last_login) values(%s, %s, %s, %s, %s, %s)", [data['username'], data['email'], password.hexdigest(), int(time.time()), 'img/avatar/man.png', int(time.time())])
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

# 我的轻听
@app.route('/listen')
def listen():
	user = session_info()
	if not 'uid' in session:
		return redirect(url_for('index'))
	else:
		(db,cursor) = connectdb()
		cursor.execute("select * from user where id=%s", [user['uid']])
		data = cursor.fetchone()
		if data['records'] == '':
			data['records'] = []
		else:
			data['records'] = data['records'].split('^')
		if data['members'] == '':
			data['members'] = []
		else:
			data['members'] = data['members'].split('^')
		data['last_login'] = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(float(data['last_login'])))
		status = data['status']
		cursor.execute("select * from forward where uid=%s", [user['uid']])
		forward = cursor.fetchall()
		forward = [[item['id'], [[key, value] for key, value in json.loads(item['content']).items()]] for item in forward]

		data['forward'] = forward

		cursor.execute("select * from chatroom where uid=%s",[user['uid']])
		chatrooms = cursor.fetchall()

		data['record_chatrooms'] = []
		data['member_chatrooms'] = []
		for item in chatrooms:
			if not item['nick_name'] in data['records']:
				data['record_chatrooms'].append(item)
			if not item['nick_name'] in data['members']:
				data['member_chatrooms'].append(item)
		data['group_chatrooms'] = chatrooms

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

		return render_template('listen.html', user=user, data=data, status=status, message=message)

# 添加群聊监测
@app.route('/record_add', methods=['POST'])
def record_add():
	data = request.form
	(db,cursor) = connectdb()
	cursor.execute("select records from user where id=%s", [session['uid']])
	records = cursor.fetchone()['records']
	if records == '':
		records = data['record']
	else:
		records = records + '^' + data['record']
	cursor.execute("update user set records=%s where id=%s", [records, session['uid']])
	closedb(db,cursor)
	return json.dumps({'result': 'ok'})

# 删除群聊监测
@app.route('/record_delete', methods=['POST'])
def record_delete():
	data = request.form
	(db,cursor) = connectdb()
	cursor.execute("select records from user where id=%s", [session['uid']])
	records = cursor.fetchone()['records']
	records = records.split('^')
	tmp = []
	for item in records:
		if not item == data['record']:
			tmp.append(item)
	if len(item) == 0:
		records = ''
	else:
		records = '^'.join(tmp)
	cursor.execute("update user set records=%s where id=%s", [records, session['uid']])
	closedb(db,cursor)
	return json.dumps({'result': 'ok'})

# 添加群成员分析
@app.route('/member_add', methods=['POST'])
def member_add():
	data = request.form
	(db,cursor) = connectdb()
	cursor.execute("select members from user where id=%s", [session['uid']])
	members = cursor.fetchone()['members']
	if members == '':
		members = data['member']
	else:
		members = members + '^' + data['member']
	cursor.execute("update user set members=%s where id=%s", [members, session['uid']])
	closedb(db,cursor)
	return json.dumps({'result': 'ok'})

# 删除群成员分析
@app.route('/member_delete', methods=['POST'])
def member_delete():
	data = request.form
	(db,cursor) = connectdb()
	cursor.execute("select members from user where id=%s", [session['uid']])
	members = cursor.fetchone()['members']
	members = members.split('^')
	tmp = []
	for item in members:
		if not item == data['member']:
			tmp.append(item)
	if len(item) == 0:
		members = ''
	else:
		members = '^'.join(tmp)
	cursor.execute("update user set members=%s where id=%s", [members, session['uid']])
	closedb(db,cursor)
	return json.dumps({'result': 'ok'})

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

# 数据统计
@app.route('/stat')
def stat():
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
		cursor.execute("select * from message where uid=%s", [data['id']])
		messages = cursor.fetchall()
		data_html['total'] = len(messages)

		data_js['plot1'] = {'xAxis': [], 'legend': [], 'data': {}}
		records = data['records']
		if records == '':
			records = []
		else:
			records = records.split('^')
		for item in messages:
			if not item['chatroom'] in records:
				pass

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

		cursor.execute("select * from friend where uid=%s",[user['uid']])
		friends = cursor.fetchall()
		cursor.execute("select * from chatroom where uid=%s",[user['uid']])
		chatrooms = cursor.fetchall()

		data_html['friend_count'] = len(friends)
		if len(friends) > 20:
			data_html['friends'] = friends[:20]
		else:
			data_html['friends'] = friends

		data_js['plot2'] = {'男': 0, '女': 0, '未知': 0}
		for item in friends:
			if int(item['sex']) == 1:
				data_js['plot2']['男'] += 1
			elif int(item['sex']) == 2:
				data_js['plot2']['女'] += 1
			else:
				data_js['plot2']['未知'] += 1
		data_js['plot2'] = [{'name': key, 'value': value} for key, value in data_js['plot2'].items()]

		data_html['chatroom_count'] = len(chatrooms)
		if len(chatrooms) > 20:
			data_html['chatrooms'] = chatrooms[:20]
		else:
			data_html['chatrooms'] = chatrooms

		data_js['plot3'] = {}
		for item in friends:
			if item['province'] == '':
				item['province'] = '未知'
			if not item['province'] in data_js['plot3']:
				data_js['plot3'][item['province']] = 0
			data_js['plot3'][item['province']] += 1
		other = 0
		for key, value in data_js['plot3'].items():
			if value < 10:
				other += value
				del data_js['plot3'][key]
		data_js['plot3']['其他'] = other
		data_js['plot3'] = sorted(data_js['plot3'].items(), key=lambda x:x[1], reverse=True)
		data_js['plot3'] = {'x': [d[0] for d in data_js['plot3']], 'y': [d[1] for d in data_js['plot3']]}

		provinces = ['北京', '天津', '上海', '重庆', '河北', '河南', '云南', '辽宁', '黑龙江', '湖南', '安徽', '山东', '新疆', '江苏', '浙江', '江西', '湖北', '广西', '甘肃', '山西', '内蒙古', '陕西', '吉林', '福建', '贵州', '广东', '青海', '西藏', '四川', '宁夏', '海南', '台湾', '香港', '澳门']

		data_js['plot4'] = []
		for i in range(0, len(data_js['plot3']['x'])):
			if data_js['plot3']['x'][i] in provinces:
				data_js['plot4'].append({'name': data_js['plot3']['x'][i], 'value': data_js['plot3']['y'][i]})
		if len(data_js['plot4']) > 0:
			data_js['plot4_max'] = data_js['plot4'][0]['value']
		else:
			data_js['plot4_max'] = 100

		cursor.execute("select signature_cloud from user where id=%s", [user['uid']])
		data_js['plot5'] = json.loads(cursor.fetchone()['signature_cloud'])

		closedb(db,cursor)
		return render_template('stat.html', user=user, data=data, data_html=data_html, data_js=json.dumps(data_js))

# 运行应用
@app.route('/start', methods=['POST'])
def start():
	uid = str(session['uid'])
	qrcode = FILE_PREFIX + 'static/data/' + uid + '/qrcode' + str(int(time.time())) + '.png'
	Popen('python ' + FILE_PREFIX + 'new_wxchat.py ' + str(session['uid']) + ' ' + qrcode + ' ' + FILE_PREFIX, shell=True)
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

# 检查是否已经扫码并确认
@app.route('/confirm', methods=['POST'])
def confirm():
	(db,cursor) = connectdb()
	while True:
		time.sleep(1)
		cursor.execute("select status from user where id=%s", [session['uid']])
		status = cursor.fetchone()['status']
		if status == 'confirm':
			break
	closedb(db,cursor)
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
	cursor.execute("select avatar from user where id=%s", [session['uid']])
	session['avatar'] = cursor.fetchone()['avatar']
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