Celery Linux Daemon Demo
===

Linux平台下以守护进程方式运行Celery任务Demo<br/>

Environment
==========
Python 2.7

Usage
====
1. 启动服务<br/>
`supervisord -c supervisord.conf`

2. 查看服务状态<br/>
`supervisorctl -c supervisord.conf status`

3. 查看服务日志<br/>
`tail -f test.log`

4. 停止服务<br/>
`supervisorctl -c supervisord.conf shutdown`

Installation
============
1. `git clone https://github.com/Wayde2014/celery-linux-daemon-demo`<br/>
2. `pip install -r requirements.txt`<br/>