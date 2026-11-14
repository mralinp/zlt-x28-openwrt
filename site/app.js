/**
 * X28 OpenWrt Showcase Web App
 */

document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  initTelephony();
  initCellularSimulator();
  initTerminal();
  initMobileMenu();
  loadStats();
});

/* --------------------------------------------------------------------------
   1. Theme Management (Dark / Light)
   -------------------------------------------------------------------------- */
function initTheme() {
  const toggleBtn = document.getElementById('themeToggle');
  const html = document.documentElement;
  const brandLogo = document.getElementById('brandLogo');

  const savedTheme = localStorage.getItem('x28-theme');
  const systemPrefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  const initialTheme = savedTheme || (systemPrefersDark ? 'dark' : 'light');

  setTheme(initialTheme);

  if (toggleBtn) {
    toggleBtn.addEventListener('click', () => {
      const current = html.getAttribute('data-theme') || 'dark';
      const next = current === 'dark' ? 'light' : 'dark';
      setTheme(next);
      localStorage.setItem('x28-theme', next);
    });
  }

  function setTheme(theme) {
    html.setAttribute('data-theme', theme);
    if (brandLogo) brandLogo.src = theme === 'dark' ? 'logo-dark-horizontal.svg' : 'logo-horizontal.svg';
  }
}

/* --------------------------------------------------------------------------
   2. Telephony & SMS Suite Interactivity (v1.1)
   -------------------------------------------------------------------------- */
