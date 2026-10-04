// Bridge exposed by electron/preload.js (absent in a plain browser).
interface Window {
  electronAPI?: {
    openDirectory: (options?: { title?: string }) => Promise<string | null>;
    isElectron: boolean;
  };
}
