import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT_DIR = path.resolve(__dirname, '..');
const SITE_DIR = path.resolve(ROOT_DIR, 'site');

const MIME_TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.webp': 'image/webp',
  '.gif': 'image/gif',
  '.ico': 'image/x-icon',
  '.woff2': 'font/woff2',
  '.ttf': 'font/ttf',
  '.md': 'text/markdown; charset=utf-8',
};

const LIVE_RELOAD_SCRIPT = `
<script>
(() => {
  let es;
  function connect() {
    es = new EventSource('/__live_reload');
    es.onmessage = (e) => {
      if (e.data === 'reload') {
        console.log('[LiveReload] Change detected, reloading...');
        location.reload();
      }
    };
    es.onerror = () => {
      es.close();
      setTimeout(connect, 1000);
    };
  }
  connect();
})();
</script>
`;

// Connected SSE clients
const sseClients = new Set();

function broadcastReload() {
  for (const res of sseClients) {
    try {
      res.write('data: reload\n\n');
    } catch {
      sseClients.delete(res);
    }
  }
}

// Watch site/ for changes
if (fs.existsSync(SITE_DIR)) {
  let debounceTimer = null;
  fs.watch(SITE_DIR, { recursive: true }, (eventType, filename) => {
    if (filename && (filename.startsWith('.') || filename.endsWith('~'))) return;
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      console.log(`[Watch] File changed: ${filename}`);
      broadcastReload();
    }, 100);
  });
}

function resolveFilePath(reqPath) {
  let cleanPath = decodeURIComponent(reqPath.split('?')[0]);
  if (cleanPath === '/' || cleanPath === '') {
    cleanPath = '/index.html';
  }

  // If path starts with /docs/, serve from ROOT_DIR/docs/
  if (cleanPath.startsWith('/docs/')) {
    const candidate = path.join(ROOT_DIR, cleanPath);
    if (candidate.startsWith(ROOT_DIR) && fs.existsSync(candidate) && fs.statSync(candidate).isFile()) {
      return candidate;
    }
  }

  // Otherwise serve from SITE_DIR
  const siteCandidate = path.join(SITE_DIR, cleanPath);
  if (siteCandidate.startsWith(SITE_DIR) && fs.existsSync(siteCandidate)) {
    if (fs.statSync(siteCandidate).isDirectory()) {
      const indexFile = path.join(siteCandidate, 'index.html');
      if (fs.existsSync(indexFile)) return indexFile;
    } else {
      return siteCandidate;
    }
  }

  // Fallback check in ROOT_DIR
  const rootCandidate = path.join(ROOT_DIR, cleanPath);
  if (rootCandidate.startsWith(ROOT_DIR) && fs.existsSync(rootCandidate) && fs.statSync(rootCandidate).isFile()) {
    return rootCandidate;
  }

  return null;
}

const server = http.createServer((req, res) => {
  if (req.url === '/__live_reload') {
    res.writeHead(200, {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
      'Access-Control-Allow-Origin': '*',
    });
    res.write('data: connected\n\n');
    sseClients.add(res);
    req.on('close', () => sseClients.delete(res));
    return;
  }

  const filePath = resolveFilePath(req.url);

  if (!filePath) {
    res.writeHead(404, { 'Content-Type': 'text/plain' });
    res.end('404 Not Found');
    return;
  }

  try {
    const ext = path.extname(filePath).toLowerCase();
    const contentType = MIME_TYPES[ext] || 'application/octet-stream';

    if (ext === '.html') {
      let content = fs.readFileSync(filePath, 'utf-8');
      if (content.includes('</body>')) {
        content = content.replace('</body>', `${LIVE_RELOAD_SCRIPT}</body>`);
      } else {
        content += LIVE_RELOAD_SCRIPT;
      }
      res.writeHead(200, {
        'Content-Type': contentType,
        'Cache-Control': 'no-store, must-revalidate',
      });
      res.end(content);
    } else {
      const stat = fs.statSync(filePath);
      res.writeHead(200, {
        'Content-Type': contentType,
        'Content-Length': stat.size,
        'Cache-Control': 'public, max-age=3600',
      });
      fs.createReadStream(filePath).pipe(res);
    }
  } catch (err) {
    res.writeHead(500, { 'Content-Type': 'text/plain' });
    res.end(`500 Server Error: ${err.message}`);
  }
});

function startServer(port = 3000, attempts = 5) {
  server.listen(port, '127.0.0.1', () => {
    console.log(`\n🚀 X28 OpenWrt Dev Server running at: http://localhost:${port}/`);
    console.log(`   Watching: ${SITE_DIR}`);
    console.log(`   Press Ctrl+C to stop.\n`);
  });

  server.on('error', (err) => {
    if (err.code === 'EADDRINUSE' && attempts > 0) {
      console.log(`Port ${port} in use, trying ${port + 1}...`);
      startServer(port + 1, attempts - 1);
    } else {
      console.error('Failed to start dev server:', err);
      process.exit(1);
    }
  });
}

startServer(Number(process.env.PORT) || 3000);