function initTelephony() {
  const tabs = document.querySelectorAll('.luci-tab');
  const panes = document.querySelectorAll('.telephony-tab-pane');
  const convoItems = document.querySelectorAll('.convo-item');
  const activeName = document.getElementById('activeContactName');
  const activeNum = document.getElementById('activeContactNum');
  const composerTarget = document.getElementById('composerToTarget');
  const threadStream = document.getElementById('threadStream');
  const composerText = document.getElementById('composerText');
  const btnSend = document.getElementById('btnComposerSend');
  const charCounter = document.getElementById('charCounter');
  const copyBtn = document.getElementById('copyApiCode');
  const searchInput = document.getElementById('searchConvoInput');

  const CONVERSATIONS = {
    '+989121234567': {
      name: 'Hamrah-e Aval',
      num: '+98 912 123 4567',
      badge: 'Verified Operator',
      messages: [
        { text: 'بسته اینترنت ۵G شما با موفقیت تمدید شد. حجم باقی‌مانده: ۴۵ گیگابایت برای دوره ۳۰ روزه.', dir: 'in', meta: '10:14 AM · 2 parts (UCS-2 Unicode)', tick: '✓ Received' },
        { text: 'Status requested via local API', dir: 'out', meta: '10:15 AM · 1 part (GSM-7)', tick: '✓ Sent' }
      ]
    },
    '+989350000000': {
      name: 'Irancell 5G',
      num: '+98 935 000 0000',
      badge: 'Verified Operator',
      messages: [
        { text: 'کد تایید ورود شما: ۸۴۹۲۰۱. این کد را هرگز در اختیار شخص دیگری قرار ندهید.', dir: 'in', meta: 'Yesterday 3:42 PM · 1 part (UCS-2)', tick: '✓ Received' },
        { text: 'Router verified login token', dir: 'out', meta: 'Yesterday 3:43 PM · 1 part (GSM-7)', tick: '✓ Sent' }
      ]
    },
    '+989120000000': {
      name: 'Home Assistant',
      num: '+98 912 000 0000',
      badge: 'Local Home Lab',
      messages: [
        { text: 'WAN failover triggered. Operating on 5G SA Band n78.', dir: 'in', meta: 'Nov 12 11:30 PM · 1 part (GSM-7)', tick: '✓ Received' },
        { text: 'Failover acknowledged. Keep-alive active.', dir: 'out', meta: 'Nov 12 11:31 PM · 1 part (GSM-7)', tick: '✓ Sent' }
      ]
    }
  };

  // Tab Switching (Messages, Phone Book, API)
  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.forEach(t => t.classList.remove('active'));
      panes.forEach(p => p.classList.remove('active'));

      tab.classList.add('active');
      const targetPane = document.getElementById(`pane-${tab.dataset.tab}`);
      if (targetPane) targetPane.classList.add('active');
    });
  });

  // Conversation Selection
  convoItems.forEach(item => {
    item.addEventListener('click', () => {
      convoItems.forEach(c => c.classList.remove('active'));
      item.classList.add('active');
      const num = item.dataset.number;
      loadConversation(num);
    });
  });

  function loadConversation(num) {
    const data = CONVERSATIONS[num];
    if (!data || !threadStream) return;

    if (activeName) activeName.textContent = data.name;
    if (activeNum) activeNum.textContent = data.num;
    if (composerTarget) composerTarget.textContent = `${data.num} (${data.name})`;

    // Rebuild thread messages
    threadStream.innerHTML = `
      <div class="system-event-pill">
        <span>Copied to /etc/x28-telephony/messages, then deleted from the SIM</span>
      </div>
    `;

    data.messages.forEach(msg => {
      const bubbleWrap = document.createElement('div');
      bubbleWrap.className = `bubble-wrap bubble-${msg.dir}`;
      bubbleWrap.innerHTML = `
        <div class="bubble-content" dir="auto">${escapeHtml(msg.text)}</div>
        <div class="bubble-footer">
          <span>${escapeHtml(msg.meta)}</span>
          <span class="status-tick ${msg.dir === 'out' ? 'tick-done' : ''}">${escapeHtml(msg.tick)}</span>
        </div>
      `;
      threadStream.appendChild(bubbleWrap);
    });

    threadStream.scrollTop = threadStream.scrollHeight;
  }

  // Quick switch from Phonebook Table
  window.switchContact = function(num) {
    const messagesTab = document.querySelector('.luci-tab[data-tab="messages"]');
    if (messagesTab) messagesTab.click();

    const matchingConvo = document.querySelector(`.convo-item[data-number="${num}"]`);
    if (matchingConvo) {
      matchingConvo.click();
    }
  };

  // Compose Textarea & Live Character Counter
  if (composerText && charCounter) {
    composerText.addEventListener('input', () => {
      const val = composerText.value;
      const isUnicode = /[^\u0000-\u007F]/.test(val);
      const limit = isUnicode ? 70 : 160;
      const parts = Math.max(1, Math.ceil(val.length / (isUnicode ? 67 : 153)));
      charCounter.textContent = `${val.length} / ${limit} (${parts} ${parts > 1 ? 'parts' : 'part'})`;
    });

    composerText.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });
  }

  // Send Message
  if (btnSend) {
    btnSend.addEventListener('click', sendMessage);
  }

  function sendMessage() {
    if (!composerText || !threadStream) return;
    const text = composerText.value.trim();
    if (!text) return;

    const isUnicode = /[^\u0000-\u007F]/.test(text);
    const parts = Math.max(1, Math.ceil(text.length / (isUnicode ? 67 : 153)));
    const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    const bubbleWrap = document.createElement('div');
    bubbleWrap.className = 'bubble-wrap bubble-out';
    bubbleWrap.innerHTML = `
      <div class="bubble-content" dir="auto">${escapeHtml(text)}</div>
      <div class="bubble-footer">
        <span>${now}</span>
        <span class="sep">·</span>
        <span>${parts} ${parts > 1 ? 'parts' : 'part'} (${isUnicode ? 'UCS-2' : 'GSM-7'})</span>
        <span class="status-tick tick-done">Demo: not sent</span>
      </div>
    `;
    threadStream.appendChild(bubbleWrap);
    composerText.value = '';
    if (charCounter) charCounter.textContent = '0 / 160 (1 part)';
    threadStream.scrollTop = threadStream.scrollHeight;

  }

  // Search / Filter Conversations
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      const q = e.target.value.toLowerCase();
      convoItems.forEach(item => {
        const text = item.textContent.toLowerCase();
        item.style.display = text.includes(q) ? 'flex' : 'none';
      });
    });
  }

  // Copy API Code
  if (copyBtn) {
    copyBtn.addEventListener('click', () => {
      const code = `curl -k -H "Authorization: Bearer $X28_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"to":"+989121234567","text":"Hello"}' \\
  https://192.168.70.1/cgi-bin/x28-telephony/messages`;

      navigator.clipboard.writeText(code).then(() => {
        copyBtn.textContent = 'Copied!';
        setTimeout(() => copyBtn.textContent = 'Copy cURL', 2000);
      });
    });
  }

  function escapeHtml(str) {
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }
}

