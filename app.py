"""
在线作业系统 - 快速原型
Flask + SQLite + SQLite 文件数据库
运行: python app.py
访问: http://localhost:5000
"""

from datetime import datetime
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user,
    login_required, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev-secret-key-change-in-production'

# 支持 PythonAnywhere 部署（通过环境变量设置数据库路径）
import os
db_path = os.environ.get('DATABASE_PATH', 'sqlite:///homework.db')
if not db_path.startswith('sqlite:///'):
    db_path = 'sqlite:///' + db_path
app.config['SQLALCHEMY_DATABASE_URI'] = db_path
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = '请先登录'


# ==================== 数据库模型 ====================

class User(UserMixin, db.Model):
    """用户表 - 老师/学生"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'teacher' 或 'student'
    created_at = db.Column(db.DateTime, default=datetime.now)

    assignments = db.relationship('Assignment', backref='teacher', lazy=True)
    submissions = db.relationship('Submission', backref='student', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Assignment(db.Model):
    """作业表"""
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    deadline = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.now)
    status = db.Column(db.String(20), default='published')  # draft / published / closed

    submissions = db.relationship('Submission', backref='assignment', lazy=True)


class Submission(db.Model):
    """作业提交表"""
    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey('assignment.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    submitted_at = db.Column(db.DateTime, default=datetime.now)
    status = db.Column(db.String(20), default='submitted')  # submitted / graded
    grade = db.Column(db.String(50))  # 分数/评语


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ==================== 权限装饰器 ====================

def teacher_required(f):
    """只允许老师访问"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if current_user.role != 'teacher':
            flash('只有老师可以访问此页面')
            return redirect(url_for('student_dashboard'))
        return f(*args, **kwargs)
    return decorated


