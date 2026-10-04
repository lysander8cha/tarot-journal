module.exports = {
  packagerConfig: {
    name: 'Tarot Journal',
    executableName: 'tarot-journal',
    icon: './electron/icon',
    ignore: [
      /^\/\.git/,
      /^\/\.venv/,
      /^\/\.claude/,
      /^\/\.vscode/,
      /^\/frontend\/node_modules/,
      /^\/frontend\/src/,
      /^\/node_modules\/(?!electron)/,
      /^\/\.thumbnail_cache/,
      /\.pyc$/,
      /^\/ios/,
      /^\/tests/,
      /^\/out/,
      /\.log(\.\d+)?$/,
    ],
    asar: false,
  },
  makers: [
    {
      name: '@electron-forge/maker-zip',
      platforms: ['darwin', 'linux', 'win32'],
    },
    {
      name: '@electron-forge/maker-dmg',
      config: {
        format: 'ULFO',
      },
    },
  ],
};
