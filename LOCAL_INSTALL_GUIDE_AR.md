# دليل التشغيل المحلي على جهاز الكمبيوتر

هذا المشروع مُجهّز للعمل محليًا على `localhost` كبرنامج ويب داخلي على الجهاز.

## المتطلبات على الجهاز
- Python 3.11 أو أحدث
- Node.js 20 أو أحدث
- Yarn
- MongoDB Community Server

## بيانات الأدمن الافتراضية
- username: `admin`
- password: `Admin@123`

بعد أول دخول يُفضّل تغيير كلمة مرور الأدمن من لوحة التحكم الخاصة ثم تفعيل Google Authenticator.

## رابط البرنامج المحلي بعد التشغيل
- الواجهة: `http://localhost:3000`
- الخلفية: `http://localhost:8001/api`
- رابط الأدمن الخاص: `http://localhost:3000/secure-admin-control-panel`

## طريقة التشغيل السريعة على Windows
1. افتح مجلد المشروع.
2. شغل الملف:
   `local_install/windows_install_and_run.bat`
3. انتظر فتح الواجهة على المتصفح.

## طريقة التشغيل السريعة على Linux / macOS
```bash
chmod +x local_install/linux_install_and_run.sh
./local_install/linux_install_and_run.sh
```

## ملاحظات مهمة
- يتم حفظ البيانات محليًا في MongoDB على نفس الجهاز.
- المصادقة الثنائية للأدمن تعمل عبر Google Authenticator بدون أي خدمة خارجية.
- يمكن تحويل هذه النسخة لاحقًا إلى Windows Installer كامل بملف Setup.exe.
