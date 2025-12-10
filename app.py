import os
from flask import Flask, render_template, jsonify, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from dotenv import load_dotenv
import hashlib

# .env faylini yuklash
load_dotenv()

app = Flask(__name__)

# ============================================
# 1. KONFIGURATSIYA (.env DAN)
# ============================================
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'fallback-secret-key')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(
    minutes=int(os.getenv('SESSION_TIMEOUT_MINUTES', '30'))
)

# Login cheklovlari
MAX_LOGIN_ATTEMPTS = int(os.getenv('MAX_LOGIN_ATTEMPTS', '3'))
BLOCK_DURATION_MINUTES = int(os.getenv('BLOCK_DURATION_MINUTES', '3'))

db = SQLAlchemy(app)

# ============================================
# 2. MODELLAR
# ============================================
class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    room_number = db.Column(db.String(10), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_active_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<User {self.room_number}: {self.full_name}>"
    
    def to_dict(self):
        return {
            'id': self.id,
            'full_name': self.full_name,
            'room_number': self.room_number,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            'last_active_at': self.last_active_at.strftime('%Y-%m-%d %H:%M:%S') if self.last_active_at else None
        }

class CleanupLog(db.Model):
    __tablename__ = 'cleanup_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    cleanup_time = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    records_deleted = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(50), default='success')
    details = db.Column(db.Text)

class LoginAttempt(db.Model):
    """Foydalanuvchi kirish urinishlarini kuzatish"""
    __tablename__ = 'login_attempts'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False)
    ip_address = db.Column(db.String(45), nullable=False)
    attempt_time = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    successful = db.Column(db.Boolean, default=False)
    
    def __repr__(self):
        status = "Muvaffaqiyatli" if self.successful else "Noto'g'ri"
        return f"<LoginAttempt {self.username} - {status} at {self.attempt_time}>"

# ============================================
# 3. YORDAMCHI FUNKSIYALAR
# ============================================
def get_admin_credentials():
    """Admin login ma'lumotlarini .env dan o'qish"""
    admin_username = os.getenv('ADMIN_USERNAME')
    admin_password = os.getenv('ADMIN_PASSWORD')
    
    admin_users_str = os.getenv('ADMIN_USERS', '')
    admin_credentials = {}
    
    if admin_users_str:
        for user_pass in admin_users_str.split(','):
            if ':' in user_pass:
                username, password = user_pass.split(':', 1)
                admin_credentials[username.strip()] = password.strip()
    else:
        admin_credentials[admin_username] = admin_password
    
    return admin_credentials

def check_admin_credentials(username, password):
    """Admin login ma'lumotlarini tekshirish"""
    admin_credentials = get_admin_credentials()
    
    if username not in admin_credentials:
        return False
    
    expected_password = admin_credentials[username]
    return password == expected_password

def check_login_attempts(ip_address):
    """IP manzil uchun kirish urinishlarini tekshirish"""
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    
    not_successful_attempts = LoginAttempt.query.filter(
        LoginAttempt.ip_address == ip_address,
        LoginAttempt.successful == False,
        LoginAttempt.attempt_time > one_hour_ago
    ).all()
    
    if len(not_successful_attempts) >= MAX_LOGIN_ATTEMPTS:
        last_failed_time = max(attempt.attempt_time for attempt in not_successful_attempts)
        block_until = last_failed_time + timedelta(minutes=BLOCK_DURATION_MINUTES)
        
        if datetime.utcnow() < block_until:
            remaining_seconds = int((block_until - datetime.utcnow()).total_seconds())
            minutes = remaining_seconds // 60
            seconds = remaining_seconds % 60
            return False, f"IP manzilingiz {BLOCK_DURATION_MINUTES} daqiqaga bloklangan. {minutes} daqiqa {seconds} soniya qoldi."
    
    return True, ""

def log_login_attempt(username, ip_address, successful):
    """Kirish urinishini bazaga yozish"""
    attempt = LoginAttempt(
        username=username,
        ip_address=ip_address,
        successful=successful
    )
    db.session.add(attempt)
    db.session.commit()

# ============================================
# 4. ILOVA BOSHLANGANDA
# ============================================
with app.app_context():
    try:
        db.create_all()
        user_count = User.query.count()
        
    except Exception as e:
        pass

# ============================================
# 5. ROUTE'LAR (LOGIN)
# ============================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login sahifasi"""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    
    error = None
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        ip_address = request.remote_addr
        
        is_allowed, block_message = check_login_attempts(ip_address)
        
        if not is_allowed:
            error = block_message
        elif not username or not password:
            error = "Iltimos, login va parolni kiriting"
        else:
            if check_admin_credentials(username, password):
                log_login_attempt(username, ip_address, True)
                
                session['user_id'] = hashlib.sha256(username.encode()).hexdigest()[:10]
                session['username'] = username
                session.permanent = True
                
                flash('Muvaffaqiyatli kirdingiz!', 'success')
                return redirect(url_for('dashboard'))
            else:
                log_login_attempt(username, ip_address, False)
                
                is_allowed_again, block_message_again = check_login_attempts(ip_address)
                
                if not is_allowed_again:
                    error = block_message_again
                else:
                    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
                    failed_count = LoginAttempt.query.filter(
                        LoginAttempt.ip_address == ip_address,
                        LoginAttempt.successful == False,
                        LoginAttempt.attempt_time > one_hour_ago
                    ).count()
                    
                    remaining_attempts = MAX_LOGIN_ATTEMPTS - failed_count
                    error = f"Noto'g'ri login yoki parol! {remaining_attempts} ta urinish qoldi."
    
    admin_credentials = get_admin_credentials()
    admin_users = list(admin_credentials.keys())
    
    return render_template('login.html', 
                         error=error, 
                         max_attempts=MAX_LOGIN_ATTEMPTS, 
                         block_duration=BLOCK_DURATION_MINUTES,
                         admin_users=admin_users)

