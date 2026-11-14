/* X28 OpenWrt landing page. No build step. */

document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  initCopyButton();
  initTerminal();
  initMobileMenu();
  loadStats();
});

/* --------------------------------------------------------------------------
   Theme (dark / light)
   -------------------------------------------------------------------------- */
function initTheme() {
  const html = document.documentElement;
  const brandLogo = document.getElementById('brandLogo');
  let saved = null;
  try { saved = localStorage.getItem('x28-theme'); } catch (e) { /* storage blocked */ }
  setTheme(saved || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'));

  document.getElementById('themeToggle')?.addEventListener('click', () => {
    const next = html.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    setTheme(next);
    try { localStorage.setItem('x28-theme', next); } catch (e) { /* storage blocked */ }
  });

  function setTheme(theme) {
    html.setAttribute('data-theme', theme);
    if (brandLogo) brandLogo.src = theme === 'dark' ? 'logo-dark-horizontal.svg' : 'logo-horizontal.svg';
  }
}

/* --------------------------------------------------------------------------
   Copy the curl example
   -------------------------------------------------------------------------- */
function initCopyButton() {
  const btn = document.getElementById('copyApiCode');
  if (!btn) return;
  btn.addEventListener('click', () => {
    const code = `curl -k -H "Authorization: Bearer $KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"to":"+989121234567","text":"Hello"}' \\
  https://192.168.70.1/cgi-bin/x28-telephony/messages`;
    navigator.clipboard.writeText(code).then(() => {
      btn.textContent = 'Copied';
      setTimeout(() => { btn.textContent = 'Copy send command'; }, 2000);
    });
  });
}

/* --------------------------------------------------------------------------
   Shell preview. Output is what the tools print today: the usage line for an
   argument they do not know (docs/TELEPHONY.md for the poll result).
   -------------------------------------------------------------------------- */
function initTerminal() {
  const termBody = document.getElementById('termBody');
  const termInput = document.getElementById('termInput');
  if (!termBody) return;

  const OUTPUT = {
    'x28-upgrade --help': 'usage: x28-upgrade [--refresh | -y [-b]]',
    'x28-update-check --help': 'usage: x28-update-check [--refresh]',
    'x28-sms --help': 'usage: x28-sms list|poll|send N TEXT|delete ID...|contacts|contact-set N NAME|contact-del N|keys|key-add LABEL|key-del ID|webhook [URL]|cgi|selftest',
    'x28-sms poll': '{"new":0}',
    'opkg update': `Downloading https://github.com/mralinp/zlt-x28-openwrt/releases/download/feed-3/Packages.gz
Updated list of available packages in /var/opkg-lists/x28
Downloading https://github.com/mralinp/zlt-x28-openwrt/releases/download/feed-3/Packages.sig
Signature check passed.`
  };

  document.querySelectorAll('.cmd-pill').forEach(btn => {
    btn.addEventListener('click', () => run(btn.dataset.cmd));
  });

  function run(cmd) {
    if (termInput) termInput.textContent = cmd;
    setTimeout(() => {
      const execLine = document.createElement('div');
      execLine.className = 'term-line';
      execLine.innerHTML = `<span class="term-prompt">root@X28:~#</span> ${escapeHtml(cmd)}`;

      const outLine = document.createElement('div');
      outLine.className = 'term-line';
      outLine.style.color = '#e2e8f0';
      outLine.textContent = OUTPUT[cmd] || `-ash: ${cmd}: not part of this demo`;

      const promptLine = termBody.querySelector('.prompt-line');
      termBody.insertBefore(execLine, promptLine);
      termBody.insertBefore(outLine, promptLine);
      if (termInput) termInput.textContent = '';
      termBody.scrollTop = termBody.scrollHeight;
    }, 200);
  }
}

function escapeHtml(str) {
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

/* --------------------------------------------------------------------------
   Mobile menu
   -------------------------------------------------------------------------- */
function initMobileMenu() {
  const btn = document.getElementById('mobileMenuBtn');
  const navLinks = document.getElementById('navLinks');
  if (!btn || !navLinks) return;

  btn.addEventListener('click', () => {
    if (navLinks.style.display === 'flex') {
      navLinks.removeAttribute('style');
      return;
    }
    Object.assign(navLinks.style, {
      display: 'flex', position: 'absolute', top: '72px', left: '0', width: '100%',
      flexDirection: 'column', background: 'var(--bg-card-solid)', padding: '24px',
      borderBottom: '1px solid var(--border-color)'
    });
  });
  // close the open menu after a jump; removing the inline style hands control back to the CSS
  navLinks.addEventListener('click', (e) => {
    if (e.target.closest('a') && navLinks.style.position === 'absolute') navLinks.removeAttribute('style');
  });
}

/* --------------------------------------------------------------------------
   Live release data: stats.json is written by site/build_site.py on deploy
   -------------------------------------------------------------------------- */
const FALLBACK_TAG = 'v1.1.1'; // the version written in index.html, replaced by the live one

function loadStats() {
  const $ = s => document.querySelector(s);
  const n = x => x.toLocaleString('en');
  const mb = b => b > 1e6 ? (b / 1e6).toFixed(1) + ' MB' : Math.max(1, Math.round(b / 1e3)) + ' kB';
  const esc = escapeHtml;
  const rows = (el, rel) => {
    $(el).innerHTML = rel.assets.filter(a => !/^(SHA256SUMS.*|.*\.sig|.*\.sha256)$/.test(a.name))
      .map(a => `<tr><td><a href="${esc(a.url)}">${esc(a.name)}</a></td><td>${mb(a.size)}</td><td>${n(a.downloads)} ↓</td></tr>`).join('');
  };
  const sum = o => Object.values(o).reduce((a, b) => a + b, 0);

  fetch('stats.json')
    .then(res => { if (!res.ok) throw new Error(res.status); return res.json(); })
    .then(s => {
      const set = (k, v) => { $(`[data-k=${k}]`).textContent = v; };
      set('stars', n(sum(s.stars)));
      set('downloads', n(sum(s.downloads)));
      set('feed', n(s.feed.packages));
      set('tests', `${s.tests.passed}/${s.tests.total}`);
      $('#flTag').textContent = s.flasher.tag;
      $('#fwTag').textContent = s.firmware.tag;
      rows('#flAssets', s.flasher);
      rows('#fwAssets', s.firmware);
      $('#built').textContent = ' · Data: ' + s.built;
      stampVersion(s.firmware.tag);
      initOsPicker(s.flasher);
    })
    .catch(() => {
      $('#liveStats').hidden = true;
      $('#dlGrid').hidden = true;
      $('#dlSub').innerHTML = 'Live data is unavailable here. Get the <a href="https://github.com/mralinp/x28-flasher/releases">flasher</a> and the <a href="https://github.com/mralinp/zlt-x28-openwrt/releases">firmware</a> from GitHub releases.';
    });
}

// index.html names a version in several places; keep them all on the newest release
function stampVersion(tag) {
  if (!/^v\d+\.\d+\.\d+$/.test(tag) || tag === FALLBACK_TAG) return;
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let node; (node = walker.nextNode());) {
    if (node.nodeValue.includes(FALLBACK_TAG)) node.nodeValue = node.nodeValue.split(FALLBACK_TAG).join(tag);
  }
  document.querySelectorAll(`a[href$="/releases/tag/${FALLBACK_TAG}"]`).forEach(a => { a.href = a.href.replace(FALLBACK_TAG, tag); });
}

/* --------------------------------------------------------------------------
   Flasher download for the visitor's operating system (step 1 of the guide).
   Asset names come from the flasher's release, e.g. X28-Flasher-windows-x64-setup.exe
   -------------------------------------------------------------------------- */
function initOsPicker(flasher) {
  const box = document.getElementById('osPick');
  if (!box) return;
  const mb = b => (b / 1e6).toFixed(1) + ' MB';
  const find = re => flasher.assets.find(a => re.test(a.name));
  const dl = (a, label, primary) => a
    ? `<a class="btn ${primary ? 'btn-primary' : 'btn-secondary'} btn-sm" href="${escapeHtml(a.url)}">${label} <small>${escapeHtml(a.name)} · ${mb(a.size)}</small></a>`
    : '';

  const OS = {
    windows: {
      label: 'Windows',
      files: () => [dl(find(/windows.*\.exe$/i), 'Download the installer (x64)', true)],
      notes: ['Run the installer. Missing USB drivers are bundled with it.', 'Windows 64-bit only.']
    },
    macos: {
      label: 'macOS',
      files: () => [dl(find(/\.dmg$/i), 'Download the disk image (Apple silicon)', true)],
      notes: ['Apple silicon Macs only; there is no Intel build.',
        'The app is not Apple-notarized. If macOS blocks it, open System Settings → Privacy & Security and choose <strong>Open Anyway</strong>, for this official download only.',
        'Compare the disk image with <code>SHA256SUMS-macos-arm64.txt</code> on the release page.']
    },
    linux: {
      label: 'Linux',
      files: () => [
        dl(find(/linux.*\.deb$/i), 'Download the .deb (Debian, Ubuntu)', true),
        dl(find(/archlinux.*\.zst$/i), 'Download the Arch Linux package', false),
        dl(find(/linux.*\.tar\.gz$/i), 'Download the .tar.gz', false)
      ],
      notes: ['x86_64 only.',
        'Debian or Ubuntu: <code>sudo apt install ./&lt;the .deb file&gt;</code>. Arch Linux: <code>sudo pacman -U &lt;the .pkg.tar.zst file&gt;</code>. Then start <code>x28-flasher</code>.',
        'If the device is not found, check that your user may access the USB device.']
    }
  };

  const plat = ((navigator.userAgentData && navigator.userAgentData.platform) || navigator.platform || navigator.userAgent || '').toLowerCase();
  const detected = /mac|iphone|ipad/.test(plat) ? 'macos' : /linux|x11|cros/.test(plat) && !/android/.test(plat) ? 'linux' : 'windows';

  box.innerHTML = `
    <p class="os-lead">X28 Flasher <b>${escapeHtml(flasher.tag)}</b>. Choose your system:</p>
    <div class="os-tabs">${Object.entries(OS).map(([k, o]) => `<button type="button" data-os="${k}">${o.label}</button>`).join('')}</div>
    <div class="os-panel" id="osPanel"></div>
    <p class="os-foot">All files and checksums: <a href="${escapeHtml(flasher.url)}" target="_blank" rel="noopener">${escapeHtml(flasher.tag)} on GitHub</a>.</p>`;

  const show = key => {
    box.querySelectorAll('.os-tabs button').forEach(b => b.classList.toggle('active', b.dataset.os === key));
    box.querySelector('#osPanel').innerHTML =
      `<div class="os-buttons">${OS[key].files().join('')}</div><ul>${OS[key].notes.map(t => `<li>${t}</li>`).join('')}</ul>`;
  };
  box.querySelectorAll('.os-tabs button').forEach(b => b.addEventListener('click', () => show(b.dataset.os)));
  show(detected);
}
