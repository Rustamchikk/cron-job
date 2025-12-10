import os
from flask import Flask, render_template, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from dotenv import load_dotenv

# .env faylini yuklash
load_dotenv()

app = Flask(__name__)

# ============================================
# 1. KONFIGURATSIYA
# ============================================
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-key-123')

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

# ============================================
# 3. ILOVA BOSHLANGANDA
# ============================================
with app.app_context():
    try:
        db.create_all()
        print("=" * 60)
        print("✅ Database jadvallari yaratildi/tekshirildi")
        
        # Agar users jadvali bo'sh bo'lsa
        if User.query.count() == 0:
            print("ℹ️  Users jadvali bo'sh.")
            # Test ma'lumotlarni qo'shish (ixtiyoriy)
            # test_users = [
            #     User(full_name='Ali Valiyev', room_number='101'),
            #     User(full_name='Sardor Qodirov', room_number='102'),
            # ]
            # for user in test_users:
            #     db.session.add(user)
            # db.session.commit()
            # print("✅ Test ma'lumotlar qo'shildi")
        
        user_count = User.query.count()
        print(f"✅ Bazada {user_count} ta foydalanuvchi mavjud")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Database xatosi: {e}")
        print("⚠️  PostgreSQL ga ulanmayapti. SQLite ishlatishni xohlaysizmi?")
        print("    app.py da DATABASE_URL ni 'sqlite:///test.db' ga o'zgartiring")

# ============================================
# 4. ROUTE'LAR
# ============================================
@app.route('/')
def index():
    """Bosh sahifa"""
    try:
        # Sizning bazangizdagi foydalanuvchilar
        users = User.query.order_by(User.created_at.desc()).limit(100).all()
        
        # Tozalash tarixi
        logs = CleanupLog.query.order_by(CleanupLog.cleanup_time.desc()).limit(20).all()
        
        # Statistikalar
        total_users = User.query.count()
        last_cleanup = CleanupLog.query.order_by(CleanupLog.cleanup_time.desc()).first()
        
    except Exception as e:
        print(f"❌ Ma'lumot olishda xatolik: {e}")
        users = []
        logs = []
        total_users = 0
        last_cleanup = None
    
    return render_template(
        'index.html',
        users=users,
        logs=logs,
        total_users=total_users,
        last_cleanup=last_cleanup,
        now=datetime.now()
    )

@app.route('/api/users')
def get_users():
    """Foydalanuvchilar ro'yxati (JSON)"""
    try:
        users = User.query.order_by(User.room_number).all()
        return jsonify([user.to_dict() for user in users])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats')
def get_stats():
    """Statistika"""
    try:
        total_users = User.query.count()
        last_cleanup = CleanupLog.query.order_by(CleanupLog.cleanup_time.desc()).first()
        
        return jsonify({
            'total_users': total_users,
            'last_cleanup': last_cleanup.cleanup_time.strftime('%Y-%m-%d %H:%M:%S') if last_cleanup else 'Hech qachon',
            'records_deleted_last': last_cleanup.records_deleted if last_cleanup else 0,
            'status': last_cleanup.status if last_cleanup else 'N/A'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/cleanup/manual', methods=['POST'])
def manual_cleanup():
    """Qo'lda tozalash"""
    try:
        count_before = User.query.count()
        
        if count_before == 0:
            return jsonify({
                'success': True,
                'message': 'Tozalash uchun foydalanuvchi yo\'q',
                'deleted': 0
            })
        
        # Barcha foydalanuvchilarni o'chirish
        deleted_count = db.session.query(User).delete()
        
        # Tarixga yozish
        log = CleanupLog(
            cleanup_time=datetime.utcnow(),
            records_deleted=deleted_count,
            status='manual',
            details=f"Qo'lda tozalash. {deleted_count} ta foydalanuvchi o'chirildi."
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
# ============================================
# 5. ISHGA TUSHIRISH
# ============================================
if __name__ == '__main__':
    print("=" * 60)
    print("🏨 YOTOQXONA FOYDALANUVCHILARI BOSHQARUV TIZIMI")
    print("=" * 60)
    print(f"📊 Database: {app.config['SQLALCHEMY_DATABASE_URI'][:50]}...")
    print(f"🌐 Server: http://localhost:5000")
    print("=" * 60)
    
    app.run(debug=True, host='0.0.0.0', port=5000)