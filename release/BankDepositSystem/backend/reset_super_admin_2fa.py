from datetime import datetime, timezone
import os
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> int:
    mongo_url = os.environ["MONGO_URL"]
    db_name = os.environ["DB_NAME"]
    admin_username = os.environ["ADMIN_USERNAME"]

    client = MongoClient(mongo_url, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")
    db = client[db_name]

    user = db.users.find_one(
        {"username": admin_username, "$or": [{"role": "super_admin"}, {"is_super_admin": True}]},
        {"_id": 0},
    )
    if not user:
        print("لم يتم العثور على حساب السوبر أدمن المخفي admin.")
        print("تأكد أن MongoDB يعمل وأن ملف backend\\.env يشير إلى قاعدة البيانات الصحيحة.")
        return 1

    result = db.users.update_one(
        {"id": user["id"]},
        {
            "$set": {
                "totp_enabled": False,
                "totp_secret": None,
                "totp_pending_secret": None,
                "updated_at": now_iso(),
            }
        },
    )
    db.login_attempts.delete_many({"username": admin_username})
    db.login_attempts.delete_many({"identifier": {"$regex": f":{admin_username}$"}})

    db.audit_logs.insert_one(
        {
            "id": f"local-reset-2fa-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            "username": "local_reset_tool",
            "actor_full_name": "أداة استعادة محلية",
            "user_id": None,
            "organization_id": user.get("organization_id") or "social-solidarity",
            "method": "LOCAL",
            "path": "reset_super_admin_2fa.py",
            "action": "reset_super_admin_2fa",
            "arabic_description": "تم تعطيل المصادقة الثنائية لحساب السوبر أدمن محلياً بعد فقدان/خطأ كود Google Authenticator.",
            "status_code": 200,
            "request_body": {"username": admin_username},
            "ip_address": "localhost",
            "created_at": now_iso(),
        }
    )

    if result.modified_count:
        print("تم تعطيل المصادقة الثنائية لحساب السوبر أدمن بنجاح.")
    else:
        print("المصادقة الثنائية كانت معطلة بالفعل، وتم تنظيف محاولات الدخول.")
    print("افتح البرنامج الآن وسجل الدخول بـ admin / Admin@123 بدون كود Google Authenticator.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())