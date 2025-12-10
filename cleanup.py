#!/usr/bin/env python3
"""
Haftalik avtomatik tozalash skripti
Har dushanba Moskva vaqti bilan 00:00 da ishga tushadi
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Loyiha yo'lini qo'shish
sys.path.insert(0, str(Path(__file__).parent))

# Log konfiguratsiyasi
log_file = Path(__file__).parent / 'cleanup.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def check_moscow_time():
    """Moskva vaqti bilan dushanba 00:00 ekanligini tekshirish"""
    try:
        import pytz
        # Agar pytz mavjud bo'lsa
        moscow_tz = pytz.timezone('Europe/Moscow')
        moscow_time = datetime.now(moscow_tz)
        
        # Dushanba (0 = dushanba) va soat 00:00-00:10 orasida
        is_monday = moscow_time.weekday() == 0
        is_midnight = moscow_time.hour == 0 and moscow_time.minute < 10
        
        logger.info(f"⏰ Moskva vaqti: {moscow_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"📅 Dushanba: {is_monday}, 00:00: {is_midnight}")
        
        return is_monday and is_midnight
    except ImportError:
        # Agar pytz mavjud bo'lmasa, UTC da hisoblaymiz (Moskva = UTC+3)
        utc_time = datetime.utcnow()
        # UTC 21:00 = Moskva 00:00 (oldingi kunning)
        is_sunday = utc_time.weekday() == 6  # 6 = yakshanba
        is_2100_utc = utc_time.hour == 21 and utc_time.minute < 10
        
        logger.info(f"⏰ UTC vaqti: {utc_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"📅 Yakshanba 21:00 UTC: {is_sunday and is_2100_utc}")
        
        return is_sunday and is_2100_utc  # Yakshanba 21:00 UTC = Dushanba 00:00 MSK

def main():
    """Asosiy tozalash funksiyasi"""
    try:
        from app import app, db, User, CleanupLog
        
        # 1. Avval Moskva vaqtini tekshiramiz
        if not check_moscow_time():
            logger.info("⏳ Tozalash vaqti emas (Moskva vaqti bilan dushanba 00:00 kerak)")
            return {
                'success': False,
                'skipped': True,
                'message': 'Tozalash vaqti emas. Moskva vaqti bilan dushanba 00:00 da ishlaydi.'
            }
        
        with app.app_context():
            logger.info("=" * 60)
            logger.info("🚀 Haftalik tozalash jarayoni boshlandi")
            logger.info("📍 Moskva vaqti bilan dushanba 00:00")
            logger.info(f"📅 Vaqt: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            # 2. Joriy holatni yozib olish
            total_users = User.query.count()
            
            if total_users == 0:
                logger.info("ℹ️  Tozalash uchun foydalanuvchi yo'q")
                # Bo'sh tozalash logi
                log = CleanupLog(
                    cleanup_time=datetime.utcnow(),
                    records_deleted=0,
                    status='skipped',
                    details="Tozalash uchun foydalanuvchi yo'q"
                )
                db.session.add(log)
                db.session.commit()
                
                return {
                    'success': True,
                    'deleted': 0,
                    'message': 'Tozalash uchum foydalanuvchi yo\'q'
                }
            
            logger.info(f"📊 Tozalanadigan foydalanuvchilar: {total_users} ta")
            
            # 3. Oxirgi faollik bo'yicha statistikalar
            week_ago = datetime.utcnow() - timedelta(days=7)
            active_users = User.query.filter(
                User.last_active_at >= week_ago
            ).count()
            inactive_users = total_users - active_users
            
            logger.info(f"📈 Faol foydalanuvchilar (oxirgi 7 kun): {active_users} ta")
            logger.info(f"📉 Faol bo'lmagan foydalanuvchilar: {inactive_users} ta")
            
            # 4. TOZALASH STRATEGIYASI:
            # Variant A: Barcha foydalanuvchilarni o'chirish (hozir bu)
            deleted_count = db.session.query(User).delete()
            
            # Variant B: Faqat faol bo'lmagan foydalanuvchilarni o'chirish
            # uncomment qilish uchun:
            # deleted_count = User.query.filter(
            #     User.last_active_at < week_ago
            # ).delete()
            # logger.info(f"🗑️  Faqat faol bo'lmagan {deleted_count} ta foydalanuvchi o'chirildi")
            
            # 5. Tozalash logini yaratish
            log = CleanupLog(
                cleanup_time=datetime.utcnow(),
                records_deleted=deleted_count,
                status='success',
                details=f"Moskva vaqti bilan avtomatik tozalash. Jami: {total_users} ta, o'chirildi: {deleted_count} ta, faollar: {active_users} ta"
            )
            db.session.add(log)
            
            # 6. O'zgarishlarni saqlash
            db.session.commit()
            
            # 7. Natijalarni log qilish
            logger.info(f"✅ MUVAFFAQIYATLI! {deleted_count} ta foydalanuvchi o'chirildi")
            logger.info(f"📝 Log yozuvi qo'shildi (ID: {log.id})")
            logger.info("=" * 60)
            
            return {
                'success': True,
                'deleted': deleted_count,
                'total_before': total_users,
                'active_users': active_users,
                'inactive_users': inactive_users,
                'message': f'{deleted_count} ta foydalanuvchi o\'chirildi'
            }
            
    except Exception as e:
        logger.error(f"❌ TOZALASHDA XATOLIK: {str(e)}", exc_info=True)
        
        # Xatolikni bazaga yozish
        try:
            with app.app_context():
                error_log = CleanupLog(
                    cleanup_time=datetime.utcnow(),
                    records_deleted=0,
                    status='error',
                    details=f"Xatolik: {str(e)[:200]}"
                )
                db.session.add(error_log)
                db.session.commit()
        except Exception as db_error:
            logger.error(f"❌ Xatolikni bazaga yozishda: {db_error}")
        
        return {
            'success': False,
            'error': str(e)
        }

if __name__ == '__main__':
    print("=" * 60)
    print("🏨 Yotoqxona Tozalash Skripti")
    print("📍 Moskva vaqti bilan har dushanba 00:00")
    print("=" * 60)
    
    result = main()
    
    print(f"\n📊 NATIJA:")
    if result.get('skipped'):
        print(f"⏳ O'tkazib yuborildi: {result.get('message')}")
    elif result.get('success'):
        print(f"✅ MUVAFFAQIYATLI")
        print(f"🗑️  O'chirilgan foydalanuvchilar: {result.get('deleted', 0)} ta")
        print(f"📈 Jami (tozalashdan oldin): {result.get('total_before', 0)} ta")
        print(f"🏃 Faollar: {result.get('active_users', 0)} ta")
    else:
        print(f"❌ XATOLIK")
        print(f"⚠️  Xatolik: {result.get('error', 'Noma\'lum')}")
    
    print("=" * 60)
    print(f"📁 Log fayli: {log_file}")
    print("=" * 60)