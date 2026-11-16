<div dir="rtl" lang="fa">

<h1 dir="rtl" align="right">دفتر شواهد بازنویسی مجموعه؛ issue به‌عنوان مسیر یادگیری</h1>

**بازبینی: ۲۰۲۶-۱۱-۱۰ — مکمل [طرح جریان](revision-plan.md)**

این فهرست حاصل خواندن issueهای اولیه و اخیر، موضوع‌های Preloader/Device Tree و گفت‌وگوهای مسئله‌های کلیدی است؛ ممیزی کامل همه issueها نیست. متن خواسته، comment اجرای آزمایش، کد و تست واحد منابع متفاوت‌اند. بسته‌شدن issue یا merge شدن PR به‌تنهایی آزمون سخت‌افزاری نیست.

<h2 dir="rtl" align="right">وضعیت نسخه در این مرحله</h2>

نویسنده گفت v0.78 در حال ساخت در CI است. آخرین release قابل مشاهده با اتصال موجود v0.77.0 بود و checkout محلی 9d0f8a0. نتیجه در حال ساخت را نه شکست و نه انتشار موفق ثبت می‌کنیم. بعد از اتمام CI باید commit، artifact/hash، نتیجه امضا و scope تست همان نسخه افزوده شود. متن قبلی سری مبنای قدیمی‌تری دارد و فقط با تغییر شماره نسخه به‌روز نمی‌شود.

<h2 dir="rtl" align="right">مسئله‌ها و استفاده روایی از آن‌ها</h2>

<div dir="rtl" align="center">

