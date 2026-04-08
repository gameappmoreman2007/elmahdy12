from flask import Flask, render_template, redirect, url_for, request, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import os

app = Flask(__name__)
app.secret_key = 'moadalah_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///moadalah.db'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024
db = SQLAlchemy(app)

os.makedirs('static/uploads', exist_ok=True)

# ==================== Models ====================

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(200))
    role = db.Column(db.String(20), default='student')
    active = db.Column(db.Boolean, default=True)
    approved = db.Column(db.Boolean, default=False)
    subscribed = db.Column(db.Boolean, default=False)
    subscription_end = db.Column(db.DateTime, nullable=True)
    join_date = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)

class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    description = db.Column(db.String(500))
    subject = db.Column(db.String(100))
    image = db.Column(db.String(200), default='📚')
    active = db.Column(db.Boolean, default=True)
    is_free = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Lecture(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    description = db.Column(db.String(500))
    filename = db.Column(db.String(300))
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'))
    course = db.relationship('Course', backref='lectures')
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    message = db.Column(db.String(300))
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class SubscriptionRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    user = db.relationship('User', backref='subscription_requests')
    status = db.Column(db.String(20), default='pending')
    plan = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class JoinRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    user = db.relationship('User', backref='join_requests')
    status = db.Column(db.String(20), default='pending')
    message = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

# ==================== Helpers ====================

def is_subscribed(user):
    if user.role == 'admin':
        return True
    if user.subscribed and user.subscription_end:
        if datetime.utcnow() < user.subscription_end:
            return True
        else:
            user.subscribed = False
            db.session.commit()
    return False

def is_approved(user):
    if user.role == 'admin':
        return True
    return user.approved

# ==================== Routes ====================

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])
        phone = request.form.get('phone', '')
        admin_code = request.form.get('admin_code', '')
        message = request.form.get('message', '')

        if admin_code == 'MOADALAH2026':
            role = 'admin'
            approved = True
        else:
            role = 'student'
            approved = False

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return render_template('register.html', error='الإيميل ده مسجل قبل كده!')

        user = User(name=name, email=email, password=password, role=role, active=True, approved=approved)
        db.session.add(user)
        db.session.commit()

        if role == 'student':
            join_req = JoinRequest(user_id=user.id, message=message)
            db.session.add(join_req)
            notif = Notification(user_id=user.id, message=f'أهلاً يا {name}! 🎉 طلب تسجيلك اتبعت للأدمين وهيتراجع قريباً.')
            db.session.add(notif)
        else:
            notif = Notification(user_id=user.id, message=f'أهلاً يا {name}! 🎉 دخلت كأدمين على منصة معادلة.')
            db.session.add(notif)

        db.session.commit()
        return render_template('pending.html', name=name)
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            if not user.active:
                return render_template('login.html', error='حسابك موقوف! تواصل مع الأدمين.')
            if user.role == 'student' and not user.approved:
                return render_template('login.html', error='طلبك لسه تحت المراجعة! انتظر موافقة الأدمين.')
            session['user_id'] = user.id
            session['name'] = user.name
            session['role'] = user.role
            user.last_login = datetime.utcnow()
            db.session.commit()
            if user.role == 'admin':
                return redirect(url_for('admin'))
            return redirect(url_for('home'))
        return render_template('login.html', error='الإيميل أو كلمة السر غلط!')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/admin')
def admin():
    if session.get('role') != 'admin':
        return redirect(url_for('home'))
    return render_template('admin.html')

@app.route('/courses')
def courses():
    if not session.get('user_id'):
        return redirect(url_for('login'))
    all_courses = Course.query.filter_by(active=True).all()
    return render_template('courses.html', courses=all_courses)

@app.route('/course/<int:id>')
def course_detail(id):
    if not session.get('user_id'):
        return redirect(url_for('login'))
    course = Course.query.get_or_404(id)
    lectures = Lecture.query.filter_by(course_id=id, active=True).all()
    user = User.query.get(session['user_id'])
    subscribed = is_subscribed(user)
    return render_template('course_detail.html', course=course, lectures=lectures, subscribed=subscribed)

@app.route('/watch/<int:id>')
def watch(id):
    if not session.get('user_id'):
        return redirect(url_for('login'))
    lecture = Lecture.query.get_or_404(id)
    user = User.query.get(session['user_id'])
    if not lecture.course.is_free and not is_subscribed(user):
        return redirect(url_for('subscribe'))
    return render_template('watch.html', lecture=lecture)

@app.route('/subscribe')
def subscribe():
    if not session.get('user_id'):
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    subscribed = is_subscribed(user)
    last_request = SubscriptionRequest.query.filter_by(user_id=user.id).order_by(SubscriptionRequest.created_at.desc()).first()
    return render_template('subscribe.html', user=user, subscribed=subscribed, last_request=last_request)

@app.route('/subscribe/request', methods=['POST'])
def subscribe_request():
    if not session.get('user_id'):
        return redirect(url_for('login'))
    plan = request.form.get('plan', 'monthly')
    existing = SubscriptionRequest.query.filter_by(user_id=session['user_id'], status='pending').first()
    if not existing:
        sub_req = SubscriptionRequest(user_id=session['user_id'], plan=plan)
        db.session.add(sub_req)
        db.session.commit()
    return redirect(url_for('subscribe'))

@app.route('/profile')
def profile():
    if not session.get('user_id'):
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    subscribed = is_subscribed(user)
    notifications = Notification.query.filter_by(user_id=user.id).order_by(Notification.created_at.desc()).limit(5).all()
    return render_template('profile.html', user=user, subscribed=subscribed, notifications=notifications)

