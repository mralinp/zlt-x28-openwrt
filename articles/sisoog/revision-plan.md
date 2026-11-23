<div dir="rtl" lang="fa">

<h1 dir="rtl" align="right">طرح بازنویسی مجموعه سیسوگ؛ تجربه مهندسی از دستگاه بسته تا محصول قابل نگهداری</h1>

**طرح برای بازبینی نویسنده — ۲۰۲۶-۱۱-۱۰ — مرحله فعلی: طراحی جریان، پیش از بازنویسی متن‌ها**

این بازبینی درباره اضافه‌کردن شماره نسخه به متن قبلی نیست. هر قسمت باید یه مشکل واقعی رو حل کنه و خواننده رو از یه وضعیت مشخص به وضعیت بعدی برسونه. کیفیت لحن و جزئیات قسمت‌های ۱ تا ۵ حفظ می‌شه، اما بعضی فصل‌های شلوغ تقسیم می‌شن تا مفهوم‌ها پیش از استفاده معرفی بشن. عنوان و شماره‌های زیر **پیشنهادی** هستن؛ فایل‌های ده‌قسمتی فعلی هنوز جابه‌جا یا بازنویسی نشده‌اند.

<h2 dir="rtl" align="right">مرز نسخه و شواهد</h2>

نویسنده تأیید کرد v0.78 در CI در حال ساخته‌شدنه. در لحظه بررسی، checkout روی `9d0f8a0` و آخرین artifact قابل مشاهده در release list، v0.77.0 بود؛ درخواست tag v0.78.0 هنوز نتیجه نداشت. بنابراین v0.78 «در حال ساخت» ثبت می‌شه، نه build ناموفق و نه خروجی منتشرشده یا آزموده‌شده. پایان CI، hash خروجی، commit و نتیجه دستگاه باید بعداً جدا ثبت بشن.

سه جست‌وجوی issue برای تازه‌ترین کارها، Preloader و Device Tree، یه مرور اولین issueها، و متن/گفت‌وگوی issueهای کلیدی بررسی شد. این ممیزی تمام issueهای پروژه نیست. متن شروع issue ممکنه فرضیه قدیمی داشته باشه؛ نظرهای بعدی، PR مربوط، source و TESTING برای نتیجه اولویت دارن. هیچ issue جدیدی ایجاد یا بسته نشد.

<h2 dir="rtl" align="right">داستانی که خواننده باید تجربه کنه</h2>

یه مودم داریم که firmwareش محدوده → اول می‌فهمیم با چه سخت‌افزاری طرفیم → دسترسی قابل اتکا می‌گیریم → اطلاعات رو حفظ می‌کنیم و محدودیت راه برگشت رو می‌سنجیم → می‌فهمیم قبل از Linux چه اتفاقی می‌افته → RootFS خودمون رو بالا می‌آریم → بهش شبکه و 5G می‌دیم → قابلیت لازم Kernel رو می‌سازیم → نتیجه رو اندازه می‌گیریم → خروجی رو package می‌کنیم → فرض‌ها رو روی مدل دوم می‌سنجیم → تصویر معتبر منتشر می‌کنیم → ارتقا و نگهداریش رو طراحی می‌کنیم.

<h2 dir="rtl" align="right">چرا دوازده قسمت؟</h2>

قسمت دوم فعلی هم NAND و Recovery رو توضیح می‌ده، هم زنجیره بوت و امضا رو. قسمت سوم هم ساخت اولین image رو داره، هم شبکه و modem. شکستن هرکدوم به دو نقطه پیشرفت، دو فصل تازه ایجاد می‌کنه. بخش VPN بعد از آموزش ABI و module قرار می‌گیره، و CI با امضای image همراه می‌شه. این تغییر از محتوای خوب کم نمی‌کنه؛ به خواننده فرصت می‌ده قبل از رفتن سراغ نتیجه بعدی، معنی موفقیت فعلی رو بفهمه.

<div dir="rtl" align="center">

| قسمت | نقطه پیشرفت | استفاده از متن فعلی |
| ---: | ---: | ---: |
| ۱ | یه مودم بسته روی میز؛ از شناخت برد تا دسترسی قابل اتکا | ۱ موجود |
| ۲ | قبل از اولین write؛ NAND رو بخونیم و راه برگشت رو بشناسیم | بخش backup و Recovery از ۲ موجود |
| ۳ | وقتی برق وصل می‌شه؛ BootROM، Preloader، LK و Device Tree | زنجیره بوت از ۲؛ DT از منابع فعلی |
| ۴ | اولین بوت خودمون؛ OpenWrt جدید روی Kernel موجود | بخش build/boot از ۳ موجود |
| ۵ | Linux بالا اومد؛ حالا یه روتر 5G بسازیم | شبکه و مودم از ۳ موجود |
| ۶ | از SDK تا module قابل استفاده؛ ABI رو جدی بگیریم | ۵ موجود با تمرکز بیشتر |
| ۷ | VPN روشنه؛ واقعاً چه چیزی رو اندازه گرفتیم؟ | ۴ موجود؛ شواهد جدید کنار تاریخ قدیم |
| ۸ | از فایل دستی تا feed امضاشده؛ نگهداری packageها | ۶ موجود |
| ۹ | دستگاه دوم فرض‌ها رو می‌شکنه؛ X28 و X28 PRO | ۷ موجود |
| ۱۰ | از build محلی تا تصویر امضاشده قابل انتشار | ۸ و بخش CI از ۱۰ موجود |
| ۱۱ | ارتقای A/B؛ وقتی روتر داره خودش رو عوض می‌کنه | ۹ موجود، بدون بحث دریافت نسخه |
| ۱۲ | کاربر نسخه تازه می‌بینه؛ از update تا نگهداری یه محصول | x28-update از ۹ و پایان ۱۰ موجود |

