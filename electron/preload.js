const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  openDirectory: (options) => ipcRenderer.invoke('dialog:openDirectory', options),
  isElectron: true,
});