@app.route('/admin/add_course', methods=['GET', 'POST'])
def add_course():
    if session.get('role') != 'admin':
        return redirect(url_for('home'))
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        subject = request.form['subject']
        image = request.form['image']
        is_free = request.form.get('is_free') == 'on'
        course = Course(title=title, description=description, subject=subject, image=image, is_free=is_free)
        db.session.add(course)
        db.session.commit()
        return redirect(url_for('courses'))
    return render_template('add_course.html')

@app.route('/admin/add_lecture', methods=['GET', 'POST'])
def add_lecture():
    if session.get('role') != 'admin':
        return redirect(url_for('home'))
    all_courses = Course.query.all()
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        course_id = request.form['course_id']
        file = request.files['video']
        if file:
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            lecture = Lecture(title=title, description=description, filename=filename, course_id=course_id)
            db.session.add(lecture)
            db.session.commit()
            return redirect(url_for('courses'))
    return render_template('add_lecture.html', courses=all_courses)

# ==================== APIs ====================

@app.route('/api/students')
def api_students():
    if session.get('role') != 'admin':
        return jsonify({'error': 'unauthorized'}), 401
    users = User.query.all()
    return jsonify([{
        'id': u.id,
        'name': u.name,
        'email': u.email,
        'role': u.role,
        'active': u.active,
        'approved': u.approved,
        'subscribed': u.subscribed,
        'subscription_end': u.subscription_end.strftime('%Y-%m-%d') if u.subscription_end else None,
        'join_date': u.join_date.strftime('%Y-%m-%d') if u.join_date else None,
        'last_login': u.last_login.strftime('%Y-%m-%d') if u.last_login else 'لم يدخل بعد'
    } for u in users])

@app.route('/api/toggle_user/<int:id>', methods=['POST'])
def toggle_user(id):
    if session.get('role') != 'admin':
        return jsonify({'error': 'unauthorized'}), 401
    user = User.query.get(id)
    if not user:
        return jsonify({'error': 'not found'}), 404
    data = request.get_json()
    user.active = data['active']
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/approve_user/<int:id>', methods=['POST'])
def approve_user(id):
    if session.get('role') != 'admin':
        return jsonify({'error': 'unauthorized'}), 401
    user = User.query.get(id)
    if not user:
        return jsonify({'error': 'not found'}), 404
    data = request.get_json()
    user.approved = data['approved']
    join_req = JoinRequest.query.filter_by(user_id=id, status='pending').first()
    if join_req:
        join_req.status = 'approved' if data['approved'] else 'rejected'
    if data['approved']:
        notif = Notification(user_id=user.id, message='🎉 تم قبول طلب تسجيلك! يمكنك الدخول على المنصة دلوقتي.')
    else:
        notif = Notification(user_id=user.id, message='❌ تم رفض طلب تسجيلك. تواصل مع الأدمين لمزيد من المعلومات.')
    db.session.add(notif)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/toggle_subscription/<int:id>', methods=['POST'])
def toggle_subscription(id):
    if session.get('role') != 'admin':
        return jsonify({'error': 'unauthorized'}), 401
    user = User.query.get(id)
    if not user:
        return jsonify({'error': 'not found'}), 404
    data = request.get_json()
    user.subscribed = data['subscribed']
    if data['subscribed']:
        months = data.get('months', 1)
        user.subscription_end = datetime.utcnow() + timedelta(days=30 * months)
        notif = Notification(user_id=user.id, message=f'🎉 تم تفعيل اشتراكك لمدة {months} شهر!')
    else:
        user.subscription_end = None
        notif = Notification(user_id=user.id, message='❌ تم إلغاء اشتراكك. تواصل مع الأدمين للتجديد.')
    db.session.add(notif)
    pending = SubscriptionRequest.query.filter_by(user_id=id, status='pending').first()
    if pending:
        pending.status = 'approved' if data['subscribed'] else 'rejected'
    db.session.commit()
    return jsonify({'success': True, 'subscription_end': user.subscription_end.strftime('%Y-%m-%d') if user.subscription_end else None})

@app.route('/api/join_requests')
def api_join_requests():
    if session.get('role') != 'admin':
        return jsonify({'error': 'unauthorized'}), 401
    requests = JoinRequest.query.filter_by(status='pending').all()
    return jsonify([{
        'id': r.id,
        'user_id': r.user_id,
        'name': r.user.name,
        'email': r.user.email,
        'message': r.message,
        'created_at': r.created_at.strftime('%Y-%m-%d')
    } for r in requests])

@app.route('/api/subscription_requests')
def api_subscription_requests():
    if session.get('role') != 'admin':
        return jsonify({'error': 'unauthorized'}), 401
    requests = SubscriptionRequest.query.filter_by(status='pending').all()
    return jsonify([{
        'id': r.id,
        'user_id': r.user_id,
        'name': r.user.name,
        'email': r.user.email,
        'plan': r.plan,
        'created_at': r.created_at.strftime('%Y-%m-%d')
    } for r in requests])

@app.route('/api/stats')
def api_stats():
    if session.get('role') != 'admin':
        return jsonify({'error': 'unauthorized'}), 401
    return jsonify({
        'courses': Course.query.count(),
        'lectures': Lecture.query.count(),
        'students': User.query.filter_by(role='student').count(),
        'subscribed': User.query.filter_by(subscribed=True).count(),
        'pending_join': JoinRequest.query.filter_by(status='pending').count(),
        'pending_sub': SubscriptionRequest.query.filter_by(status='pending').count()
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)