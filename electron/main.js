const { app, BrowserWindow, dialog, ipcMain } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const http = require('http');

const PROJECT_ROOT = path.dirname(__dirname);
const FLASK_PORT = parseInt(process.env.FLASK_PORT || '5678', 10);
const IS_DEV = process.env.NODE_ENV === 'development';
const VITE_PORT = 5173;

let flaskProcess = null;
let mainWindow = null;

function startFlask() {
  const runScript = path.join(PROJECT_ROOT, 'backend', 'run.py');
  // Use the venv's Python if it exists, otherwise fall back to system Python
  const venvPython = path.join(PROJECT_ROOT, '.venv', 'bin', 'python3');
  const pythonCmd = require('fs').existsSync(venvPython) ? venvPython : 'python3';

  // WeasyPrint (used by the PDF export) is a CFFI wrapper around
  // pango/cairo/glib. macOS's dyld doesn't include Homebrew's lib
  // dir by default, so prepend it (alongside the user's own value)
  // so libgobject-2.0 etc. resolve at import time.
  const dyldExtra = '/opt/homebrew/lib:/usr/local/lib';
  const dyldExisting = process.env.DYLD_FALLBACK_LIBRARY_PATH || '';
  const dyldFallback = dyldExisting
    ? `${dyldExtra}:${dyldExisting}`
    : dyldExtra;

  flaskProcess = spawn(pythonCmd, [runScript], {
    cwd: PROJECT_ROOT,
    env: {
      ...process.env,
      FLASK_PORT: String(FLASK_PORT),
      PYTHONDONTWRITEBYTECODE: '1',
      DYLD_FALLBACK_LIBRARY_PATH: dyldFallback,
    },
    stdio: ['pipe', 'pipe', 'pipe'],
  });

  flaskProcess.stdout.on('data', (data) => {
    console.log(`[Flask] ${data.toString().trim()}`);
  });

  flaskProcess.stderr.on('data', (data) => {
    console.error(`[Flask] ${data.toString().trim()}`);
  });

  flaskProcess.on('close', (code) => {
    console.log(`[Flask] Process exited with code ${code}`);
    flaskProcess = null;
  });
}

function waitForFlask(retries = 30, interval = 500) {
  return new Promise((resolve, reject) => {
    let attempt = 0;

    function check() {
      attempt++;
      const req = http.get(`http://127.0.0.1:${FLASK_PORT}/api/health`, (res) => {
        if (res.statusCode === 200) {
          resolve();
        } else if (attempt < retries) {
          setTimeout(check, interval);
        } else {
          reject(new Error('Flask health check failed'));
        }
      });

      req.on('error', () => {
        if (attempt < retries) {
          setTimeout(check, interval);
        } else {
          reject(new Error('Flask did not start'));
        }
      });

      req.end();
    }

    check();
  });
}

function stopFlask() {
  if (flaskProcess) {
    flaskProcess.kill('SIGTERM');
    // Give it a moment, then force kill if needed
    setTimeout(() => {
      if (flaskProcess) {
        flaskProcess.kill('SIGKILL');
      }
    }, 3000);
  }
}

function createWindow() {
  // The Nocturne design is drawn at 1440×940 with no narrow layout;
  // the floor stays a bit below that for small displays, accepting
  // some squeeze rather than blocking them entirely.
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 940,
    minWidth: 1100,
    minHeight: 720,
    title: 'Tarot Journal',
    backgroundColor: '#161826',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  // In development, load Vite dev server; in production, load Flask
  const url = IS_DEV
    ? `http://localhost:${VITE_PORT}`
    : `http://localhost:${FLASK_PORT}`;

  mainWindow.loadURL(url);

  if (IS_DEV) {
    mainWindow.webContents.openDevTools();
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// IPC handler for the folder picker (the default app menu already
// provides View → Toggle Developer Tools)
ipcMain.handle('dialog:openDirectory', async (_event, options) => {
  if (!mainWindow) return null;
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openDirectory'],
    title: options?.title || 'Select Folder',
  });
  return result.canceled ? null : result.filePaths[0];
});

// App lifecycle
app.whenReady().then(async () => {
  startFlask();

  try {
    await waitForFlask();
    console.log('[Electron] Flask is ready');
  } catch (err) {
    console.error('[Electron] Failed to start Flask:', err.message);
    dialog.showErrorBox('Startup Error', 'Failed to start the backend server. Make sure Python 3 is installed.');
    app.quit();
    return;
  }

  createWindow();
});

// app.quit() always emits before-quit, which stops Flask.
app.on('window-all-closed', () => {
  app.quit();
});

app.on('before-quit', () => {
  stopFlask();
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});