/* --------------------------------------------------------------------------
   3. Cellular Band Locking Simulator
   -------------------------------------------------------------------------- */
function initCellularSimulator() {
  const modeButtons = document.querySelectorAll('#modeSelector .btn-toggle');
  const bandChips = document.querySelectorAll('#bandChips .chip');
  const btnApply = document.getElementById('btnApplyBand');
  const btnReset = document.getElementById('btnResetBands');

  const simCarrier = document.getElementById('simCarrier');
  const simModeBadge = document.getElementById('simModeBadge');
  const valRsrp = document.getElementById('valRsrp');
  const valSinr = document.getElementById('valSinr');
  const valSpeed = document.getElementById('valSpeed');
  const barRsrp = document.getElementById('barRsrp');
  const barSinr = document.getElementById('barSinr');
  const barSpeed = document.getElementById('barSpeed');
  const simLog = document.getElementById('simLog');

  let currentMode = 'sa';
  let activeBand = 'n78';

  modeButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      modeButtons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentMode = btn.dataset.mode;
      updateSimulation();
    });
  });

  bandChips.forEach(chip => {
    chip.addEventListener('click', () => {
      bandChips.forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      activeBand = chip.dataset.band;
      updateSimulation();
    });
  });

  if (btnReset) {
    btnReset.addEventListener('click', () => {
      modeButtons.forEach(b => b.classList.remove('active'));
      document.querySelector('#modeSelector [data-mode="sa"]')?.classList.add('active');
      currentMode = 'sa';

      bandChips.forEach(c => c.classList.remove('active'));
      document.querySelector('#bandChips [data-band="n78"]')?.classList.add('active');
      activeBand = 'n78';

      updateSimulation();
      appendLog('> [demo] Band lock removed, automatic selection');
    });
  }

  if (btnApply) {
    btnApply.addEventListener('click', () => {
      const activeChip = document.querySelector('#bandChips .chip.active');
      const b = activeChip ? activeChip.dataset.band : 'n78';
      appendLog(`> [demo] Band lock applied: ${b.toUpperCase()}`);
    });
  }

  function updateSimulation() {
    const activeChip = document.querySelector('#bandChips .chip.active');
    if (!activeChip) return;

    const band = activeChip.dataset.band;
    const freq = activeChip.dataset.freq;
    const bw = activeChip.dataset.bw;
    const baseRsrp = parseInt(activeChip.dataset.rsrp, 10);
    const baseSinr = parseInt(activeChip.dataset.sinr, 10);
    const baseSpeed = parseInt(activeChip.dataset.speed, 10);

    let modeText = '5G SA Attached';
    let speedMult = 1.0;
    if (currentMode === 'nsa') {
      modeText = '5G NSA (EN-DC B3+n78)';
      speedMult = 0.9;
    } else if (currentMode === 'lte') {
      modeText = '4G LTE-A (CA B1+B3+B7)';
      speedMult = 0.35;
    }

    if (simModeBadge) simModeBadge.textContent = modeText;

    const calcRsrp = currentMode === 'lte' ? baseRsrp - 4 : baseRsrp;
    const calcSinr = currentMode === 'lte' ? baseSinr - 5 : baseSinr;
    const calcSpeed = Math.round(baseSpeed * speedMult);

    if (valRsrp) valRsrp.textContent = `${calcRsrp} dBm`;
    if (valSinr) valSinr.textContent = `+${calcSinr} dB`;
    if (valSpeed) valSpeed.textContent = `${calcSpeed} Mbps`;

    if (barRsrp) barRsrp.style.width = `${Math.min(100, Math.max(20, (calcRsrp + 130) * 1.4))}%`;
    if (barSinr) barSinr.style.width = `${Math.min(100, Math.max(20, calcSinr * 3.3))}%`;
    if (barSpeed) barSpeed.style.width = `${Math.min(100, Math.max(15, (calcSpeed / 1000) * 100))}%`;

    appendLog(`> [demo] Switched mode: ${modeText} | Active band: ${band.toUpperCase()} (${freq}, BW: ${bw})`);
  }

  function appendLog(line) {
    if (!simLog) return;
    const time = new Date().toLocaleTimeString();
    simLog.textContent += `\n[${time}] ${line}`;
    simLog.scrollTop = simLog.scrollHeight;
  }
}

