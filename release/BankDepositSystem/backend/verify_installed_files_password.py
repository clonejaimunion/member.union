import getpass
import os
from pathlib import Path

import bcrypt
from dotenv import load_dotenv
from pymongo import MongoClient


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")


def main() -> int:
    mongo_url = os.environ["MONGO_URL"]
    db_name = os.environ["DB_NAME"]
    client = MongoClient(mongo_url, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")
    settings = client[db_name].app_settings.find_one({"id": "global"}, {"_id": 0}) or {}
    if not settings.get("installed_files_lock_enabled"):
        return 0
    password_hash = settings.get("installed_files_password_hash")
    if not password_hash:
        print("قفل مجلد التثبيت مفعل لكن كلمة السر غير محددة من صفحة أمان البرنامج.")
        return 1
    password = getpass.getpass("أدخل كلمة سر مجلد الملفات المثبتة لتشغيل البرنامج: ")
    if bcrypt.checkpw(password.encode(), password_hash.encode()):
        print("تم التحقق من كلمة سر مجلد التثبيت.")
        return 0
    print("كلمة سر مجلد الملفات المثبتة غير صحيحة.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())