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

  flaskProcess = spawn(pythonCmd, [runScript], {
    cwd: PROJECT_ROOT,
    env: {
      ...process.env,
      FLASK_PORT: String(FLASK_PORT),
      PYTHONDONTWRITEBYTECODE: '1',
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
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 800,
    minHeight: 600,
    title: 'Tarot Journal',
    backgroundColor: '#1e2024',
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

  // Allow toggling DevTools with Cmd+Option+I (Mac) or Ctrl+Shift+I (Windows/Linux)
  mainWindow.webContents.on('before-input-event', (event, input) => {
    if ((input.meta || input.control) && input.alt && input.key.toLowerCase() === 'i') {
      mainWindow.webContents.toggleDevTools();
    }
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// IPC handlers for file dialogs
ipcMain.handle('dialog:openFile', async (_event, options) => {
  if (!mainWindow) return null;
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openFile'],
    filters: options?.filters || [],
    title: options?.title || 'Open File',
  });
  return result.canceled ? null : result.filePaths[0];
});

ipcMain.handle('dialog:openDirectory', async (_event, options) => {
  if (!mainWindow) return null;
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openDirectory'],
    title: options?.title || 'Select Folder',
  });
  return result.canceled ? null : result.filePaths[0];
});

ipcMain.handle('dialog:saveFile', async (_event, options) => {
  if (!mainWindow) return null;
  const result = await dialog.showSaveDialog(mainWindow, {
    filters: options?.filters || [],
    title: options?.title || 'Save File',
    defaultPath: options?.defaultPath,
  });
  return result.canceled ? null : result.filePath;
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

app.on('window-all-closed', () => {
  stopFlask();
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
