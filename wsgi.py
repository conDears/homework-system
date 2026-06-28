"""
PythonAnywhere 部署入口
部署步骤：
1. 在 PythonAnywhere 创建 Web App，选择 Flask
2. 上传项目文件
3. 在 Web 设置中修改 WSGI 文件路径指向此文件
4. 修改 Database 路径（在 app.py 中）
"""

import sys
import os

# 添加项目路径
project_home = os.path.dirname(os.path.abspath(__file__))
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# 设置数据库路径（PythonAnywhere 上的绝对路径）
# 格式：/home/你的用户名/homework-system/instance/homework.db
username = 'ykl'  # 改成你的 PythonAnywhere 用户名
db_path = os.path.join('/home', username, 'homework-system', 'instance', 'homework.db')
os.environ['DATABASE_PATH'] = db_path

from app import app as application
