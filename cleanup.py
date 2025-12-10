#!/usr/bin/env python3
"""
Haftalik avtomatik tozalash skripti
Har dushanba 00:00 da CRON tomonidan ishga tushadi
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

def main():
    """Asosiy tozalash funksiyasi"""
    try:
        from app import app, db, User, CleanupLog
        
        with app.app_context():
            logger.info("=" * 60)
            logger.info("🚀 Haftalik tozalash jarayoni boshlandi")
            logger.info(f"📅 Vaqt: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            # 1. Joriy holatni yozib olish
            total_users = User.query.count()
            
            if total_users == 0:
                logger.info("ℹ️  Tozalash uchun foydalanuvchi yo'q")
                return {
                    'success': True,
                    'deleted': 0,
                    'message': 'Tozalash uchun foydalanuvchi yo\'q'
                }
            
            logger.info(f"📊 Tozalanadigan foydalanuvchilar: {total_users} ta")
            
            # 2. Oxirgi faollik bo'yicha statistikalar
            week_ago = datetime.utcnow() - timedelta(days=7)
            active_users = User.query.filter(
                User.last_active_at >= week_ago
            ).count()
            inactive_users = total_users - active_users
            
            logger.info(f"📈 Faol foydalanuvchilar (oxirgi 7 kun): {active_users} ta")
            logger.info(f"📉 Faol bo'lmagan foydalanuvchilar: {inactive_users} ta")
            
            # 3. TOZALASH STRATEGIYASI:
            # Variant A: Barcha foydalanuvchilarni o'chirish
            deleted_count = db.session.query(User).delete()
            
            # Variant B: Faqat faol bo'lmagan foydalanuvchilarni o'chirish
            # deleted_count = User.query.filter(
            #     User.last_active_at < week_ago
            # ).delete()
            
            # 4. Tarixga yozish
            log = CleanupLog(
                cleanup_time=datetime.utcnow(),
                records_deleted=deleted_count,
                status='automatic',
                details=f"""
                Avtomatik haftalik tozalash.
                Jami foydalanuvchilar: {total_users}
                Faol foydalanuvchilar: {active_users}
                O'chirilganlar: {deleted_count}
                """
            )
            db.session.add(log)
            db.session.commit()
            
            # 5. Natijalarni log qilish
            logger.info(f"✅ MUVAFFAQIYATLI! {deleted_count} ta foydalanuvchi o'chirildi")
            logger.info(f"📝 Log yozuvi qo'shildi (ID: {log.id})")
            logger.info("=" * 60)
            
            return {
                'success': True,
                'deleted': deleted_count,
                'total_before': total_users,
                'active_users': active_users,
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
    print("=" * 60)
    
    result = main()
    
    print(f"📊 Natija: {'✅ Muvaffaqiyatli' if result.get('success') else '❌ Xatolik'}")
    if 'deleted' in result:
        print(f"🗑️  O'chirilganlar: {result['deleted']} ta")
    if 'error' in result:
        print(f"⚠️  Xatolik: {result['error']}")
    
    print("=" * 60)
    print(f"📁 Log fayli: {log_file}")
    print("=" * 60)