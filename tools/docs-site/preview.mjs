import { fileURLToPath } from 'node:url';
import { preview } from 'vite';

// VitePress 1's preview ignores --host/--open and has no port fallback.
// Use the same Vite version with an explicit local-only preview configuration.
const server = await preview({
  configFile: false,
  root: fileURLToPath(new URL('.', import.meta.url)),
  build: { outDir: '.vitepress/dist' },
  preview: { host: '127.0.0.1', port: 5173, open: true },
});
server.printUrls();
