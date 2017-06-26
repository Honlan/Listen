# Listen

## 编辑配置文件

```
cp config_sample.py config.py
```

## 安装虚环境

```
virtualenv venv
. venv/bin/activate
```

## 安装python包

```
pip install -r requirements.txt
```

## 新建数据目录

```
mkdir static/data/
```

## 安装Redis

```
cd ~
wget http://download.redis.io/releases/redis-3.2.9.tar.gz
tar xzf redis-3.2.9.tar.gz
cd redis-3.2.9
make
```

## 启动Redis

```
src/redis-server
```

## 启动celery

```
celery worker -A run.celery --loglevel info
```

## 编辑wsgi

## 编辑Apache conf文件

## 安装mod_wsgi

```
apt-get install libapache2-mod-wsgi
```

## 修改itchat代码，不输出图片

## 重启Apache

## TODO

掉线提醒
加好友后自动邀请入群