def student_required(f):
    """只允许学生访问"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if current_user.role != 'student':
            flash('只有学生可以访问此页面')
            return redirect(url_for('teacher_dashboard'))
        return f(*args, **kwargs)
    return decorated


# ==================== 认证路由 ====================

@app.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.role == 'teacher':
            return redirect(url_for('teacher_dashboard'))
        return redirect(url_for('student_dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user)
            flash(f'欢迎回来，{username}！')
            if user.role == 'teacher':
                return redirect(url_for('teacher_dashboard'))
            return redirect(url_for('student_dashboard'))
        flash('用户名或密码错误')

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']

        if User.query.filter_by(username=username).first():
            flash('用户名已存在')
            return render_template('register.html')

        user = User(username=username, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash('注册成功，请登录')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('已退出登录')
    return redirect(url_for('login'))


# ==================== 老师端路由 ====================

@app.route('/teacher')
@login_required
@teacher_required
def teacher_dashboard():
    """老师主页 - 查看自己布置的所有作业"""
    assignments = Assignment.query.filter_by(teacher_id=current_user.id)\
        .order_by(Assignment.created_at.desc()).all()

    # 统计每个作业的提交情况
    stats = []
    for a in assignments:
        total = Submission.query.filter_by(assignment_id=a.id).count()
        stats.append({
            'assignment': a,
            'submission_count': total,
        })

    return render_template('teacher/dashboard.html', stats=stats)


@app.route('/teacher/assignment/create', methods=['GET', 'POST'])
@login_required
@teacher_required
def create_assignment():
    """布置新作业"""
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        deadline_str = request.form.get('deadline', '')

        deadline = None
        if deadline_str:
            deadline = datetime.strptime(deadline_str, '%Y-%m-%dT%H:%M')

        assignment = Assignment(
            teacher_id=current_user.id,
            title=title,
            description=description,
            deadline=deadline,
            status='published',
        )
        db.session.add(assignment)
        db.session.commit()

        flash('作业发布成功！')
        return redirect(url_for('teacher_dashboard'))

    return render_template('teacher/create_assignment.html')


@app.route('/teacher/assignment/<int:assignment_id>/submissions')
@login_required
@teacher_required
def view_submissions(assignment_id):
    """查看某次作业的所有学生提交"""
    assignment = Assignment.query.get_or_404(assignment_id)

    # 确保是作业布置老师本人
    if assignment.teacher_id != current_user.id:
        flash('无权查看')
        return redirect(url_for('teacher_dashboard'))

    submissions = Submission.query.filter_by(assignment_id=assignment_id)\
        .order_by(Submission.submitted_at.desc()).all()

    return render_template(
        'teacher/view_submissions.html',
        assignment=assignment,
        submissions=submissions,
    )


@app.route('/teacher/submission/<int:submission_id>/grade', methods=['POST'])
@login_required
@teacher_required
def grade_submission(submission_id):
    """批改作业 - 给分"""
    submission = Submission.query.get_or_404(submission_id)
    assignment = Assignment.query.get(submission.assignment_id)

    if assignment.teacher_id != current_user.id:
        flash('无权操作')
        return redirect(url_for('teacher_dashboard'))

    grade = request.form['grade']
    submission.grade = grade
    submission.status = 'graded'
    db.session.commit()

    flash('评分成功')
    return redirect(url_for('view_submissions', assignment_id=assignment.id))


@app.route('/teacher/assignment/<int:assignment_id>/close', methods=['POST'])
@login_required
@teacher_required
def close_assignment(assignment_id):
    """关闭作业（停止接收提交）"""
    assignment = Assignment.query.get_or_404(assignment_id)
    if assignment.teacher_id == current_user.id:
        assignment.status = 'closed'
        db.session.commit()
        flash('作业已关闭')
    return redirect(url_for('teacher_dashboard'))


# ==================== 学生端路由 ====================

@app.route('/student')
@login_required
@student_required
def student_dashboard():
    """学生主页 - 查看所有已发布的作业"""
    assignments = Assignment.query.filter(
        Assignment.status.in_(['published'])
    ).order_by(Assignment.created_at.desc()).all()

    # 标记哪些已经提交过
    submitted_ids = set(
        s.assignment_id for s in
        Submission.query.filter_by(student_id=current_user.id).all()
    )

    return render_template(
        'student/dashboard.html',
        assignments=assignments,
        submitted_ids=submitted_ids,
    )


@app.route('/student/assignment/<int:assignment_id>/submit', methods=['GET', 'POST'])
@login_required
@student_required
def submit_assignment(assignment_id):
    """提交作业"""
    assignment = Assignment.query.get_or_404(assignment_id)

    if assignment.status == 'closed':
        flash('该作业已关闭，无法提交')
        return redirect(url_for('student_dashboard'))

    # 检查是否已提交
    existing = Submission.query.filter_by(
        assignment_id=assignment_id,
        student_id=current_user.id
    ).first()

    if request.method == 'POST':
        content = request.form['content']

        if existing:
            # 更新已有提交
            existing.content = content
            existing.submitted_at = datetime.now()
            existing.status = 'submitted'
            existing.grade = None
            flash('作业已更新')
        else:
            submission = Submission(
                assignment_id=assignment_id,
                student_id=current_user.id,
                content=content,
            )
            db.session.add(submission)
            flash('作业提交成功！')

        db.session.commit()
        return redirect(url_for('student_dashboard'))

    return render_template(
        'student/submit.html',
        assignment=assignment,
        existing=existing,
    )


@app.route('/student/submission/<int:submission_id>')
@login_required
@student_required
def view_my_submission(submission_id):
    """查看自己的作业批改结果"""
    submission = Submission.query.get_or_404(submission_id)
    if submission.student_id != current_user.id:
        flash('无权查看')
        return redirect(url_for('student_dashboard'))

    return render_template('student/view_result.html', submission=submission)


# ==================== 初始化 ====================

def init_db():
    """初始化数据库，创建测试账号"""
    with app.app_context():
        db.create_all()

        # 如果没有用户，创建测试账号
        if not User.query.first():
            teacher = User(username='老师', role='teacher')
            teacher.set_password('123456')
            db.session.add(teacher)

            student = User(username='学生', role='student')
            student.set_password('123456')
            db.session.add(student)

            db.session.commit()
            print('[OK] 数据库已初始化，测试账号已创建：')
            print('   老师: 用户名=老师, 密码=123456')
            print('   学生: 用户名=学生, 密码=123456')


def start_ngrok_tunnel():
    """启动 ngrok 隧道，生成公网链接"""
    try:
        import ngrok
        listener = ngrok.forward(addr=5000, authtoken_from_env=True)
        url = listener.url()
        print('[OK] 公网访问地址: ' + url)
        return url
    except Exception as e:
        print('[提示] ngrok 隧道启动失败: ' + str(e))
        print('[提示] 请先设置环境变量 NGROK_AUTHTOKEN')
        print('[提示] 或者去 ngrok.com 注册获取 authtoken')
        return None


if __name__ == '__main__':
    import sys, io, os
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    init_db()
    print('[OK] 在线作业系统已启动')
    print('[OK] 本地访问: http://localhost:5000')
    print('[OK] 局域网访问: http://192.168.2.75:5000')

    # 如果设置了 authtoken，自动启动 ngrok 隧道
    if os.environ.get('NGROK_AUTHTOKEN'):
        start_ngrok_tunnel()

    print('   Ctrl+C 停止服务\n')
    app.run(debug=True, host='0.0.0.0', port=5000)
