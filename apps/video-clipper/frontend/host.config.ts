import { defineConfig } from '@rsbuild/core';
import { pluginWebPlatform } from '@lynx-js/web-platform-rsbuild-plugin';

export default defineConfig({
  plugins: [pluginWebPlatform({ polyfill: false })],
  source: { entry: { index: './src/host.ts' } },
  html: { template: './index.html' },
  output: { assetPrefix: '/', polyfill: 'off', cleanDistPath: false, distPath: { root: 'dist' } },
  server: { publicDir: { name: './public' } },
});
