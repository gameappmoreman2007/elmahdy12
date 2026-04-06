from flask import Flask, render_template, redirect, url_for, request, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)
app.secret_key = 'moadalah_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///moadalah.db'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024
db = SQLAlchemy(app)

os.makedirs('static/uploads', exist_ok=True)

# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(200))
    role = db.Column(db.String(20)) # 'admin' or 'student'
    active = db.Column(db.Boolean, default=True)

class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    description = db.Column(db.String(500))
    subject = db.Column(db.String(100))
    image = db.Column(db.String(100), default='📚')
    active = db.Column(db.Boolean, default=True)

class Lecture(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    description = db.Column(db.String(500))
    video_url = db.Column(db.String(300))
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'))

# Routes
@app.route('/')
def index():
    if session.get('user_id'):
        return redirect(url_for('home'))
    return render_template('index.html')

@app.route('/home')
def home():
    if not session.get('user_id'):
        return redirect(url_for('login'))
    return render_template('home.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            if not user.active:
                return "حسابك موقوف، تواصل مع الإدارة."
            session['user_id'] = user.id
            session['name'] = user.name
            session['role'] = user.role
            return redirect(url_for('home'))
        return "بيانات غير صحيحة"
    return render_template('register.html') # Login inside register template

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        admin_code = request.form.get('admin_code')
        
        role = 'student'
        if admin_code == "ADMIN123": # كود سري لإنشاء حساب أدمن
            role = 'admin'
            
        hashed_pw = generate_password_hash(password)
        new_user = User(name=name, email=email, password=hashed_pw, role=role)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/courses')
def courses():
    if not session.get('user_id'):
        return redirect(url_for('login'))
    all_courses = Course.query.filter_by(active=True).all()
    return render_template('course_detail.html', courses=all_courses, list_mode=True)

@app.route('/course/<int:id>')
def course_detail(id):
    if not session.get('user_id'):
        return redirect(url_for('login'))
    course = Course.query.get_or_404(id)
    lectures = Lecture.query.filter_by(course_id=id).all()
    return render_template('course_detail.html', course=course, lectures=lectures, list_mode=False)

@app.route('/admin')
def admin():
    if session.get('role') != 'admin':
        return redirect(url_for('home'))
    return render_template('admin.html')

@app.route('/add_course', methods=['GET', 'POST'])
def add_course():
    if session.get('role') != 'admin':
        return redirect(url_for('home'))
    if request.method == 'POST':
        title = request.form.get('title')
        desc = request.form.get('description')
        subj = request.form.get('subject')
        img = request.form.get('image')
        new_course = Course(title=title, description=desc, subject=subj, image=img)
        db.session.add(new_course)
        db.session.commit()
        return redirect(url_for('courses'))
    return render_template('add_course.html')

@app.route('/add_lecture', methods=['GET', 'POST'])
def add_lecture():
    if session.get('role') != 'admin':
        return redirect(url_for('home'))
    all_courses = Course.query.all()
    if request.method == 'POST':
        title = request.form.get('title')
        course_id = request.form.get('course_id')
        file = request.files['video']
        if file:
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            new_lec = Lecture(title=title, video_url=filename, course_id=course_id)
            db.session.add(new_lec)
            db.session.commit()
            return redirect(url_for('course_detail', id=course_id))
    return render_template('add_lecture.html', courses=all_courses)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