/* --------------------------------------------------------------------------
   5. Interactive Terminal Shell Preview (v1.1.1 commands)
   -------------------------------------------------------------------------- */
function initTerminal() {
  const cmdButtons = document.querySelectorAll('.cmd-pill');
  const termBody = document.getElementById('termBody');
  const termInput = document.getElementById('termInput');

  // Output as recorded in docs/TELEPHONY.md, docs/THERMAL.md and docs/PACKAGE-FEED.md
  const COMMAND_OUTPUTS = {
    'x28-sms poll': '{"new":27}',
    'cat /sys/class/thermal/thermal_zone0/temp': '40120',
    'opkg update': `Downloading https://github.com/mralinp/zlt-x28-openwrt/releases/download/feed-3/Packages.gz
Updated list of available packages in /var/opkg-lists/x28
Downloading https://github.com/mralinp/zlt-x28-openwrt/releases/download/feed-3/Packages.sig
Signature check passed.`
  };

  cmdButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      const cmd = btn.dataset.cmd;
      runCommand(cmd);
    });
  });

  function runCommand(cmd) {
    if (!termBody) return;

    if (termInput) termInput.textContent = cmd;

    setTimeout(() => {
      const execLine = document.createElement('div');
      execLine.className = 'term-line';
      execLine.innerHTML = `<span class="term-prompt">root@X28:~#</span> ${escapeHtml(cmd)}`;

      const outLine = document.createElement('div');
      outLine.className = 'term-line';
      outLine.style.color = '#e2e8f0';
      outLine.textContent = COMMAND_OUTPUTS[cmd] || `-ash: ${cmd}: not part of this demo`;

      const promptLine = termBody.querySelector('.prompt-line');
      if (promptLine) {
        termBody.insertBefore(execLine, promptLine);
        termBody.insertBefore(outLine, promptLine);
      } else {
        termBody.appendChild(execLine);
        termBody.appendChild(outLine);
      }

      if (termInput) termInput.textContent = '';
      termBody.scrollTop = termBody.scrollHeight;
    }, 200);
  }

  function escapeHtml(str) {
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }
}

/* --------------------------------------------------------------------------
   7. Mobile Menu
   -------------------------------------------------------------------------- */
function initMobileMenu() {
  const btn = document.getElementById('mobileMenuBtn');
  const navLinks = document.getElementById('navLinks');

  if (btn && navLinks) {
    btn.addEventListener('click', () => {
      const isVisible = navLinks.style.display === 'flex';
      if (isVisible) navLinks.removeAttribute('style');
      else {
        navLinks.style.display = 'flex';
        navLinks.style.position = 'absolute';
        navLinks.style.top = '72px';
        navLinks.style.left = '0';
        navLinks.style.width = '100%';
        navLinks.style.flexDirection = 'column';
        navLinks.style.background = 'var(--bg-card-solid)';
        navLinks.style.padding = '24px';
        navLinks.style.borderBottom = '1px solid var(--border-color)';
      }
    });
    // close the open menu after a jump; removing the inline style hands control back to the CSS
    navLinks.addEventListener('click', (e) => {
      if (e.target.closest('a') && navLinks.style.position === 'absolute') navLinks.removeAttribute('style');
    });
  }
}

/* --------------------------------------------------------------------------
   8. Live release data: stats.json is written by site/build_site.py on deploy
   -------------------------------------------------------------------------- */
const FALLBACK_TAG = 'v1.1.1'; // the version written in index.html, replaced by the live one

function loadStats() {
  const $ = s => document.querySelector(s);
  const n = x => x.toLocaleString('en');
  const mb = b => b > 1e6 ? (b / 1e6).toFixed(1) + ' MB' : Math.max(1, Math.round(b / 1e3)) + ' kB';
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
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
