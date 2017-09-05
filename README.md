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

## 编辑wsgi

## 编辑Apache conf文件

## 安装mod_wsgi

```
apt-get install libapache2-mod-wsgi
```

## 重启Apache

## TODO

## 注意

- 修改`wxpy/api/messages/message.py`中的`html = HTMLParser()`，并注释`itchat/components/login.py`中的`utils.print_qr(picDir)`