| منبع | مسئله اصلی | نقش در روایت و حدود شاهد |
| ---: | ---: | ---: |
| [#1](https://github.com/mralinp/zlt-x28-openwrt/issues/1) | Dump all mtd partitions with verified checksums | backup همه پارتیشن‌ها؛ ملاک نهایی شمارش و checksum ثبت‌شده است. |
| [#2](https://github.com/mralinp/zlt-x28-openwrt/issues/2) | Find UART pads and capture the boot log | هدف اولیه console با نتیجه واقعی UART اشتباه نشود. |
| [#3](https://github.com/mralinp/zlt-x28-openwrt/issues/3) | Map boot flow: A/B slot selection, seccfg lock, signed rootfs | فرض اولیه درباره تصمیم LK با پژوهش جدید انتخاب slot در Preloader تصحیح شود. |
| [#4](https://github.com/mralinp/zlt-x28-openwrt/issues/4) | Write and test the way back to stock | backup با آزمون برگشت یکی نیست؛ دامنه restore ثبت شود. |
| [#18](https://github.com/mralinp/zlt-x28-openwrt/issues/18) | Request the GPL source from ZLT/Tozed in writing | منبع سابقه درخواست SDK؛ دریافت SDK و تشکر، تأیید صریح بعدی نویسنده است. |
| [#19](https://github.com/mralinp/zlt-x28-openwrt/issues/19) | Extract and inventory proprietary blobs from the stock rootfs | inventory اجزای vendor پیش از تصمیم به جایگزینی userspace. |
| [#28](https://github.com/mralinp/zlt-x28-openwrt/issues/28) | CI: build the OpenWrt 23.05 userspace rootfs with ImageBuilder | ImageBuilder بسته‌های آماده را ترکیب می‌کند؛ build همه sourceها نیست. |
| [#34](https://github.com/mralinp/zlt-x28-openwrt/issues/34) | test: boot the 23.05 userspace in QEMU and check fw3, netifd, LuCI | QEMU با Kernel دیگر، شاهد کارکرد سخت‌افزار مودم نیست. |
| [#40](https://github.com/mralinp/zlt-x28-openwrt/issues/40) | research: what the bootloader's rootfs signature check does on failure | نظر پایانی: خطای verifier به halt می‌رسد؛ نبود بررسی payload جدا بررسی شده. |
| [#76](https://github.com/mralinp/zlt-x28-openwrt/issues/76) | build: stage the private native rootfs with matching vendor components | staging خصوصی با وابستگی‌های مشخص؛ اجزای BSP دلخواه جایگزین نشوند. |
| [#114](https://github.com/mralinp/zlt-x28-openwrt/issues/114) | research: why the download-agent block write to misc is never acknowledged | مسیر آزمایش misc با restore اثبات‌شده اشتباه نشود. |
| [#122](https://github.com/mralinp/zlt-x28-openwrt/issues/122) | Native image: front LEDs and a full LAN (all ports, DHCP) | خرابی DHCP/jail و مالکیت LAN، داستان ملموس bring-up. |
| [#154](https://github.com/mralinp/zlt-x28-openwrt/issues/154) | Research sysupgrade for the A/B layout (no recovery slot) | تحقیق اولیه sysupgrade؛ اجرای امروز با متن شروع issue یکی نیست. |
| [#195](https://github.com/mralinp/zlt-x28-openwrt/issues/195) | docs: root filesystem tree and device tree summary | نام و ساختار rootfs و DT برای مقدمه آموزشی. |
| [#215](https://github.com/mralinp/zlt-x28-openwrt/issues/215) | research: where LK gets the device tree it passes to Linux | مسیر DTB داخل boot به Linux و DTB مستقل LK؛ دو مصرف‌کننده. |
| [#227](https://github.com/mralinp/zlt-x28-openwrt/issues/227) | research: is native WireGuard on the vendor kernel safe to use? | نظرهای آفلاین ABI و سپس تست واقعی تونل، دو سطح شاهد مستقل. |
| [#273](https://github.com/mralinp/zlt-x28-openwrt/issues/273) | fix(recovery): DA goes silent after GET-SYS-PROPERTY DA.SLA, identical flash of slot A fails | DA.SLA و ترتیب پروتکل؛ هشدار ابزار همیشه علت اصلی write نیست. |
| [#302](https://github.com/mralinp/zlt-x28-openwrt/issues/302) | research(flash): drop the recovery slot and make use of slot B: what does the preloader do without B? | تغییر تصمیم از recovery اختصاصی B؛ رفتار preloader در source تحلیل شده. |
| [#318](https://github.com/mralinp/zlt-x28-openwrt/issues/318) | feat(recovery): guarded flash for other units, with no UART and no SSH | هویت و pin هر دستگاه باید از backup خودش بیاد. |
| [#376](https://github.com/mralinp/zlt-x28-openwrt/issues/376) | x28-kmods: one reboot within 120 s leaves modules unloaded (Passwall2 'Missing components') | marker اولیه reboot سالم را هم مانع load می‌کرد؛ اصلاح و TESTING ۴۶/۴۸. |
| [#394](https://github.com/mralinp/zlt-x28-openwrt/issues/394) | research(feed): classify every 23.05 kmod as stub, out-of-tree buildable, or needs kernel change | مبنای طبقه‌بندی kmod، نه ادعای ساخت همه بسته‌ها. |
| [#417](https://github.com/mralinp/zlt-x28-openwrt/issues/417) | feat(build): the x28-* packages as real .ipk files | فایل دستی به package نسخه‌دار و install/remove قابل آزمون تبدیل شد. |
| [#418](https://github.com/mralinp/zlt-x28-openwrt/issues/418) | feat(feed): x28-base meta-package that protects the required packages | dependencyهای x28-base جلوی حذف اتفاقی نیازهای اصلی را می‌گیرند. |
| [#436](https://github.com/mralinp/zlt-x28-openwrt/issues/436) | feat(feed): x28-nrband and x28-switch as feed packages, in x28-base and on the image | وجود ابزار روی میز توسعه به معنی حضور آن در image تازه نبود. |
| [#450](https://github.com/mralinp/zlt-x28-openwrt/issues/450) | research(flash): slot B as a second native slot for A/B rollback | native B جای stock را می‌گیرد؛ قرارداد recovery تغییر می‌کند. |
| [#451](https://github.com/mralinp/zlt-x28-openwrt/issues/451) | feat(bootok): reset slot B's tries when a native B boots (Refs #450) | boot-health باید slot جاری B را هم بشناسد. |
| [#452](https://github.com/mralinp/zlt-x28-openwrt/issues/452) | chore(kmods): do not refuse on bootslot=b (Refs #450) | loader فقط برای bootslot=a کافی نبود. |
| [#457](https://github.com/mralinp/zlt-x28-openwrt/issues/457) | feat(sysupgrade): platform hooks and the misc writer, host-tested (Refs #154) | منطق write/verify/misc؛ تست host از تست NAND واقعی جدا. |
| [#458](https://github.com/mralinp/zlt-x28-openwrt/issues/458) | test(sysupgrade): hardware pass on the sacrificial unit with UART (Refs #154) | گفت‌وگو ترتیب آزمایش identical، تغییر، native B و محدودیت power-loss را روشن می‌کند. |
| [#465](https://github.com/mralinp/zlt-x28-openwrt/issues/465) | feat(sysupgrade): stage 2, leave the root and run the write from RAM (Refs #154) | ابزارهای موجود در محیط اصلی لزوماً در RAM root حاضر نیستند. |
| [#476](https://github.com/mralinp/zlt-x28-openwrt/issues/476) | feat(sysupgrade): signed sysupgrade images with fwtool metadata, built and published by CI | نظرهای identity/variants، روش standard signature و تست ۵۳d؛ issue باز چند خروجی متفاوت دارد. |
| [#477](https://github.com/mralinp/zlt-x28-openwrt/issues/477) | feat(sysupgrade): keep settings and the installed package list across an upgrade (-k) | حفظ config و package list هنوز مسئله باز؛ -n با -k برابر نیست. |
| [#478](https://github.com/mralinp/zlt-x28-openwrt/issues/478) | feat(sysupgrade): upgrade from the terminal and from LuCI's Flash firmware page | مسیر عمومی flash page هنوز نیازمند تست مستقل است. |
| [#488](https://github.com/mralinp/zlt-x28-openwrt/issues/488) | feat(usb): USB-C as an Ethernet LAN link (NCM) and AT console | module اولیه panic؛ patch با ping فقط همان مسیر را سنجید؛ کار باز برای بسته و DHCP. |
| [#492](https://github.com/mralinp/zlt-x28-openwrt/issues/492) | feat(luci): show real 5G (EN-DC) state and NR signal in the Carrier tab | طبقه‌بندی NR فعال در برابر neighbour/قابلیت؛ نیاز به MIPC نه حدس AT. |
| [#499](https://github.com/mralinp/zlt-x28-openwrt/issues/499) | fix(feed): bump the releases of x28-mipc, luci-proto-x28-mipc and x28-nrband | فایل تغییرکرده باید revision جدید داشته باشد. |
| [#501](https://github.com/mralinp/zlt-x28-openwrt/issues/501) | docs(modules): the Ethernet sockets, the 2.5 G port and the switch ports | شماره switch با سوکت فیزیکی برابر فرض نشود. |
| [#503](https://github.com/mralinp/zlt-x28-openwrt/issues/503) | fix(feed): pin x28-nrband 0.1.0-2 so images carry the 5G signal command | یکسانی نسخه ابزار و image، نه صرف حضور asset تازه. |
| [#509](https://github.com/mralinp/zlt-x28-openwrt/issues/509) | feat(sysupgrade): always write the slot that is not running, then boot it | قاعده target غیرجاری، تغییر در رفتار نسخه مبدأ است. |
| [#511](https://github.com/mralinp/zlt-x28-openwrt/issues/511) | LuCI notice when a newer signed native image is released | کشف release و اعلان با نوشتن flash یکی نیست. |
| [#513](https://github.com/mralinp/zlt-x28-openwrt/issues/513) | Wi-Fi down on the X28 PRO with the general image: x28-wifi-l1 never restores the two-card profile | profile عمومی از X28؛ PRO به تبدیل عکس مسیر تک‌کارت نیاز داشت. |
| [#515](https://github.com/mralinp/zlt-x28-openwrt/issues/515) | x28-upgrade: one-command upgrade to the newest signed image (CLI + LuCI button) | تأیید کاربر، RAM، lock، checksum و sysupgrade؛ host test، نه OTA بی‌حضور. |

</div>

<h2 dir="rtl" align="right">گفت‌وگوهایی که نتیجه را نسبت به متن آغاز تغییر می‌دهند</h2>

- [گفت‌وگوی #40](https://github.com/mralinp/zlt-x28-openwrt/issues/40): 1 نظر در پاسخ قابل دسترسی بررسی شد؛ تاریخ، پیش‌نیاز، نتیجه و not-proven از هدف اولیه جدا خوانده شوند.
- [گفت‌وگوی #227](https://github.com/mralinp/zlt-x28-openwrt/issues/227): 3 نظر در پاسخ قابل دسترسی بررسی شد؛ تاریخ، پیش‌نیاز، نتیجه و not-proven از هدف اولیه جدا خوانده شوند.
- [گفت‌وگوی #376](https://github.com/mralinp/zlt-x28-openwrt/issues/376): 1 نظر در پاسخ قابل دسترسی بررسی شد؛ تاریخ، پیش‌نیاز، نتیجه و not-proven از هدف اولیه جدا خوانده شوند.
- [گفت‌وگوی #476](https://github.com/mralinp/zlt-x28-openwrt/issues/476): 3 نظر در پاسخ قابل دسترسی بررسی شد؛ تاریخ، پیش‌نیاز، نتیجه و not-proven از هدف اولیه جدا خوانده شوند.
- [گفت‌وگوی #458](https://github.com/mralinp/zlt-x28-openwrt/issues/458): 8 نظر در پاسخ قابل دسترسی بررسی شد؛ تاریخ، پیش‌نیاز، نتیجه و not-proven از هدف اولیه جدا خوانده شوند.

<h2 dir="rtl" align="right">وضعیت issueهای محوری؛ شاخص مدیریت کار، نه درجه اثبات</h2>

<div dir="rtl" align="center">

| issue | وضعیت مشاهده‌شده در API | برداشت مجاز |
| ---: | ---: | ---: |
| [#215](https://github.com/mralinp/zlt-x28-openwrt/issues/215) | بسته | مسیر DTB داخل boot به Linux و DTB مستقل LK؛ دو مصرف‌کننده. |
| [#227](https://github.com/mralinp/zlt-x28-openwrt/issues/227) | بسته | نظرهای آفلاین ABI و سپس تست واقعی تونل، دو سطح شاهد مستقل. |
| [#376](https://github.com/mralinp/zlt-x28-openwrt/issues/376) | بسته | marker اولیه reboot سالم را هم مانع load می‌کرد؛ اصلاح و TESTING ۴۶/۴۸. |
| [#476](https://github.com/mralinp/zlt-x28-openwrt/issues/476) | باز | نظرهای identity/variants، روش standard signature و تست ۵۳d؛ issue باز چند خروجی متفاوت دارد. |
| [#509](https://github.com/mralinp/zlt-x28-openwrt/issues/509) | بسته | قاعده target غیرجاری، تغییر در رفتار نسخه مبدأ است. |
| [#513](https://github.com/mralinp/zlt-x28-openwrt/issues/513) | بسته | profile عمومی از X28؛ PRO به تبدیل عکس مسیر تک‌کارت نیاز داشت. |
| [#515](https://github.com/mralinp/zlt-x28-openwrt/issues/515) | بسته | تأیید کاربر، RAM، lock، checksum و sysupgrade؛ host test، نه OTA بی‌حضور. |
| [#477](https://github.com/mralinp/zlt-x28-openwrt/issues/477) | باز | حفظ config و package list هنوز مسئله باز؛ -n با -k برابر نیست. |
| [#478](https://github.com/mralinp/zlt-x28-openwrt/issues/478) | باز | مسیر عمومی flash page هنوز نیازمند تست مستقل است. |
| [#458](https://github.com/mralinp/zlt-x28-openwrt/issues/458) | باز | گفت‌وگو ترتیب آزمایش identical، تغییر، native B و محدودیت power-loss را روشن می‌کند. |
| [#488](https://github.com/mralinp/zlt-x28-openwrt/issues/488) | باز | module اولیه panic؛ patch با ping فقط همان مسیر را سنجید؛ کار باز برای بسته و DHCP. |

</div>

<h2 dir="rtl" align="right">مواردی که باید در بازنویسی اصلاح شوند</h2>

- #3 در شروع درباره نقش LK سؤال دارد؛ متن آموزشی باید نقش انتخاب slot در Preloader را مطابق پژوهش بعدی روشن کند.
- #40 در شروع امضای rootfs را مانع فرض کرده بود؛ comment نهایی و پژوهش signed-content/content-enforcement مرز metadata و payload را روشن می‌کنند. تجربه بوت RootFS جدید با LK اصلی از preview محلی LK جداست.
- #181 در طرح اولیه تعداد متفاوتی برای پارتیشن‌ها گفته؛ شمارش معتبر ثبت backup و TESTING ملاک است، نه عدد متن قدیمی issue.
- #227 ابتدا بدون ترافیک بود؛ comment بعدی handshake/traffic را ثبت کرده و محدودیت ABI بلندمدت همچنان باقی است.
- #376 و #513 صرفاً «ویژگی اضافه شد» نیستند؛ failure، علت، patch و آزمون regression بخش اصلی داستان‌اند.
- #476 باز مانده، اما بخشی از مسیر امضا روی دستگاه انجام شده؛ وضعیت کلی issue نباید آن نتیجه را پاک کند یا همه زیرکارها را تمام‌شده نشان بدهد.
- #509 رفتار هدف را برای نسخه جدید عوض می‌کند؛ تست upgrade نسخه قدیمی اثبات سیاست جدید در همه مبدأها نیست.
- #515 بسته است و helper host test دارد؛ نبود تست LuCI روی واحد یا upgrade بی‌حضور کاربر با این وضعیت جبران نمی‌شود.

<h2 dir="rtl" align="right">ترتیب تطبیق نتیجه برای نویسنده</h2>

۱. مسئله/فرض اولیه در issue → ۲. comment آزمایش و اصلاح → ۳. تغییر source و نسخه آن → ۴. TESTING و شرایط اجرای واقعی → ۵. statement محدود برای مقاله. اگر source و یادداشت قدیمی ناسازگارن، ادعا با تاریخ مشخص و شاهد آخر بیان شود. گزارش جدید صاحب دستگاه نیز با عنوان «تأیید نویسنده» از خروجی ابزار جدا بماند.

منابع source و تست اصلی:

- [زنجیره بوت و Device Tree](../../docs/BOOT-FLOW.md)
- [امضای metadata و محتوای فایل‌سیستم](../../docs/research/rootfs-signed-content.md)
- [مصرف‌کننده بررسی محتوای rootfs](../../docs/research/content-enforcement.md)
- [رفتار Preloader و slot B](../../docs/research/slot-b-reuse.md)
- [ABI باینری‌های vendor](../../docs/FIRMWARE-INVENTORY.md)
- [CRC و ماژول‌ها](../../docs/research/kernel-module-crc.md)
- [آزمون‌ها](../../docs/TESTING.md)
- [انتخاب target و عملیات upgrade](../../package/x28-sysupgrade/files/lib/upgrade/platform.sh)
- [helper ارتقای نسخه](../../package/x28-update/files/x28-upgrade)
- [releaseهای قابل مشاهده](https://github.com/mralinp/zlt-x28-openwrt/releases)

هیچ command روی مودم، build یا workflow تازه، تغییر issue، commit یا push در تهیه این دفتر انجام نشده. تفسیر hardware هنوز به شواهد موجود محدود است.

</div>

