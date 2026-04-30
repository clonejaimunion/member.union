# دليل التشغيل المحلي على جهاز الكمبيوتر

هذا المشروع مُجهّز للعمل محليًا على `localhost` كبرنامج ويب داخلي على الجهاز بدون الاعتماد على رابط خارجي للواجهة أو الخلفية.

## المتطلبات على الجهاز
- Python 3.11 أو أحدث
- MongoDB Community Server

## بيانات الأدمن الافتراضية
- username: `admin`
- password: `Admin@123`

بعد أول دخول يُفضّل تغيير كلمة مرور الأدمن من لوحة التحكم الخاصة ثم تفعيل Google Authenticator.

## رابط البرنامج المحلي بعد التشغيل
- البرنامج المحلي: `http://localhost:8001`
- الخلفية: `http://localhost:8001/api`
- رابط الأدمن الخاص: `http://localhost:8001/secure-admin-control-panel`

## طريقة التشغيل السريعة على Windows
1. شغّل ملف التثبيت: `BankDepositSystemSetup.exe`.
2. بعد التثبيت افتح اختصار سطح المكتب: `Bank Deposit System`.
3. انتظر فتح البرنامج على `http://localhost:8001`.

لا يحتاج التشغيل بعد التثبيت إلى Node.js أو Yarn أو إنترنت؛ الواجهة مبنية مسبقًا والاعتماديات الخلفية مرفقة داخل `backend\wheels` للتثبيت المحلي.

## منشئ البرنامج
تم إنشاء البرنامج بواسطة يوسف عبدالغني احمد.

## طريقة التشغيل السريعة على Linux / macOS
```bash
chmod +x local_install/linux_install_and_run.sh
./local_install/linux_install_and_run.sh
```

## ملاحظات مهمة
- يتم حفظ البيانات محليًا في MongoDB على نفس الجهاز.
- الواجهة تتصل بالخلفية محليًا عبر `http://localhost:8001/api` عند تشغيل نسخة Windows المثبتة.
- المصادقة الثنائية للأدمن تعمل عبر Google Authenticator بدون أي خدمة خارجية.
- ملف التثبيت يتم إنشاؤه داخل مجلد `dist` باسم `BankDepositSystemSetup.exe`.
