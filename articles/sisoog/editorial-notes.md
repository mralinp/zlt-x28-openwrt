<div dir="rtl" lang="fa">

<h1 dir="rtl" align="right">یادداشت‌های تحریریه مجموعه ZLT X28 برای سیسوگ</h1>

**نویسنده مقالات: علی نادری پاریزی — تاریخ بازبینی منابع: ۲۰۲۶-۱۱-۱۰؛ چهار قسمت نخست با مبنای تاریخی ۲۰۲۶-۱۱-۰۴**

این پوشه حالا ده مقاله Markdown و یک نقشه مجموعه برای بازبینی فنی و تحریریه دارد. چهار قسمت نخست snapshot تاریخی‌اند و شش قسمت جدید ادامه توسعه تا بازبینی ۲۰۲۶-۱۱-۱۰ را پوشش می‌دهند. عنوان ثابت مجموعه در ابتدای هر مقاله «مهندسی معکوس مودم‌های 5G مدل ZLT X28 و X28 PRO» است و زیر آن، شماره قسمت و عنوان موضوعی مثل عنوان فصل کتاب می‌آید؛ عبارت «از چهار قسمت» استفاده نمی‌شود. فقط همین پوشه به پروژه افزوده شده است؛ هیچ اتصال به روتر، build فریمور، فلش، تغییر تنظیمات، commit یا push در آماده‌سازی مقالات انجام نشده است. اعداد و نتایج سخت‌افزاری نقل از شواهد موجود پروژه‌اند، نه آزمون تازه این نگارش.

<h2 dir="rtl" align="right">مبنا، دامنه و نقشه شواهد</h2>