@app.route('/logout')
def logout():
    """Chiqish"""
    username = session.get('username', 'Noma\'lum')
    session.clear()
    flash(f'{username} tizimdan chiqdingiz.', 'info')
    return redirect(url_for('login'))

# ============================================
# 6. DASHBOARD ROUTE'LARI
# ============================================
def login_required(f):
    """Decorator - faqat login qilganlar uchun"""
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Iltimos, avval tizimga kiring.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    
    return decorated_function

@app.route('/')
@app.route('/dashboard')
@login_required
def dashboard():
    """Asosiy dashboard sahifasi"""
    try:
        users = User.query.order_by(User.created_at.desc()).limit(100).all()
        logs = CleanupLog.query.order_by(CleanupLog.cleanup_time.desc()).limit(20).all()
        total_users = User.query.count()
        last_cleanup = CleanupLog.query.order_by(CleanupLog.cleanup_time.desc()).first()
        
        login_history = LoginAttempt.query.order_by(LoginAttempt.attempt_time.desc()).limit(10).all()
        
        admin_credentials = get_admin_credentials()
        admin_users = list(admin_credentials.keys())
        
    except Exception as e:
        users = []
        logs = []
        total_users = 0
        last_cleanup = None
        login_history = []
        admin_users = []
    
    return render_template(
        'dashboard.html',
        users=users,
        logs=logs,
        total_users=total_users,
        last_cleanup=last_cleanup,
        login_history=login_history,
        admin_users=admin_users,
        now=datetime.now(),
        username=session.get('username', 'Foydalanuvchi'),
        max_attempts=MAX_LOGIN_ATTEMPTS,
        block_duration=BLOCK_DURATION_MINUTES
    )

@app.route('/api/users')
@login_required
def get_users():
    """Foydalanuvchilar ro'yxati (JSON) - Faqat login qilganlar"""
    try:
        users = User.query.order_by(User.room_number).all()
        return jsonify([user.to_dict() for user in users])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats')
@login_required
def get_stats():
    """Statistika - Faqat login qilganlar"""
    try:
        total_users = User.query.count()
        last_cleanup = CleanupLog.query.order_by(CleanupLog.cleanup_time.desc()).first()
        
        week_ago = datetime.utcnow() - timedelta(days=7)
        active_users = User.query.filter(User.last_active_at >= week_ago).count()
        
        stats = {
            'total_users': total_users,
            'active_users': active_users,
            'inactive_users': total_users - active_users,
            'last_cleanup': last_cleanup.cleanup_time.strftime('%Y-%m-%d %H:%M:%S') if last_cleanup else 'Hech qachon',
            'records_deleted_last': last_cleanup.records_deleted if last_cleanup else 0,
            'status': last_cleanup.status if last_cleanup else 'N/A'
        }
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/cleanup/manual', methods=['POST'])
@login_required
def manual_cleanup():
    """Qo'lda tozalash - Faqat login qilganlar"""
    try:
        count_before = User.query.count()
        
        if count_before == 0:
            return jsonify({
                'success': True,
                'message': 'Tozalash uchun foydalanuvchi yo\'q',
                'deleted': 0
            })
        
        deleted_count = db.session.query(User).delete()
        
        log = CleanupLog(
            cleanup_time=datetime.utcnow(),
            records_deleted=deleted_count,
            status='manual',
            details=f"Qo'lda tozalash. {deleted_count} ta foydalanuvchi o'chirildi. Admin: {session.get('username')}"
        )
        db.session.add(log)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'{deleted_count} ta foydalanuvchi o\'chirildi',
            'deleted': deleted_count
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Xatolik: {str(e)}'
        }), 500

@app.route('/api/users/active-count')
@login_required
def active_users_count():
    """Oxirgi 7 kunda faol bo'lgan foydalanuvchilar soni - Faqat login qilganlar"""
    try:
        week_ago = datetime.utcnow() - timedelta(days=7)
        active_count = User.query.filter(User.last_active_at >= week_ago).count()
        total_count = User.query.count()
        
        return jsonify({
            'active_users': active_count,
            'inactive_users': total_count - active_count,
            'total_users': total_count
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/cleanup/count')
@login_required
def cleanup_count():
    """Tozalashlar soni"""
    try:
        count = CleanupLog.query.count()
        return jsonify({'count': count})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================
# 7. ISHGA TUSHIRISH
# ============================================
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=os.environ.get('PORT'))