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
import itchat

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

@app.route('/')
def index():
	newInstance = itchat.new_instance()
	newInstance.auto_login(hotReload=True, statusStorageDir='newInstance.pkl')

	@newInstance.msg_register(TEXT)
	def reply(msg):
		return msg['Text']

	newInstance.run()
	
	return render_template('index.html')

if __name__ == '__main__':
	app.run(debug=True)