</div>

<h2 dir="rtl" align="right">قسمت ۱: یه مودم بسته روی میز؛ از شناخت برد تا دسترسی قابل اتکا</h2>

**سؤال آغاز:** دستگاه روشنه، اما از داخلش چی می‌دونیم و چطور بدون حدس به سیستم دسترسی بگیریم؟

**وضعیت ورودی و کار این قسمت:** قابلیت‌ها و محدودیت‌های firmware، PCB و SoC؛ UART فقط ثبت لاگ، ولتاژ ۱٫۸ V و chronology واقعی CGI → Telnet → BusyBox → SSH. قفل SIM از دسترسی root جدا بماند.

**چیزی که در پایان به دست آوردیم:** inventory پالایش‌شده، عکس واقعی و دسترسی‌ای که سطح privilege آن معلوم است.

**گره واقعی روایت:** هدف اولیه UART در issue #2 با نتیجه واقعی یکی نبود؛ بوت‌لاگ داشتن را shell داشتن نمی‌نامیم.

**معرفی مفهوم و مرز روایت:** تعریف کوتاه SoC، AP/MD، firmware، UART، shell و root؛ ورود به bootloader فقط در حد نقشه راه.

**رد شواهد و مسئله‌ها:** [#1](https://github.com/mralinp/zlt-x28-openwrt/issues/1)، [#2](https://github.com/mralinp/zlt-x28-openwrt/issues/2)، [#18](https://github.com/mralinp/zlt-x28-openwrt/issues/18)؛ نتیجه نهایی با source و TESTING تطبیق داده شود.

<h2 dir="rtl" align="right">قسمت ۲: قبل از اولین write؛ NAND رو بخونیم و راه برگشت رو بشناسیم</h2>

**سؤال آغاز:** اگر تصویر خودمون بالا نیومد چه چیزی برای برگشت داریم؟

**وضعیت ورودی و کار این قسمت:** هندسه NAND، page/eraseblock/ECC/OOB، ۵۱ پارتیشن، main-data dump، hash، UBI/UBIFS/SquashFS؛ Preloader DL و Download Agent در مقابل BootROM.

**چیزی که در پایان به دست آوردیم:** backup با provenance و checksum و مرز روشن عملیات restore واقعاً آزموده‌شده.

**گره واقعی روایت:** خواندن موفق یا ACK یه target، مجوز تعمیم به misc نیست؛ کابل و خطای DA.SLA هم به نسخه و ترتیب درخواست‌ها وابسته بودند.

**معرفی مفهوم و مرز روایت:** مفهوم filesystem، block device و لایه UBI با تصویر تو‌در‌تو؛ backup با recovery تضمین‌شده برابر نیست.

**رد شواهد و مسئله‌ها:** [#1](https://github.com/mralinp/zlt-x28-openwrt/issues/1)، [#4](https://github.com/mralinp/zlt-x28-openwrt/issues/4)، [#114](https://github.com/mralinp/zlt-x28-openwrt/issues/114)، [#273](https://github.com/mralinp/zlt-x28-openwrt/issues/273)، [#329](https://github.com/mralinp/zlt-x28-openwrt/issues/329)؛ نتیجه نهایی با source و TESTING تطبیق داده شود.

<h2 dir="rtl" align="right">قسمت ۳: وقتی برق وصل می‌شه؛ BootROM، Preloader، LK و Device Tree</h2>

**سؤال آغاز:** پیش از اجرای Linux چه کسی حافظه، slot و تصویر بعدی رو آماده می‌کنه؟

**وضعیت ورودی و کار این قسمت:** نقشه مراحل بوت، init حافظه و handoff؛ انتخاب slot در Preloader؛ وظیفه LK؛ image header؛ DTB ذخیره‌شده و درخت تحویل‌داده‌شده به Kernel؛ امضای boot و rootfs_sig.

**چیزی که در پایان به دست آوردیم:** خواننده بتونه یه boot log پالایش‌شده رو مرحله‌بندی کنه و بدونه هر تصمیم کجا گرفته می‌شه.

**گره واقعی روایت:** وجود ROOTFS_SIG_VFY Success ثابت نمی‌کرد payload جدید hash شده؛ درخت داخل LK و boot با وجود byteهای یکسان مصرف‌کننده متفاوت داشتن.

**معرفی مفهوم و مرز روایت:** تعریف کامل Preloader، LK، trust chain، hash/certificate/signature، DTS/DTB، compatible، reg، interrupts، chosen و reserved-memory؛ تفاوت ARM32/Thumb بوت با Kernel ARM64.

**رد شواهد و مسئله‌ها:** [#3](https://github.com/mralinp/zlt-x28-openwrt/issues/3)، [#40](https://github.com/mralinp/zlt-x28-openwrt/issues/40)، [#91](https://github.com/mralinp/zlt-x28-openwrt/issues/91)، [#207](https://github.com/mralinp/zlt-x28-openwrt/issues/207)، [#211](https://github.com/mralinp/zlt-x28-openwrt/issues/211)، [#215](https://github.com/mralinp/zlt-x28-openwrt/issues/215)، [#302](https://github.com/mralinp/zlt-x28-openwrt/issues/302)؛ نتیجه نهایی با source و TESTING تطبیق داده شود.

<h2 dir="rtl" align="right">قسمت ۴: اولین بوت خودمون؛ OpenWrt جدید روی Kernel موجود</h2>

**سؤال آغاز:** چطور RootFS رو عوض کنیم ولی قرارداد سخت‌افزار رو نشکنیم؟

**وضعیت ورودی و کار این قسمت:** Kernel در برابر userspace؛ BSP، libc و ELF loader؛ ABI کاربران؛ چهار compat library؛ ImageBuilder در برابر compile؛ tar staging و UBI؛ QEMU → RAM chroot → native boot.

**چیزی که در پایان به دست آوردیم:** تصویر ساخته‌شده با ورودی شناخته‌شده و شواهد اولین بوت؛ روشن باشد کدام جزء عوض شده و کدام ثابت مانده.

**گره واقعی روایت:** داشتن symbol هم‌نام یا symlink به SONAME جدید، سازگاری ABI را تضمین نمی‌کرد؛ /dev/console و نبود devtmpfs هم تعیین‌کننده بودن.

**معرفی مفهوم و مرز روایت:** تعریف ABI با نمونه واقعی library؛ toolchain و cross-compile پیش از دستور؛ native image را با Kernel mainline یکی نگیریم.

**رد شواهد و مسئله‌ها:** [#19](https://github.com/mralinp/zlt-x28-openwrt/issues/19)، [#28](https://github.com/mralinp/zlt-x28-openwrt/issues/28)، [#34](https://github.com/mralinp/zlt-x28-openwrt/issues/34)، [#76](https://github.com/mralinp/zlt-x28-openwrt/issues/76)؛ نتیجه نهایی با source و TESTING تطبیق داده شود.

<h2 dir="rtl" align="right">قسمت ۵: Linux بالا اومد؛ حالا یه روتر 5G بسازیم</h2>

**سؤال آغاز:** چرا shell و LuCI روشن هنوز به معنی CPE کارکرده نیست؟

**وضعیت ورودی و کار این قسمت:** control/data plane در AP/MD، CCCI/CCIF/DPMAIF/CCMNI در حد نیاز، MIPC، netifd/UCI/ubus/procd، LAN و switch/PHY، DHCP/DNS/NAT، IPv6 و Wi-Fi vendor.

**چیزی که در پایان به دست آوردیم:** مسیر یک بسته LAN تا WAN قابل توضیح؛ مدیریت شبکه مالک مشخص داشته باشد و تست 5G از برداشت UI جدا باشد.

**گره واقعی روایت:** dnsmasq و jail ناسازگار با Kernel؛ socket با شماره switch یکی نبود؛ 4/5G یا سلول همسایه به معنی NR فعال نیست.

**معرفی مفهوم و مرز روایت:** QMI/MBIM را جای MIPC ننشانیم؛ driver و daemon و protocol handler جدا معرفی شوند؛ جزئیات band lock بعد از مبانی ثبت شبکه.

**رد شواهد و مسئله‌ها:** [#122](https://github.com/mralinp/zlt-x28-openwrt/issues/122)، [#304](https://github.com/mralinp/zlt-x28-openwrt/issues/304)، [#306](https://github.com/mralinp/zlt-x28-openwrt/issues/306)، [#307](https://github.com/mralinp/zlt-x28-openwrt/issues/307)، [#492](https://github.com/mralinp/zlt-x28-openwrt/issues/492)، [#501](https://github.com/mralinp/zlt-x28-openwrt/issues/501)؛ نتیجه نهایی با source و TESTING تطبیق داده شود.

<h2 dir="rtl" align="right">قسمت ۶: از SDK تا module قابل استفاده؛ ABI رو جدی بگیریم</h2>

**سؤال آغاز:** برای قابلیتی که Kernel نداره چه چیزی رو می‌سازیم و چطور نتیجه رو می‌سنجیم؟

**وضعیت ورودی و کار این قسمت:** تشکر از Tozed؛ نقش SDK و config؛ userspace ABI در برابر Kernel ABI؛ vermagic/MODVERSIONS/CRC؛ WireGuard و TPROXY، export symbol، loader و crash marker.

**چیزی که در پایان به دست آوردیم:** از source و toolchain تا module و آزمون مصرف‌کننده، زنجیره شاهد کامل شود.

**گره واقعی روایت:** load بدون کنترل نسخه، سلامت حافظه را ثابت نکرد؛ marker سخت‌گیرانه ابتدا reboot سالم را هم شبیه crash می‌دید (#376).

**معرفی مفهوم و مرز روایت:** یک آزمایش WireGuard محور روایت باشد؛ مسئله NCM به مطالعه جانبی منتقل شود تا این فصل فهرست چند driver نامرتبط نشود.

**رد شواهد و مسئله‌ها:** [#18](https://github.com/mralinp/zlt-x28-openwrt/issues/18)، [#227](https://github.com/mralinp/zlt-x28-openwrt/issues/227)، [#376](https://github.com/mralinp/zlt-x28-openwrt/issues/376)، [#394](https://github.com/mralinp/zlt-x28-openwrt/issues/394)؛ نتیجه نهایی با source و TESTING تطبیق داده شود.

<h2 dir="rtl" align="right">قسمت ۷: VPN روشنه؛ واقعاً چه چیزی رو اندازه گرفتیم؟</h2>

**سؤال آغاز:** تونل کار می‌کنه، اما سرعت، مسیر و مصرف حافظه چطور سنجیده می‌شن؟

**وضعیت ورودی و کار این قسمت:** WireGuard/OpenVPN و Passwall2/Xray؛ TPROXY در مقابل forwarding؛ TCP/UDP/IPv6، DNS، CPU و جهت تست؛ workload torrent و رشد socket.

**چیزی که در پایان به دست آوردیم:** ماتریس آزمایش و benchmark با مسیر، واحد، جهت، شرایط و دامنه نتیجه؛ خواننده بتواند روش را تکرار کند.

**گره واقعی روایت:** نصب package یا سبزشدن UI اثبات عبور LAN نیست؛ تخمین ظرفیت با throughput اندازه‌گیری‌شده فرق دارد.

**معرفی مفهوم و مرز روایت:** کد و نمودار packet path به شرط منبع واقعی؛ آزمون حجیم و تغییر firewall صرفاً با پیش‌نیاز؛ اعداد اولیه بازنویسی یا مدرن‌سازی جعلی نشوند.

**رد شواهد و مسئله‌ها:** [#227](https://github.com/mralinp/zlt-x28-openwrt/issues/227)، [#250](https://github.com/mralinp/zlt-x28-openwrt/issues/250)، [#376](https://github.com/mralinp/zlt-x28-openwrt/issues/376)؛ نتیجه نهایی با source و TESTING تطبیق داده شود.

<h2 dir="rtl" align="right">قسمت ۸: از فایل دستی تا feed امضاشده؛ نگهداری packageها</h2>

**سؤال آغاز:** چطور دستگاه بعد از خروج از میز توسعه‌دهنده قابل نگهداری می‌مونه؟

**وضعیت ورودی و کار این قسمت:** ipk/control/dependency، kernel record، stub در برابر module، epoch/revision، x28-base، یک set از ipk برای image و feed، امضای index و ترتیب انتشار.

**چیزی که در پایان به دست آوردیم:** یه package قابل پیگیری از build تا نصب/rollback و dependency درست؛ شکست پشتیبانی‌نشده صریح باشد.

**گره واقعی روایت:** module دستی با package هم‌نام یکی نیست؛ #436 ابزار نصب‌شده روی واحد توسعه را از تصویر تازه جا انداخته بود.

**معرفی مفهوم و مرز روایت:** همه packageهای 23.05 دوباره compile نشده‌اند؛ امضای package از امضای image و boot جدا بماند.

**رد شواهد و مسئله‌ها:** [#352](https://github.com/mralinp/zlt-x28-openwrt/issues/352)، [#394](https://github.com/mralinp/zlt-x28-openwrt/issues/394)، [#417](https://github.com/mralinp/zlt-x28-openwrt/issues/417)، [#418](https://github.com/mralinp/zlt-x28-openwrt/issues/418)، [#436](https://github.com/mralinp/zlt-x28-openwrt/issues/436)، [#499](https://github.com/mralinp/zlt-x28-openwrt/issues/499)، [#503](https://github.com/mralinp/zlt-x28-openwrt/issues/503)؛ نتیجه نهایی با source و TESTING تطبیق داده شود.

<h2 dir="rtl" align="right">قسمت ۹: دستگاه دوم فرض‌ها رو می‌شکنه؛ X28 و X28 PRO</h2>

**سؤال آغاز:** چرا image روی یه واحد درست و روی PRO خراب بود؟

**وضعیت ورودی و کار این قسمت:** هویت برد و PCI، تک‌کارت/دوکارت، profile و calibration، تشخیص پیش از load، DHCP timing و مطالعه paired test.

**چیزی که در پایان به دست آوردیم:** چک‌لیست مدل‌ها با مثبت/منفی/آزموده‌نشده؛ تصویر عمومی از داده اختصاصی واحد پاک باشد.

**گره واقعی روایت:** issue #513: image عمومی از stock معمولی، منطق فقط تبدیل دوکارت به تک‌کارت داشت؛ روی PRO هر دو باند بدون SSID بودند.

**معرفی مفهوم و مرز روایت:** آزمون با SIM و فن متفاوت مقایسه کنترل‌شده نیست؛ نام تجاری یا closed issue اثبات همه revisionها نیست.

**رد شواهد و مسئله‌ها:** [#318](https://github.com/mralinp/zlt-x28-openwrt/issues/318)، [#436](https://github.com/mralinp/zlt-x28-openwrt/issues/436)، [#476](https://github.com/mralinp/zlt-x28-openwrt/issues/476)، [#513](https://github.com/mralinp/zlt-x28-openwrt/issues/513)؛ نتیجه نهایی با source و TESTING تطبیق داده شود.

<h2 dir="rtl" align="right">قسمت ۱۰: از build محلی تا تصویر امضاشده قابل انتشار</h2>

**سؤال آغاز:** چطور تصویر تحویل‌داده‌شده همون چیزیه که بررسی کردیم؟

**وضعیت ورودی و کار این قسمت:** assembly و inputها، generic image، manifest و hash، fwtool/usign/ucert، supported_devices، signer جدا از کلید آفلاین، artifact و CI gates.

**چیزی که در پایان به دست آوردیم:** رد unsigned/tampered و پذیرش signed با شاهد؛ نسخه و provenance خروجی معلوم باشد.

**گره واقعی روایت:** Tozed,X28 یه شناسه کامل با کاماست، نه دو board؛ نتیجه بررسی امضا در RAM root با محیط قبل از pivot یکسان فرض شده بود.

**معرفی مفهوم و مرز روایت:** امضای vendor و امضای خودمان یکی نیست؛ دریافت SDK اجازه انتشار تمام آن یا تأیید رسمی محصول استنباط نشود.

**رد شواهد و مسئله‌ها:** [#254](https://github.com/mralinp/zlt-x28-openwrt/issues/254)، [#476](https://github.com/mralinp/zlt-x28-openwrt/issues/476)، [#499](https://github.com/mralinp/zlt-x28-openwrt/issues/499)؛ نتیجه نهایی با source و TESTING تطبیق داده شود.

<h2 dir="rtl" align="right">قسمت ۱۱: ارتقای A/B؛ وقتی روتر داره خودش رو عوض می‌کنه</h2>

**سؤال آغاز:** چطور image رو بنویسیم بدون اینکه نسخه کارکرده رو زودتر از موعد از دست بدیم؟

**وضعیت ورودی و کار این قسمت:** sysupgrade stage2/RAM root، نسخه مبدأ و مقصد، inactive target، UBI logical verify، misc چندکپی، x28-bootok و tries/success، overlay/UUID و config.

**چیزی که در پایان به دست آوردیم:** check → write → verify → select → boot-health با شاهد؛ A → B → A در نسخه آزموده‌شده مستند بماند.

**گره واقعی روایت:** stage2 غایب، log روی overlay unmountشده، node UBI غایب و تصمیم target پس از pivot؛ hash کل MTD بعد از ubiformat معیار مناسب نبود.

**معرفی مفهوم و مرز روایت:** سیاست قبل/بعد از v0.76 تفکیک شود؛ native روی B یعنی stock داخلی دیگر باقی نیست؛ قطع برق و tries-6 صرفاً با شاهد مستقل.

**رد شواهد و مسئله‌ها:** [#154](https://github.com/mralinp/zlt-x28-openwrt/issues/154)، [#302](https://github.com/mralinp/zlt-x28-openwrt/issues/302)، [#450](https://github.com/mralinp/zlt-x28-openwrt/issues/450)، [#451](https://github.com/mralinp/zlt-x28-openwrt/issues/451)، [#452](https://github.com/mralinp/zlt-x28-openwrt/issues/452)، [#457](https://github.com/mralinp/zlt-x28-openwrt/issues/457)، [#458](https://github.com/mralinp/zlt-x28-openwrt/issues/458)، [#465](https://github.com/mralinp/zlt-x28-openwrt/issues/465)، [#476](https://github.com/mralinp/zlt-x28-openwrt/issues/476)، [#477](https://github.com/mralinp/zlt-x28-openwrt/issues/477)، [#509](https://github.com/mralinp/zlt-x28-openwrt/issues/509)؛ نتیجه نهایی با source و TESTING تطبیق داده شود.

<h2 dir="rtl" align="right">قسمت ۱۲: کاربر نسخه تازه می‌بینه؛ از update تا نگهداری یه محصول</h2>

**سؤال آغاز:** چطور نسخه پیدا و دریافت می‌شه، و چطور به کاربر اثر upgrade رو درست می‌گیم؟

**وضعیت ورودی و کار این قسمت:** check/cache و release discovery، hash و sysupgrade -T، حافظه RAM و lock، تأیید LuCI، -n و اثر config، پایش پس از upgrade و پایان‌بندی مهندسی.

**چیزی که در پایان به دست آوردیم:** مسیر صاحب دستگاه از دیدن release تا تصمیم upgrade روشن؛ CI سبز، artifact امضاشده و unit-tested سه شاهد جدا بمانند.

**گره واقعی روایت:** خودکاربودن ساخت release به معنی reboot بدون تأیید نیست؛ helper با fake sysupgrade تست شده، همان نتیجه را تست کامل LuCI نمی‌نامیم.

**معرفی مفهوم و مرز روایت:** v0.78 اکنون در CI است؛ artifact پس از پایان به دفتر شواهد افزوده شود. پایان روایت، کارهای باز و درس‌های قابل انتقال است، نه فهرست تبلیغاتی قابلیت‌ها.

**رد شواهد و مسئله‌ها:** [#477](https://github.com/mralinp/zlt-x28-openwrt/issues/477)، [#478](https://github.com/mralinp/zlt-x28-openwrt/issues/478)، [#479](https://github.com/mralinp/zlt-x28-openwrt/issues/479)، [#511](https://github.com/mralinp/zlt-x28-openwrt/issues/511)، [#515](https://github.com/mralinp/zlt-x28-openwrt/issues/515)؛ نتیجه نهایی با source و TESTING تطبیق داده شود.

<h2 dir="rtl" align="right">الگوی ثابت هر قسمت؛ تجربه مهندسی، نه گزارش قابلیت‌ها</h2>

۱. صحنه شروع: همین حالا چه چیزی کار می‌کنه و چه چیزی نه؟

۲. سؤال: برای قدم بعدی دقیقاً چه مجهولی داریم؟

۳. معرفی مفهوم: تعریف ساده، نقش در همین دستگاه و یه نمودار کوچک.

۴. فرضیه و راه مشاهده: چرا این log، source، command یا ابزار رو انتخاب کردیم؟

۵. اجرا: فرمان واقعی با ورودی و پیش‌نیاز معلوم؛ دستور تاریخی از دستور توصیه‌شده امروز جدا.

۶. شکست یا نتیجه غیرمنتظره: چه دیدیم و کدوم فرض عوض شد؟

۷. اصلاح و سنجش: چه چیزی تغییر کرد و با کدوم test فهمیدیم بهتر شده؟

۸. مرز نتیجه: این آزمایش چه چیزی رو ثابت نکرد؟

۹. درس قابل انتقال: خواننده همین روش رو روی برد یا محصول خودش چطور به کار می‌بره؟

۱۰. پل به فصل بعد: چه نیاز تازه‌ای از همین موفقیت به وجود اومد؟

این ساختار قالب اجباری ده‌تیتره نیست؛ ریتم متن باید طبیعی بمونه. اصطلاح انگلیسی قبل از تعریف رها نمی‌شه، بحث نظری بدون مسئله واقعی طول نمی‌کشه، و issueها به داستان تصمیم و بازخورد تبدیل می‌شن، نه یه changelog فارسی.

<h2 dir="rtl" align="right">معرفی‌های پایه که باید از نو نوشته بشن</h2>

<div dir="rtl" align="center">

| مفهوم | معرفی نخست | مثال مربوط به پروژه | اشتباهی که باید جلوش گرفته بشه |
| ---: | ---: | ---: | ---: |
| BootROM و Preloader | اشاره در ۲، توضیح کامل در ۳ | ROM آغازین، آماده‌سازی برد/حافظه، انتخاب slot و پنجره DL | Preloader صرفاً «loader لینوکس» یا همان BootROM نیست |
| LK و handoff | ۳ | مرحله بعد، خواندن boot image و آماده‌سازی ورودی Kernel | UART log از LK به معنی shell یا فرمان set_active نیست |
| Device Tree | ۳، استفاده در ۴/۵ | DTB در boot، نسخه مصرفی LK و fixupهای chosen و memory | DT driver نیست و تغییر reg به معنی کشف سخت‌افزار نیست |
| امضای vendor | ۳ | metadata گواهی و مسیر Fail/Success | معتبر بودن امضای metadata، اثبات بررسی byteهای payload نیست |
| ABI کاربران | ۴ | ELF، SONAME و چهار library سازگاری | هم‌نام بودن symbol یا ARM64 بودن کافی نیست |
| ABI Kernel | ۶ | module_layout، CRC و struct offset | خاموش‌کردن check، سازگاری حافظه نمی‌سازه |
| امضای image پروژه | ۱۰ | signer جدا، ucert/fwtool و board metadata | امضای خودمان با کلید vendor یا secure boot یکی نیست |
| update / upgrade / OTA | ۸، ۱۱، ۱۲ | package، نوشتن تصویر، کشف نسخه و تأیید کاربر | CI خودکار یا دکمه upgrade معادل OTA بی‌حضور کاربر نیست |

</div>

<h2 dir="rtl" align="right">طرح تصویرها و تمرین‌های کم‌خطر</h2>

- قسمت ۱: عکس واقعی برد و UART، همراه جهت و سطح ولتاژ تأییدشده؛ TX/RX از ظاهر عکس حدس زده نشه.
- قسمت ۲: لایه NAND → UBI → volume → filesystem و یک hash comparison از شواهد واقعی.
- قسمت ۳: نمودار BootROM → Preloader → LK → Kernel → init با مشخص‌کردن جای انتخاب slot و هر check؛ دو مسیر مستقل DTB برای LK و Linux.
- قسمت ۴: نمودار وابستگی ELF و نمونه library mismatch؛ مقایسه inventory و manifest بدون اجرای vendor binary روی میزبان.
- قسمت ۵: مسیر یه بسته LAN تا modem و مسیر جدا control؛ سؤال آموزشی «DHCP نداریم یا WAN نداریم؟».
- قسمت ۶/۷: source → build → load → functional test و جدول benchmark بدون کلید peer یا endpoint خصوصی.
- قسمت ۸: dependency graph یه بسته واقعی و قبل/بعد database؛ stub خروجی اجرایی تازه ایجاد نمی‌کنه.
- قسمت ۹: جدول شناسایی PCI و profile تک‌کارت/دوکارت بدون انتشار calibration؛ عکس فرضی از PRO ساخته نشه.
- قسمت ۱۰: نمودار کلید اعتماد، signer و artifact و نمونه رد تصویر دست‌کاری‌شده از log موجود.
- قسمت ۱۱: state diagram upgrade و جدول قطع عملیات در هر مرحله؛ درخت خطای stage2 به‌جای shell command مخرب.
- قسمت ۱۲: screenshot واقعی اعلان و تأیید LuCI بعد از حذف اطلاعات خصوصی؛ نبود screenshot یا test با نمونه جعلی پر نشه.

هر تمرین باید برچسب «روی فایل میزبان»، «خواندن دستگاه»، «شبکه/دانلود»، «تغییر runtime» یا «نوشتن flash» داشته باشه. تمرین مطالعه defaultش خواندنه؛ ساختن test خرابی روی تنها مودم اینترنت کار خواننده عادی نیست.

<h2 dir="rtl" align="right">چه چیزی از ده قسمت فعلی حفظ یا اصلاح می‌شه؟</h2>

لحن خودمونی و اول‌شخص، عکس‌های واقعی، مسیر TXS0108E، ترتیب واقعی دسترسی و اعداد benchmark حفظ می‌شن. عبارت‌های مکرر «وجود فایل دلیل کارکرد نیست» به یه مورد واقعی و یه نتیجه مشخص تبدیل می‌شن. فصل ۵ فعلی پایه خوبی برای فصل ۶ هست؛ فقط روی یه آزمایش اصلی تمرکز می‌کنه. شش فصل آخر نباید صرفاً قابلیت‌ها رو فهرست کنن: هرکدوم یه before/after و یه گره واقعی از issueها خواهد داشت.

به‌جای بستن چند فصل با banner «این متن قدیمیه، فصل بعد رو ببین»، هر فصل داستان کامل مرحله خودش رو می‌گه و یه کادر کوتاه «در اون مرحله / وضعیت امروز» داره. مسیر ابزارهایی که به x28-flasher منتقل شدن روشن می‌مونه، اما حفظ روش تاریخی نباید به راهنمای نصب گمراه‌کننده تبدیل بشه. نام فایل‌ها تا آماده‌شدن متن جایگزین تغییر نمی‌کنه؛ جدول تطبیق بالا جلوی لینک شکسته و گم‌شدن محتوا رو می‌گیره.

<h2 dir="rtl" align="right">ترتیب بازنویسی و معیار تمام‌شدن</h2>

این طرح عمداً داخل articles/sisoog نگه داشته شده؛ درخواست اصلی کار رو به همین پوشه محدود می‌کنه. tasks/plan.md از قبل برنامه کار مستقلِ نیمکت آزمون/Kernel داره و دست نخورده می‌مونه. checkpoint بازبینی همین flow پیش از بازنویسی متن‌هاست؛ در این مرحله درخواست ساخت PR یا issue تازه وجود نداره.

<h3 dir="rtl" align="right">مرحله A: تثبیت شواهد نسخه</h3>

- **دامنه:** همین طرح و دفتر شواهد
- **معیار پذیرش:** ورودی‌های GitHub و محلی با تاریخ و commit معلوم؛ v0.78 تا اتمام CI جدا باشد.
- **بررسی:** مقایسه release artifact، تغییرهای source و TESTING؛ بدون فرض موفقیت CI.
- **وابسته به:** ندارد

<h3 dir="rtl" align="right">مرحله B: بازنویسی شناخت، backup و boot</h3>

- **دامنه:** قسمت‌های پیشنهادی ۱ تا ۳؛ هرکدوم یه مرحله مستقل
- **معیار پذیرش:** Preloader، LK، DT و امضا قبل از استفاده تعریف شده؛ chronology دسترسی و مرز Recovery درست باشد.
- **بررسی:** مقایسه BOOT-FLOW و #40/#215/#302؛ خواندن از دید فردی که بار اول برد embedded می‌بینه.
- **وابسته به:** A و بازبینی flow

<h3 dir="rtl" align="right">مرحله C: بازنویسی اولین بوت و شبکه</h3>

- **دامنه:** قسمت‌های ۴ و ۵
- **معیار پذیرش:** دلیل حفظ Kernel، ABI library، DT و ownership شبکه در مسیر یه آزمایش معلوم بیان شود.
- **بررسی:** مطابقت inventory، QEMU و تست روی واحد؛ هیچ فرمان نصب روز از script تاریخی نتیجه گرفته نشود.
- **وابسته به:** B

<h3 dir="rtl" align="right">مرحله D: module و آزمایش قابلیت</h3>

- **دامنه:** قسمت‌های ۶ و ۷
- **معیار پذیرش:** کامپایل، load و ترافیک مستقل گزارش شوند؛ benchmark قابل مقایسه و failure واقعی داشته باشد.
- **بررسی:** خواندن نظرهای #227 و #376 و TESTING ۳۷ تا ۴۱؛ حفظ همه محدودیت‌ها.
- **وابسته به:** C

<h3 dir="rtl" align="right">مرحله E: بسته و مدل دوم</h3>

- **دامنه:** قسمت‌های ۸ و ۹
- **معیار پذیرش:** dependency با capability هماهنگ؛ مشکل profile عمومی PRO به علت و اصلاح برسد.
- **بررسی:** تطبیق #436/#513 و source؛ تفاوت دو نمونه از پشتیبانی همه revisionها جدا باشد.
- **وابسته به:** D

<h3 dir="rtl" align="right">مرحله F: انتشار امضاشده</h3>

- **دامنه:** قسمت ۱۰
- **معیار پذیرش:** hash، trust، board metadata و provenance در یه زنجیره روشن معرفی شوند.
- **بررسی:** بررسی #476 و ابزار image_sign؛ کلید خصوصی یا محتوای اختصاصی وارد متن نشود.
- **وابسته به:** E

<h3 dir="rtl" align="right">مرحله G: upgrade و نگهداری</h3>

- **دامنه:** قسمت‌های ۱۱ و ۱۲
- **معیار پذیرش:** نسخه مبدأ/مقصد، محیط RAM، inactive slot و تصمیم کاربر روشن؛ وضعیت pending آزمایش‌ها مشخص.
- **بررسی:** #458/#509/#515، source جاری و TESTING ۵۳d؛ حفظ config و power-loss وعده داده نشود.
- **وابسته به:** F

<h3 dir="rtl" align="right">مرحله H: بازبینی کل مجموعه</h3>

- **دامنه:** فهرست و editorial-notes پس از آماده‌شدن فصل‌ها
- **معیار پذیرش:** گذارها، واژه‌ها، شماره‌ها و لینک‌ها یکسان؛ هیچ مفهوم مهم پیش از تعریف استفاده نشود.
- **بررسی:** بازبینی فنی و خوانش آموزشی؛ RTL heading، code LTR، جدول/عکس وسط، منابع فهرستی و لینک محلی سالم.
- **وابسته به:** G

اندازه هدف متن کامل هر قسمت حدود ۲۰۰۰ تا ۳۵۰۰ واژه‌ست، با اولویت کامل‌بودن آزمایش و خوانایی. تعریف، نمونه و failure باید عمق بدن، نه تکرار عبارت‌ها برای رسیدن به عدد. هر بسته بازنویسی حداکثر دو یا سه فصل رو درگیر می‌کنه و پیش از رفتن سراغ مرحله بعد، گذار آموزشی و شواهدش مرور می‌شن.

<h2 dir="rtl" align="right">منابع و دفتر شواهد</h2>

- [دفتر issueها و تصمیم‌های ویرایشی همین بازبینی](revision-evidence.md)
- [فهرست ده مقاله موجود؛ هنوز شماره‌گذاری قبلی](README.md)
- [BOOT-FLOW](../../docs/BOOT-FLOW.md)
- [FIRMWARE-INVENTORY و ABI](../../docs/FIRMWARE-INVENTORY.md)
- [ثبت آزمون‌ها](../../docs/TESTING.md)
- [وضعیت پروژه](../../docs/STATUS.md)
- [طراحی sysupgrade](../../docs/research/sysupgrade-design.md)
- [releaseهای پروژه](https://github.com/mralinp/zlt-x28-openwrt/releases)

</div>