مبنای چهار قسمت نخست، commit [`b9c1a96`](https://github.com/mralinp/zlt-x28-openwrt/tree/b9c1a96) است. عنوان بعضی سندها تاریخ قدیمی دارد، اما متن آن‌ها به‌روزرسانی‌های بعدی را در خود دارد. اولویت در نتیجه‌گیری: کد و interface فعلی برای رفتار ابزار؛ ثبت آزمون تاریخ‌دار برای نتیجه دستگاه؛ تحلیل artifact برای معماری؛ برنامه و TODO فقط برای کار آینده. نبود شاهد، به موفقیت تعبیر نشده است.

<div dir="rtl" align="center">

| مقاله | محور و نتیجه | وضعیت شواهد |
| ---: | ---: | ---: |
| [۱. سخت‌افزار و دسترسی](01-hardware-and-initial-access.md) | MT6890، CGI/DMZ به Telnet،‏ BusyBox با UID 1000،‏ root SSH با کلید و سپس UART | مسیر shell با گفت‌وگوی اولیه و آثار محلی تطبیق داده شد؛ SIM-unlock از قبل انجام شده بود |
| [۲. فریمور و NAND](02-firmware-nand-and-bootloader.md) | همه ۵۱ پارتیشن، backup بدون OOB، A/B، گواهی‌ها، DA و restore | خواندن همه پارتیشن‌ها؛ restore محدود یک صفحه؛ BROM عمومی اثبات نشده |
| [۳. OpenWrt و 5G](03-openwrt-installation-and-5g.md) | userspace 23.05.5 روی 4.19.205، ساخت محلی، boot A، netifd و MIPC | native boot و شبکه روی یک واحد؛ reconnect طولانی و چند اپراتور باز |
| [۴. VPN و benchmark](04-passwall2-vpn-and-benchmarks.md) | ماژول‌ها، feed، WireGuard/OpenVPN، Passwall2 و RAM | آزمون آزمایشگاهی VPN و LAN واقعی proxy؛ clean-flash نهایی Passwall2 تأیید نشده |

</div>

برای ممیزی، درخت `docs/` به‌صورت بازگشتی فهرست و اسناد فعلی، archive، research، config و DTS بررسی شدند. فایل‌های نشان تجاری از شواهد سخت‌افزار جدا شدند. مسیرهای `router/` و `experiments/` مربوط به stock overlay هستند؛ وجود آن‌ها به معنی استفاده در native image نیست. کدهای `tools/build/`،‏ `tools/recovery/`،‏ `tools/firmware/` و `package/x28-*` برای claims اصلی مرجع قرار گرفتند. kernel moduleهای vendored صرفاً برای نیاز source/patch مرتبط بررسی شدند؛ این کار ممیزی خط‌به‌خط تمام source WireGuard یا firmware اختصاصی نیست.

<h3 dir="rtl" align="right">منابع ادعاهای مهم</h3>

<div dir="rtl" align="center">

| ادعا | منابع دقیق در مخزن | سطح شاهد و نحوه استفاده |
| ---: | ---: | ---: |
| MT6890/T750، چهار A55، MT7915، RAM و flash | [HARDWARE](../../docs/HARDWARE.md)، [معماری](../../docs/research/x28-hardware-architecture.md)، [DTS پالایش‌شده](../../docs/firmware/x28-device-tree.dts) | live/DT؛ ظرفیت chip از span استنباط شده؛ marking زیر شیلد تأیید نشده |
| RG500L-EU و مسیر داخلی AP/MD | [معماری](../../docs/research/x28-hardware-architecture.md)، [تحلیل درایور مودم](../../docs/research/x28-modem-driver-analysis.md) | هویت firmware و driver زنده؛ جزئیات source از SDK هم‌خانواده، نه source دقیق Tozed |
| MT7531AE و اختلاف config با شبکه زنده | [DEVICE-AUDIT](../../docs/DEVICE-AUDIT.md)، [پیش‌نیاز LAN](../../docs/research/live-native-boot-prerequisites.md)، [BUILD](../../docs/BUILD.md) | مشاهده switch و مسیر VLAN؛ از `eth1` فرضی به mapping آزموده‌شده |
| سابقه LuCI، SSH 2222 و نبود netifd فعال | [luci-fix-notes](../../docs/luci-fix-notes.md)، [luci-on-stock](../../docs/luci-on-stock.md)، [README قدیمی](../../docs/archive/2026-10-20-README.md) | تاریخچه stock؛ نقص روایت دسترسی اولیه با آثار محلی و چت اولیه تکمیل شد؛ بخش بعدی را ببینید |
| UART، 1.8 V، pinout و 921600 8N1 | [RECOVERY، Verified setup](../../docs/RECOVERY.md)، [لاگ UART](../../docs/research/uart-boot-log.md) | تأیید نهایی متأخر بر candidate و آزمون پیوستگی نادرست مقدم است |
| ۵۱ پارتیشن و backup | [RECOVERY-BACKUP](../../docs/RECOVERY-BACKUP.md)، [RECOVERY](../../docs/RECOVERY.md)، [dump_partitions.py](https://github.com/mralinp/x28-flasher/blob/main/tools/recovery/dump_partitions.py)، [common.py](https://github.com/mralinp/x28-flasher/blob/main/tools/recovery/common.py) | main data بدون OOB؛ اندازه کل 1,072,168,960 بایت |
| جدول کامل MTD مقاله دوم | metadata خصوصی `private/recovery/20261020-capture-prepared-20261021/metadata/mtd.txt`؛ تطبیق با [slot_session](https://github.com/mralinp/x28-flasher/blob/main/tools/recovery/slot_session.py) و [RECOVERY](../../docs/RECOVERY.md) | فقط نام، شماره و اندازه منتشر شده؛ فایل خصوصی یا محتوای پارتیشن به مقالات کپی نشده |
| استخراج UBI/SquashFS و حساسیت حروف | [FIRMWARE-EXTRACTION](../../docs/FIRMWARE-EXTRACTION.md)، [Dockerfile](https://github.com/mralinp/zlt-x28-openwrt/blob/b9c1a96/tools/firmware/Dockerfile) | ابزارهای shell داخل container؛ tree استخراجی و firmware خصوصی باقی می‌مانند |
| Preloader و LK و A/B | [BOOT-FLOW](../../docs/BOOT-FLOW.md)، [UART](../../docs/research/uart-boot-log.md)، [slot-selection](../../docs/research/slot-selection.md)، [TESTING ۲۷ تا ۲۹](../../docs/TESTING.md) | مدل اولیه tries با مشاهده زنده بعدی تصحیح شده؛ rollback جامع هنوز آزمون نشده |
| امضای RSA-PSS و SquashFS به طول 31,274,410 | [rootfs-signed-content](../../docs/research/rootfs-signed-content.md)، [content-enforcement](../../docs/research/content-enforcement.md) | بررسی host و live hash؛ احراز metadata از enforcement محتوا تفکیک شده |
| RootFS جدید با LK و boot اصلی | [BOOT-FLOW، به‌روزرسانی ابتدای سند](../../docs/BOOT-FLOW.md)، [LK authentication](../../docs/research/lk-authentication-ghidra.md) | hash زنده مراحل بوت اصلی؛ فقط دامنه پیکربندی آزمایش‌شده |
| دو تغییر شاخه در LK | [lk-boot-auth-preview](../../docs/research/lk-boot-auth-preview.md)، [اسکریپت preview](../../tools/firmware/LkBootAuthPreview.java) | تنها database Ghidra؛ binary export و hardware test انجام نشده |
| DA و نسخه mtkclient و ACK | [RECOVERY](../../docs/RECOVERY.md)، [setup_mtkclient](https://github.com/mralinp/x28-flasher/blob/main/tools/recovery/setup_mtkclient.py)، [نتیجه identical](../../docs/research/patched-identical-write-result.md) | موفقیت نشست خواندن/نوشتن مشخص؛ خطاهای تاریخی به نسخه و ترتیب پروتکل وابسته بودند |
| restore صفحه تغییرکرده | [changed-page-restore-result](../../docs/research/changed-page-restore-result.md) | صفحه ۴ KiB؛ دو write یک MiB؛ ۱۸ read و stock-B return |
| محدودیت مستقل Recovery | [recovery-route-proof](../../docs/research/recovery-route-proof.md)، [misc-probe-plan](../../docs/research/misc-probe-plan.md)، [rootfs-a-write-plan](../../docs/research/rootfs-a-write-plan.md) | طرح‌های محدود؛ خرابی misc ممکن است قبل از پنجره USB اثر بگذارد |
| build و چهار compat library | [BUILD](../../docs/BUILD.md)، [FIRMWARE-INVENTORY](../../docs/FIRMWARE-INVENTORY.md)، [userspace.sh](../../tools/build/userspace.sh)، [stage_native.py](https://github.com/mralinp/x28-flasher/blob/main/tools/build/stage_native.py) | ImageBuilder عمومی + assembly خصوصی؛ تصویر رسمی target برد نیست |
| نخستین بوت، overlay و boot counter | [first_boot.py](https://github.com/mralinp/x28-flasher/blob/main/tools/build/first_boot.py)، [package_ubi.py](https://github.com/mralinp/x28-flasher/blob/main/tools/build/package_ubi.py)، [x28-bootok](../../package/x28-bootok/files/x28-bootok.init)، [preinit ذخیره‌سازی](../../package/x28-storage/files/x28-user-data.preinit) | UUID و tries اثر واقعی دارند؛ دستور حذف overlay زنده ارائه نشده |
| console اولیه و `/dev/console` | [native-image-completeness](../../docs/research/native-image-completeness.md)، [BUILD](../../docs/BUILD.md) | Kernel فاقد devtmpfs؛ askfirst فعلی با getty stock متفاوت است |
| MIPC، CID، validation، IPv6 | [NATIVE-CELLULAR](../../docs/NATIVE-CELLULAR.md)، [x28_mipc.sh](../../package/x28-mipc/files/x28_mipc.sh)، [x28-modem.init](../../package/x28-modem/files/x28-modem.init)، [تست‌های mocked](../../tests/test_native.py) | پیاده‌سازی و آزمون زنده جدا گزارش شده؛ یک SIM؛ ۳۱ case تاریخی mock |
| Wi-Fi فعلی و شروع باز | [mtwifi.detect](../../package/x28-wifi/files/mtwifi.detect)، [mtwifi.sh](../../package/x28-wifi/files/mtwifi.sh)، [TESTING ۳۶/۳۸/۳۹](../../docs/TESTING.md) | درایور vendor؛ open default با WPA2 تنظیم‌شده در برخی snapshotها متفاوت است |
| feed و subset واقعی ipset | [vendor-ipset-packaging](../../docs/research/vendor-ipset-packaging.md)، [signed-package-feed](../../docs/research/signed-package-feed.md)، [kmod stubs](../../package/x28-kmod-stubs/stubs.txt)، [TESTING ۳۶](../../docs/TESTING.md) | نصب موفق، شاهد همه set typeها نیست؛ `hash:ip,mac` غایب |
| CRC و ماژول‌های بدون version | [kernel-module-crc](../../docs/research/kernel-module-crc.md)، [x28-kmods](../../package/x28-kmods/README.md)، [loader](../../package/x28-kmods/files/x28-kmods.init) | ریسک ABI باقی است؛ محل جدید moduleها بعد از آخرین reboot ثبت‌شده تغییر کرده |
| VPN و Passwall2، اعداد CPU/سرعت | [TESTING ۳۷ تا ۴۱](../../docs/TESTING.md)، [PASSWALL2](../../docs/PASSWALL2.md) | مسیر، جهت و backend هر عدد در مقاله آمده؛ تخمین ۳۰۰–۴۵۰ با اندازه‌گیری تفکیک شده |
| guard و ICMP/Direct/localhost | [PASSWALL2](../../docs/PASSWALL2.md)، [x28-killswitch.sh](https://github.com/mralinp/x28-flasher/blob/main/tools/build/x28-killswitch.sh)، [TESTING ۴۰](../../docs/TESTING.md) | همه‌پروتکل/همه‌مبدأ نیست؛ clean-flash و tunnel-down کامل آزمون نشده |
| soak و حرارت | [TESTING ۳۳](../../docs/TESTING.md)، [THERMAL](../../docs/THERMAL.md)، [HARDWARE](../../docs/HARDWARE.md) | ۲۶٫۶ ساعت مجموع، نه یک اجرای بی‌وقفه ۴۸ساعته؛ وضعیت فن native روشن نیست |
| upstream و کار آینده | [mainline feasibility](../../docs/research/x28-mainline-kernel-feasibility.md)، [mainline roadmap](../../docs/research/x28-mainline-roadmap.md)، [GPL request](../../docs/research/gpl-source-request.md)، [TASKS](../../docs/TASKS.md) | تحلیل و پیشنهاد؛ نه Linux 6.x بوت‌شده و نه تعهد زمان‌بندی |
| flasher جدید و حذف Rust | [x28-flasher-binary](../../docs/research/x28-flasher-binary.md)، [طراحی Rust کنارگذاشته‌شده](../../docs/research/rust-flasher-design.md)، [launcher فعلی](https://github.com/mralinp/x28-flasher/blob/main/tools/x28-flasher/x28_flasher.py) | ابزار فعلی front end بر recovery است؛ frozen binary هنوز مبنای راهنمای نوشتن عمومی قرار نگرفت |

</div>

<h3 dir="rtl" align="right">تاریخچه‌ای که برای ترتیب روایت استفاده شد</h3>

**تکمیل شواهد دسترسی اولیه پس از بازبینی نویسنده:** چت موجود با عنوان دقیق **Assess ZLT X28 firmware access** و شناسه `01a155b7-1881-77a3-a9ea-2cce881621f0`، مراحل اکتبر ۱۹–۲۰ پیش از commit اول را ثبت کرده است. بخش‌های اصلی: turn با شناسه `01a155bf-9211-7700-b4a5-355c20da5b9a` برای Telnet و UID 1000؛ و `01a155ca-16c2-77e3-b07d-e7bdb1e6db17` برای root SSH، اصلاح مسیر کلید و cleanup. این سابقه از ابزار خواندن چت بررسی شد؛ فقط summary عنوان مبنای نتیجه نیست.

آثار همان کار **داخل این workspace** نیز وجود دارند، ولی git-ignored و بخشی از snapshot عمومی commit نیستند:

- `you-are-a-senior-embedded-linux/work/router-js/dmz.js` و فایل‌های هم‌پوشه: کد صفحه DMZ و زمینه درخواست API.
- `dropbear-start-original.py`: فرمان اجرای Dropbear با host key موقت، bind به LAN و پورت 2222 و password-auth بسته.
- `recovery-original.py`: کپی کلید عمومی به `/etc/dropbear/authorized_keys` و mode برابر 600، از مسیر CGI.
- `you-are-a-senior-embedded-linux/outputs/router-root-ssh/connect.sh`: گزینه‌های دقیق RSA، کلید اختصاصی، known_hosts و strict host checking.

فایل‌های `*-original.py` credential دارند و پوشه خروجی SSH حاوی private key است؛ **هیچ‌یک برای انتشار کپی یا ضمیمه نشوند**. فقط قطعه‌فرمان‌های بدون secret به مقاله منتقل شد. در چت، Telnet با `telnetd -b 192.168.70.1 -p 2323` واقعاً باز شد، shell برابر BusyBox 1.30.1/ash و UID 1000 بود، و بعد SSH خروجی `uid=0(root) gid=0(root)` داد. فرمان اجرای Telnet بدون login به‌عنوان مسیر موفق معرفی نشد، چون اجرای آن متوقف شده بود. شکست Ed25519 نیز به‌تنهایی اثبات عدم پشتیبانی نیست؛ مسیر اشتباه authorized_keys عامل مخدوش‌کننده است. نسخه اولیه مقاله این مرحله را مستندنشده می‌دانست؛ این ارزیابی با شواهد بازیابی‌شده جایگزین شد. برای داوری عمومی، یک excerpt پالایش‌شده با تأیید نویسنده کافی است؛ export کامل چت شامل داده خصوصی است. در بازبینی بعدی، اشاره به مسیر خصوصی JavaScript در متن مقاله با راهنمای ورود Super Admin، بررسی Network/Sources و Copy as cURL جایگزین شد. نمونه cURL فقط خواندن وضعیت DMZ است و اجرا نشده؛ نیاز به حفظ اطلاعات نشست توضیح داده شده، اما کوکی به‌تنهایی کافی فرض نشده است: `main.js` بررسی‌شده، `sessionId` و برای POST مقدار `token` را از `sessionStorage` به JSON اضافه می‌کند.

تاریخ commit با تاریخ انجام آزمایش الزاماً یکی نیست. جدول، زمان ثبت تغییرات مهم را نشان می‌دهد؛ زمان مشاهدات از سند مربوط گرفته شده است.

<div dir="rtl" align="center">

| commit | تاریخ | اهمیت |
| ---: | ---: | ---: |
| `2ae70f4` | ۲۰۲۶-۱۰-۲۰ | آغاز مخزن با دسترسی و کار stock موجود |
| `4eca019` | ۲۰۲۶-۱۰-۲۲ | ابزار backup و USB |
| `c29c043` / `fcac19b` | ۲۰۲۶-۱۰-۲۳ | ABI و build userspace |
| `d9cc533` | ۲۰۲۶-۱۰-۲۳ | آزمون RAM روی دستگاه |
| `422099b` | ۲۰۲۶-۱۰-۲۶ | ثبت UART و بررسی‌های بوت |
| `682e8d8` | ۲۰۲۶-۱۰-۲۸ | pinout تأییدشده و getty |
| `b4cbe4a` / `4961bdd` | ۲۰۲۶-۱۰-۲۸ | اصلاح ACK و آزمون identical |
| `b75da12` | ۲۰۲۶-۱۰-۲۹ | ثبت restore صفحه تغییرکرده |
| `8cc66d9` / `fc72b55` / `6a3a8c8` | ۲۰۲۶-۱۰-۲۹ | staging، management و UBI |
| `22302bd` | ۲۰۲۶-۱۱-۰۳ | ثبت ریسک RAM در torrent |
| `f50c91d` / `1663b4c` / `b9c1a96` | ۲۰۲۶-۱۱-۰۴ | کنارگذاشتن Rust، front end و آماده‌سازی frozen runtime |

</div>

<h2 dir="rtl" align="right">اختلاف منابع و تصمیم تحریریه</h2>

**زمینه بازار در مقدمه قسمت اول:** بنا به توضیح نویسنده، معرفی 5G در ایران، رواج X28 و عرضه استوک پیش از داستان پروژه قرار گرفت. [نقشه nPerf](https://www.nperf.com/fa/map/IR/-/1795.IranCell/signal) وجود پوشش اندازه‌گیری‌شده کاربران را نشان می‌دهد؛ نقشه جامع یا تضمین پوشش هر نشانی نیست. [مقایسه بازار دورنگر](https://doornegar.com/مقایسه-zlt-x28-و-grayten-gt525؛-کدام-مودم-5g-ارزش-خرید-بیشت/) X28 را محبوب و پرفروش در بخش استوک توصیف می‌کند، اما آمار مستقل سهم بازار ارائه نمی‌دهد. بنابراین متن از «یکی از مدل‌های شناخته‌شده و پرطرفدار» استفاده می‌کند، نه رتبه قطعی «محبوب‌ترین مودم ایران». عرضه استوک به معنی یکسان‌بودن firmware یا revision همه نمونه‌ها نیست. این منابع فقط زمینه بازارند؛ مشخصات و نتایج مهندسی همچنان از پروژه می‌آیند.

1. **تاریخ قدیمی STATUS و TASKS:** نتایج جدیدتر TESTING مقدم‌اند. VPN دیگر صرفاً TODO نیست و استفاده گوشی روی Wi-Fi ثبت شده، ولی آزمون جامع Wi-Fi تمام نشده است.
2. **pinout نامعلوم در متن UART قدیمی:** جدول Verified setup مورخ ۲۰۲۶-۱۰-۲۸ در RECOVERY نتیجه نهایی است. نویسنده در ۲۰۲۶-۱۱-۰۴ استفاده از ماژول TXS0108E و رگولاتور تأمین ۱٫۸ ولت را تأیید و عکس چیدمان را ارائه کرد؛ جهت فیزیکی و شماره کانال‌ها همچنان باید با pinout کنترل شوند.
3. **tries در طرح انتخاب slot:** توضیح شمارنده کاهشی طرح آفلاین با مشاهده افزایش ۰ به ۱ در دستگاه جایگزین شد. تعداد کل تلاش و تمام سیاست fallback هنوز قطعیت آزمون جامع ندارد.
4. **امضا و boot:** بخش‌هایی که custom boot را نامعلوم می‌دانند تاریخی‌اند. boot native و hashهای نوامبر شاهد جدیدترند؛ patch Ghidra همچنان deploy نشده است.
5. **Passwall2 «LAN throughput unproven»:** بخش پایانی قدیمی PASSWALL2 با TESTING ۴۱ به‌روزرسانی معنایی شد؛ تخمین سقف هنوز measured نیست.
6. **محل module و زمان load:** reboot موفق با مسیر قدیمی ثبت شده؛ انتقال به `/lib/modules/x28` بعد از آن است. کد فعلی منتظر tries می‌ماند؛ «۳۰ ثانیه» در BUILD عدد قطعی نسخه فعلی نیست.
7. **`--tproxy-modules`:** متن قدیمی PASSWALL2 با argparse واقعی `first_boot.py` تطبیق داده شد؛ گزینه فعلی و اجباری `--kmods` است.
8. **Wi-Fi با WPA2 در STATUS:** حالت تنظیم‌شده دستگاه است؛ default تصویر تازه در کد `encryption=none` است. هشدار نصب اولیه بر پایه کد و آزمون clean-flash نوشته شد.
9. **گرمای native:** ادعای قطعی کاهش ۶۵ به ۴۰ درجه «بدون فن» حذف شد؛ THERMAL وضعیت فن هنگام آن اندازه‌گیری را ثبت‌نشده می‌داند.
10. **مجوز:** کل مخزن در تاریخ مبنا GPL-3.0-or-later شده؛ sourceهای بعضی packageها GPL-2.0-only هستند. این به معنی مجوز انتشار firmware، SDK یا module خصوصی نیست.

<h2 dir="rtl" align="right">تصاویر و رسانه‌ها</h2>

تصاویر محتوایی اولیه `docs/images/` به‌صورت بصری بازبینی شدند: JPGهای برد و UART و PNG مربوط به Passwall2. در ادامه بازبینی قسمت اول، سه تصویر تازه نویسنده برای ماژول تبدیل سطح، مبدل USB به TTL و چیدمان مدار هم به‌صورت بصری بررسی و به مقاله افزوده شدند. PNG/SVGهای `docs/assets/` عمدتاً logo، icon و social preview هستند؛ تصویر آزمایش یا دیاگرام معماری مستقل به حساب نیامدند. WebP محتوایی یافت نشد. نسخه تازه یا عکس stock تولید نشده است.

<div dir="rtl" align="center">

| مسیر دقیق از ریشه مخزن | ارجاع نسبی از مقاله | کاربرد و caption |
| ---: | ---: | ---: |
| `docs/images/x28-board-back.jpg` | `../../docs/images/x28-board-back.jpg` | نمای پشت برد، محل footprint و هویت برد؛ مقاله ۱ و زمینه سخت‌افزار مقاله ۳ |
| `docs/images/x28-uart-candidate.jpg` | `../../docs/images/x28-uart-candidate.jpg` | بزرگ‌نمایی سه سوراخ UART؛ مقاله ۱ و پیش‌نیاز مشاهده Recovery در مقاله ۲ |
| `docs/images/x28-passwall2-luci.png` | `../../docs/images/x28-passwall2-luci.png` | وضعیت Core و connection checkها؛ مقاله ۴ |
| `docs/images/usb-ttl-module.png` | `../../docs/images/usb-ttl-module.png` | تصویر معرفی مبدل USB به TTL؛ مقاله ۱؛ نه مدرک مدل دقیق مبدل آزمایش |
| `docs/images/level-shifter.png` | `../../docs/images/level-shifter.png` | تصویر معرفی TXS0108E با برچسب VA/VB؛ مقاله ۱؛ تفاوت با نام V1 ماژول نویسنده توضیح داده شده |
| `docs/images/uart-circut.jpeg` | `../../docs/images/uart-circut.jpeg` | عکس چیدمان واقعی مدار؛ مقاله ۱؛ نه شماتیک یا تأیید تک‌تک سیم‌ها |

</div>

هر استفاده alt فارسی، caption و توضیح اهمیت فنی دارد. عکس نزدیک UART مورب است؛ annotation پیشنهادی باید پیش از انتشار با نویسنده تطبیق داده شود. برچسب TX/RX بر اساس حدس عکس افزوده نشده است. نام کوتاه node در screenshot دیده می‌شود؛ endpoint، UUID یا secret آشکار دیده نشد، ولی پوشاندن نام نمایشی با اجازه نویسنده برای نسخه انتشار مناسب است. تصویر اصلی تغییر نکرده است.

**عکس تکمیلی نویسنده، ۲۰۲۶-۱۱-۰۴:** فایل `photo_2026-11-04 07.37.50.jpeg` بدون ویرایش به `articles/sisoog/images/x28-uart-txs0108e-setup.jpeg` کپی شد و ابتدا در قسمت اول با مسیر نسبی `images/x28-uart-txs0108e-setup.jpeg` استفاده شد. در بازبینی بعدی، ارجاع مقاله با عکس تازه `../../docs/images/uart-circut.jpeg` جایگزین شد؛ فایل قبلی برای حفظ سابقه حذف نشده است. این تصویر از پوشه `docs/` نیست؛ مدرک جدیدی است که نویسنده برای همین مجموعه ارائه کرده است. متن استفاده از TXS0108E و رگولاتور ۱٫۸ ولتی بر تأیید صریح نویسنده تکیه دارد، نه تشخیص شماره قطعه از عکس. نویسنده سپس روشن کرد که خروجی رگولاتور به V1 سمت A و OE ماژول وصل بوده؛ V1 نام روی ماژول برای تغذیه سمت A است و VCCA نام تغذیه متناظر در دیتاشیت تراشه است. [صفحه رسمی TI](https://www.ti.com/product/TXS0108E) مرجع مشخصات دو تغذیه و شرط `VCCA ≤ VCCB` است. مقادیر پیشنهادی VCCA/VCCB از مشخصات قطعه آمده‌اند؛ عکس، تأیید سیم‌کشی همه پایه‌ها یا اندازه‌گیری مستقل ولتاژ نیست. مدل رگولاتور حدس زده نشده و تصویر هیچ تغییری نکرده است.

نمودارهای Mermaid در مقالات ۲ و ۳ تألیفی و inline هستند و عکس واقعی معرفی نشده‌اند. نمودار بوت، BootROM را به‌عنوان مرحله معماری و مسیر USB تأییدشده را از Preloader جدا می‌کند. نمودار مودم میان control و data plane تمایز می‌گذارد؛ همه جزئیات transport به source دقیق vendor نسبت داده نشده‌اند.

<h2 dir="rtl" align="right">موارد نیازمند تأیید نویسنده پیش از انتشار</h2>

- انتشار excerpt پالایش‌شده از شواهد initial root، در صورت نیاز تحریریه؛ روش shell اکنون با فایل محلی و چت تطبیق داده شده است. روش SIM-unlock پیش از این آزمایش همچنان معلوم نیست و به CGI نسبت داده نشده است.
- annotation جهت‌دار pinout و مسیر کانال‌های TX/RX؛ مدل level shifter اکنون TXS0108E و تغذیه کم‌ولتاژ ۱٫۸ ولت با رگولاتور تأیید شده است. نویسنده اتصال خروجی ۱٫۸ ولت رگولاتور به V1 سمت A و OE را صریحاً تأیید کرده است. مدل دقیق رگولاتور و شماره کانال‌های استفاده‌شده هنوز مشخص نیست.
- علت شکست C-to-C: فقدان مقاومت CC هنوز فرض است، نه اندازه‌گیری.
- ظرفیت و marking فیزیکی RAM/NAND و package مودم زیر شیلد، اگر قرار است به‌جای شواهد نرم‌افزاری ادعای خواندن قطعه مطرح شود.
- وضعیت فن هنگام دمای native، مدل، اندازه، محل نصب و منبع تغذیه؛ ادعای آزمایش کنترل‌شده حرارت فعلاً مناسب نیست.
- کدام build نهایی حامل تمام Passwall2، module loader در مسیر جدید و kill switch واقعاً clean-flash و reboot شده است؟ سند فعلی چنین نتیجه‌ای ندارد.
- دامنه fallback خودکار، انتخاب میان رکوردهای متفاوت misc و Recovery بعد از قطع برق؛ آزمایش جدید بدون طرح مستقل پیشنهاد نشده است.
- طولانی‌مدت WireGuard/TPROXY، reconnect مودم، SIM/PIN، اپراتورهای دیگر، set typeهای ipset و آزمون کامل Wi-Fi.
- آیا روایت اول‌شخص انگیزه و انتخاب‌های مهندسی را درست بازتاب می‌دهد؟ متن بر اهداف README تکیه دارد و خاطره، دیالوگ یا benchmark اختراع نکرده است.

<h2 dir="rtl" align="right">شواهد تصویری یا آزمایشی کمبوددار</h2>

عکس روی دیگر برد و نقشه annotationشده مسیر سیگنال‌های UART؛ عکس چیدمان واقعی اکنون اضافه شده است. همچنین capture پالایش‌شده اولین boot A؛ screenshot صفحه `x28_mipc` با شناسه‌ها حذف‌شده؛ وضعیت LAN/DHCP و IPv6؛ transcript کامل فرمان‌های استخراج اولیه UBI/SquashFS؛ config کامل peer آزمایشگاهی بدون کلید؛ فرمان‌های دقیق و خروجی خام عمومی benchmark؛ آزمون مستقیم LAN سیمی؛ clean-flash/reboot نهایی؛ soak کامل ۴۸ساعته؛ و تست روی دستگاه دوم در مخزن موجود نیست یا شواهد عمومی کافی ندارد. جای خالی این موارد با لاگ ساختگی یا تصویر unrelated پر نشده است.

<h2 dir="rtl" align="right">بازبینی دستورهای خطرناک</h2>

<div dir="rtl" align="center">

| عملیات | خطر یا پیش‌نیاز | تصمیم متن |
| ---: | ---: | ---: |
| CGI/DMZ injection و Telnet موقت | تغییر تنظیم gateway، login بدون رمزنگاری، listener ریشه؛ نشست معتبر مالک و cleanup لازم است | روایت تاریخی همراه پورت/UID و قطعه‌فرمان واقعی؛ credential و session token حذف شده‌اند |
| کپی authorized_keys و اجرای Dropbear | بازنویسی فایل ممکن است کلید قبلی را حذف کند؛ bind و password-auth باید بررسی شوند | scope نمونه و هشدار حفظ کلیدهای قبلی آمده؛ private key هرگز به متن منتقل نشده است |
| `slot_entry.py ... --write` و `restore_entry.py ... --write` | NAND، هویت واحد، backup دوم، UART زنده، receipt، candidate و recovery بررسی‌شده | فرمان آماده اجرا منتشر نشده؛ dry-run و سند دقیق معرفی شده |
| هر تغییر `misc`، `dd-nand` یا slot switch | آسیب metadata می‌تواند پیش از USB اثر کند؛ B ممکن است A را repair کند | فقط نتیجه و روش بررسی توصیف شده؛ دستور خام ارائه نشده |
| patch یا export LK و تغییر `boot_*` | policy Preloader و container و LK دوم حل نشده | فقط offsetهای تحقیق با برچسب preview؛ دستور ساخت/flashing ندارد |
| تغییر inittab و reload init | نوشتن overlay و ایجاد shell فیزیکی | تاریخچه توصیف شده؛ روش unlock اولیه نامیده نشده |
| پاک‌کردن extroot، reset و حذف `upper` | پاک‌شدن تنظیمات یا shadowکردن state جدید | دستور حذف زنده و یک‌خطی مخرب کپی نشده |
| load module بدون CRC | امکان crash یا فساد حافظه | فقط build میزبان و loader پروژه توضیح داده شده؛ force-load عمومی ندارد |
| `opkg install` و تغییر Passwall2 | نوشتن overlay، تغییر ترافیک یا قطع proxy | با دامنه و پیش‌نیاز، از read-only جدا آمده است |
| `read_verify` و backup | flash write ندارند؛ DA اینترنت را تا power-cycle قطع می‌کند | اثر دسترس‌پذیری و محرمانگی فایل خروجی گفته شده است |
| benchmark | مصرف حجم و بار پردازنده | مسیر و حدود اندازه‌گیری مشخص؛ اجرای تازه انجام نشده |

</div>

فرمان‌های build نمونه به backup و SDK خصوصی و مسیرهای آماده نیاز دارند. `NEW` و `<ubi-dir>` جایگزین صریح‌اند؛ فرمان، نصب یک‌مرحله‌ای برای checkout تمیز نیست. خروجی `NOT-FLASHABLE` مجوز نوشتن نیست. فرمان‌های تاریخی که با interface فعلی فرق دارند، به‌عنوان تاریخی توضیح داده شده‌اند و بی‌صدا modernize نشده‌اند.

<h2 dir="rtl" align="right">الگوی سیسوگ و آماده‌سازی انتشار</h2>

با درخواست نویسنده، لحن چهار مقاله به فارسی محاوره‌ای و روایت مستقیم تجربه تغییر کرد: جمله‌های کوتاه‌تر، سؤال‌های عملی و توضیح شکست‌ها به زبان روزمره. دستورها، خروجی‌ها، نام‌ها، نسخه‌ها و محدودیت‌های فنی در این ویرایش حفظ شدند. یادداشت تحریریه برای پیگیری منابع، لحن مستند خود را نگه می‌دارد.

سه نمونه خواسته‌شده خوانده شدند: [TK-2510 و بررسی سخت‌افزار](https://sisoog.com/irancell-td-lte-modem-tk-2510-can-be-hacked-unlocked/)، [بررسی EC200U](https://sisoog.com/full-review-of-quectel-ec200u-modem/) و [ساخت مودم با EC200A](https://sisoog.com/ec200a-usb-modem/). اولی مسیر کشف را با عکس برد و خروجی بوت پیش می‌برد؛ دومی معماری را کنار تصاویر قطعه توضیح می‌دهد؛ سومی پیش‌نیاز و اقدام را نزدیک هم می‌آورد. از این شیوه ارائه استفاده شد، نه از متن یا مشخصات فنی آن دستگاه‌ها برای X28.

برای WordPress سیسوگ، عنوان پست را از عنوان ثابت مجموعه به‌همراه شماره و عنوان قسمت بسازید تا پست‌ها از هم قابل تشخیص باشند؛ در فایل‌ها H1 عنوان مشترک مجموعه و اولین H2 عنوان قسمت است. عنوان‌های بعدی H2/H3 ساختار بدنه را مشخص می‌کنند؛ کدها و جدول‌های عددی LTR و متن اصلی RTL باشند. نقل‌قول ایمنی باید نزدیک اقدام بماند. عکس‌ها را از مسیر اصلی در media library بارگذاری و لینک نسبی را با URL واقعی جایگزین کنید؛ caption و alt فارسی منتقل شوند. برای Mermaid، اگر افزونه سایت پشتیبانی ندارد، خروجی SVG از همان تعریف تأییدشده تهیه شود؛ تصویر جدیدی در این کار ساخته نشده است.

مقاله‌ها از نظر شمارش ساده whitespace و با حذف code fence حدود ۲۱۰۰ تا ۲۷۰۰ واژه دارند؛ شمارش واژه فارسی در سامانه انتشار ممکن است متفاوت باشد. برای نسخه چاپی کوتاه‌تر، جدول کامل پارتیشن را می‌توان در بخش بازشونده گذاشت، اما هشدارها، واحدها، جهت benchmark و qualifiers حذف نشوند. در انتشار، لینک مستندات را به [snapshot ثابت مخزن](https://github.com/mralinp/zlt-x28-openwrt/tree/b9c1a96) نگه دارید تا تغییرات آینده معنی شواهد را عوض نکنند.

<h3 dir="rtl" align="right">عنوان و توضیح پیشنهادی SEO</h3>

<div dir="rtl" align="center">

| بخش | عنوان SEO | توضیح پیشنهادی |
| ---: | ---: | ---: |
| ۱ | مهندسی معکوس ZLT X28؛ سخت‌افزار، UART و دسترسی Linux | بررسی مستند MT6890 و RG500L-EU، کنسول UART یک‌وهشت‌ولتی و شروع پروژه OpenWrt روی یک مودم X28. |
| ۲ | backup فریمور ZLT X28؛ NAND، بوت A/B و Recovery | نقشه ۵۱ پارتیشن، backup با hash، بررسی امضای RootFS و تجربه mtkclient و بازیابی محدود NAND در X28. |
| ۳ | ساخت OpenWrt برای ZLT X28 و اتصال 5G با MIPC | ساخت userspace 23.05.5 روی Kernel سازنده، بوت slot A و اتصال اینترنت سلولی به netifd با x28_mipc. |
| ۴ | WireGuard، OpenVPN و Passwall2 روی ZLT X28 | سازگاری ماژول‌ها با Kernel 4.19، راه‌اندازی TPROXY و نتایج واقعی سرعت، CPU و محدودیت RAM در X28. |

</div>

<h2 dir="rtl" align="right">نتیجه کنترل نهایی</h2>

کنترل تحریریه شامل پیوستگی چهار قسمت، حجم، تمایز وضعیت تاریخی و فعلی، منابع claims، مسیرهای Markdown و تصویر، دستورهای موجود و افشای اطلاعات بود. جدول پارتیشن با metadata نمونه و مجموع اندازه تطبیق می‌شود. اعداد benchmark با TESTING مقایسه شده‌اند. هیچ تست firmware یا اتصال live برای تأیید دوباره نتایج اجرا نشده است. مجموعه برای **بازبینی انسانی پیش از انتشار** آماده است؛ تأیید برق UART و موارد مشخص‌شده بالا همچنان به نویسنده نیاز دارد.


<h2 dir="rtl" align="right">گسترش مجموعه در ۲۰۲۶-۱۱-۱۰؛ از دسترسی اولیه تا نگهداری فریمور</h2>

مبنای بازبینی شش فصل تازه، درخت محلی commit `e1ded5c`، کد و test log موجود و به‌روزرسانی هم‌زمان اسناد وضعیت در ۲۰۲۶-۱۱-۱۰ است. تغییرهای خارج از articles/sisoog که در working tree دیده می‌شوند، کار این بازبینی نیستند و دست نخورده‌اند. به‌جای تکیه بر شماره release قدیمی در README یا STATUS، ادعاهای تازه با MODULES، PACKAGE-FEED، TESTING بخش‌های ۴۲ تا ۵۳، پیاده‌سازی platform.sh و workflowهای Image و Sign image تطبیق داده شدند. در این کار هیچ تست دستگاهی یا اجرای workflow انجام نشد.

تأیید نویسنده در همین گفت‌وگو، ۲۰۲۶-۱۱-۱۰: Tozed، SDK را در اختیار پروژه گذاشته است. تشکر از شرکت در نقشه مجموعه و فصل‌های ۵ و ۱۰ آمده؛ تاریخ تحویل، نسخه کامل SDK، دسترسی عمومی، اجازه توزیع تمام اجزا یا حمایت رسمی از فریمور استنباط نشده است. متن قدیمی درخواست source در docs/research/gpl-source-request.md سابقه است و به‌تنهایی وضعیت فعلی دریافت SDK را توصیف نمی‌کند.

<div dir="rtl" align="center">

| فصل تازه | مسئله و آموزش | منابع اصلی و محدودیت |
| ---: | ---: | ---: |
| ۵. SDK و driver | toolchain، ABI، MODVERSIONS، مصرف‌کننده module و خطای NCM | MODULES، BUILD، package/x28-kmods؛ driver مودم و Wi-Fi بازنویسی‌شده یا mainline معرفی نشده‌اند |
| ۶. feed | سه حالت capability موجود، module ساخته‌شده و dependency پشتیبانی‌نشده؛ امضا و نسخه | PACKAGE-FEED، release_check، feed_release، TESTING ۴۵ تا ۵۰؛ بازکامپایل همه بسته‌ها ادعا نشده |
| ۷. X28 و PRO | تشخیص PCI، تک‌کارت/دوکارت، زمان شروع DHCP و تست هم‌شرط | MODULES، BUILD، TESTING ۴۲ تا ۴۴ و ۵۱؛ سایر rebrandها و همه benchmarkهای PRO تأیید نشده |
| ۸. امضای تصویر | hash، board metadata، fwtool/usign/ucert و signer جدا | image_sign.sh، image.yml، sign-image.yml، TESTING ۵۳d؛ CI کامل، انقضا و revocation آزموده‌شده معرفی نشده |
| ۹. ارتقای A/B | target غیرجاری، RAM root، verify منطقی و misc | platform.sh، sysupgrade-design، TESTING ۵۲ و ۵۳؛ آزمایش تاریخی درجا با سیاست جدید #509 تفکیک شده |
| ۱۰. انتشار | ورودی عمومی/خصوصی، assembly، clean flash، upgrade و OTA | workflowها، BUILD، PACKAGE-FEED، TESTING؛ وجود فایل CI به‌عنوان اجرای موفق یا OTA آماده گزارش نشده |

</div>

<h3 dir="rtl" align="right">اختلاف منابع که در روایت حل شد</h3>

- در آغاز بازبینی، STATUS با تاریخ ۸ نوامبر و بعضی جدول‌ها sysupgrade را آینده می‌دانستند؛ هنگام نگارش، STATUS و overviewها به ۱۰ نوامبر به‌روز شدند. TESTING در ۹ نوامبر آزمون واقعی ۵۳ و ۵۳d را ثبت کرده است. فصل‌های تازه این شاهدها و وضعیت جدید را بیان می‌کنند، بدون تعمیم به OTA بی‌حضور کاربر.
- امضای feed، امضای sysupgrade و امضای vendor در LK مستقل توضیح داده شده‌اند. امضای پروژه، امضای Tozed یا secure boot کامل معرفی نشده است.
- policy فعلی x28_target در platform.sh همیشه slot غیرجاری را انتخاب می‌کند؛ آزمون‌های قدیمی شامل in-place و marker انتخاب B بوده‌اند. پذیرش و چرخه امضاشده ۵۳d شاهد نسخه آزمایش‌شده است، نه تأیید سخت‌افزاری تمام revisionهای بعدی.
- نوشتن native روی B، stock داخلی را حذف می‌کند؛ عبارت قدیمی «B همیشه stock است» فقط در مرحله اولیه معنا دارد.
- SDK، ImageBuilder و بازکامپایل module تفکیک شده‌اند. بسته‌های userspace رسمی که آماده مصرف می‌شوند، به‌عنوان ساخته‌شده از source توسط پروژه معرفی نشده‌اند.
- فرمان‌های source قدیمی در چهار مقاله نخست تاریخی باقی مانده‌اند و banner دارند. لینک ابزارهایی که منتقل شده‌اند به مخزن x28-flasher هدایت شده است؛ دسترسی عمومی آن مخزن پیش از انتشار باید بررسی شود.


**لایه update تازه:** package/x28-update، ابزار x28-upgrade، check نسخه، اعلان و پنجره تأیید LuCI و tests/test_update.sh نیز خوانده شدند. حالت بدون آرگومان فقط check با درخواست شبکه و cache است؛ حالت -y دانلود، checksum، sysupgrade -T و سپس -n را اجرا می‌کند. هیچ‌کدام در تهیه مقاله اجرا نشدند. تفکیک پیاده‌سازی host-tested از آزمون دستگاه در فصل‌های ۹ و ۱۰ و نقشه مجموعه اضافه شد. «Nothing upgrades on its own» در STATUS فعلی، مبنای پرهیز از ادعای OTA بدون تأیید است.

<h3 dir="rtl" align="right">عنوان و توضیح پیشنهادی برای جست‌وجو؛ فصل‌های تازه</h3>

- **۵ — ساخت درایور برای ZLT X28 با SDK؛ سازگاری Kernel و ABI:** چرا module برای ARM64 کافی نیست و چطور driver ساخته‌شده روی Kernel واقعی آزموده می‌شود؟
- **۶ — ساخت feed امضاشده OpenWrt برای X28 و X28 PRO:** dependencyها، kmodهای واقعی و stubها، نسخه‌گذاری و انتشار امن packageها.
- **۷ — تفاوت X28 و X28 PRO در پورت OpenWrt:** پروفایل Wi-Fi، تشخیص PCI و رفع خطای DHCP بدون دست‌زدن به calibration واحد دیگر.
- **۸ — امضای فریمور OpenWrt با fwtool و ucert:** فرق hash و امضا، گواهی signer و بررسی تصویر پیش از نوشتن.
- **۹ — ارتقای A/B در ZLT X28؛ sysupgrade و Recovery:** چرا verify تصویر باید پیش از تغییر misc باشد و کدام آزمون‌ها واقعاً انجام شده‌اند؟
- **۱۰ — انتشار و نگهداری فریمور سفارشی X28:** از SDK و assembly تا CI، feed، آزمون دستگاه واقعی و مسیر آینده OTA.

<h3 dir="rtl" align="right">بازبینی انتشار این گسترش</h3>

فصل‌های تازه متن آموزشی مستقل دارند و برای پرکردن تعداد کلمه، مراحل یا نتایج تکراری اضافه نشده است. اندازه آن‌ها از هدف تقریبی ۲۰۰۰ تا ۳۵۰۰ واژه درخواست اولیه کوتاه‌تر است؛ برای انتشار می‌توان مباحث امضا و A/B را جدا حفظ کرد یا با نظر نویسنده به متن‌های بلندتر گسترش داد. فرمان‌های فلش خودکار و داده خصوصی اضافه نشده‌اند. نمودار جریان در فصل ۹، متن تألیفی در بلوک LTR است و لاگ واقعی معرفی نشده.

عکس تازه یا screenshot ساختگی اضافه نشده است؛ عکس‌های واقعی چهار قسمت نخست حفظ شده‌اند. برای فصل‌های تازه، screenshot پالایش‌شده Software/LuCI، Carrier و دو رادیوی PRO، نمونه metadata بدون secret، خروجی رد امضای نامعتبر و capture چرخه A/B می‌تواند با شاهد واقعی و اجازه نویسنده اضافه شود. تا آن زمان، جدول‌ها و کدها محتوای آموزشی اصلی‌اند.

پیش از انتشار: نسخه نهایی release و index feed تثبیت شود؛ هویت board_name برای PRO از حدس جدا بماند؛ دامنه آزمون policy جدید A/B و حفظ config بررسی شود؛ اجازه بازنشر تصویرها و اجزای vendor مستقل از تشکر بابت SDK بررسی شود. گزارش انقضا، revoke، قطع برق، fallback tries-6 و OTA سرتاسری بدون شاهد تازه به متن افزوده نشود.


<h2 dir="rtl" align="right">بازنگری جریان آموزشی؛ پیش از بازنویسی بعدی</h2>

درخواست تازه نویسنده: مجموعه باید تجربه ساخت یه دستگاه Embedded Linux رو منتقل کنه و هر پیشرفت عمده یه قسمت داشته باشه؛ تعریف روشن Preloader، LK، کنترل امضا، Device Tree و ABI پیش از استفاده لازم است. [طرح دوازده‌قسمتی](revision-plan.md) به‌همراه [دفتر شواهد issueها](revision-evidence.md) برای همین مرحله آماده شد. کیفیت و محتوای مفید قسمت‌های ۱ تا ۵ حفظ می‌شود؛ فصل‌های متراکم NAND/boot و build/network تقسیم می‌شوند و بخش‌های بعدی با مسئله، مشاهده، شکست، اصلاح و معیار موفقیت بازنویسی خواهند شد.

نویسنده تأیید کرد v0.78 در حال ساخت CI است؛ در بررسی فعلی artifact آن هنوز در release list قابل مشاهده نبود. نبود artifact در این زمان، شکست CI معرفی نشده و موفقیت یا تست واحد برای آن فرض نشده است. مرجع محلی جدید 9d0f8a0 است؛ مبنای قدیمی شش فصل قبلی با این تغییر بی‌صدا عوض نشده است.

این گام فقط طراحی و تطبیق شواهد است؛ متن و شماره‌بندی ده مقاله هنوز بازنویسی نشده‌اند. برنامه مستقل tasks/plan.md و وضعیت issueهای GitHub تغییر نکرده‌اند. پس از مرور این flow، بسته‌های بازنویسی و معیارهای پذیرش در خود طرح مشخص‌اند.

</div>
