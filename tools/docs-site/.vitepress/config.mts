import { readFileSync, readdirSync, realpathSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';
import { createRequire } from 'node:module';
import { defineConfig } from 'vitepress';
import { withMermaid } from 'vitepress-plugin-mermaid';
import { repositoryReferences } from './references.mjs';

const root = fileURLToPath(new URL('../../../', import.meta.url));
// Markdown lives outside this package; use this tool's installed dependencies.
const require = createRequire(import.meta.url);
const packageRoots = Object.fromEntries(['vue', 'vitepress', 'mermaid']
  .map(name => [name, realpathSync(fileURLToPath(new URL(`../node_modules/${name}`, import.meta.url)))]));
const fromVitePress = createRequire(resolve(packageRoots.vitepress, 'package.json'));
const fromMermaid = createRequire(resolve(packageRoots.mermaid, 'package.json'));
const dependencyRoots = {
  name: 'docs-dependency-roots',
  configResolved(config) {
    // These preload hints otherwise resolve from the repository root. The
    // plugin's old "debug" hint is not a dependency of the pinned Mermaid 11.
    config.optimizeDeps.include = config.optimizeDeps.include.filter(id => id !== 'debug').map(id => {
      if (id.startsWith('vitepress > ')) return fromVitePress.resolve(id.slice('vitepress > '.length));
      return ['@braintree/sanitize-url', 'dayjs', 'cytoscape-cose-bilkent', 'cytoscape'].includes(id)
        ? fromMermaid.resolve(id) : id;
    });
  },
};
const references = repositoryReferences(root);
const page = (text: string, file: string) => ({ text, link: `/${file.replace(/\.md$/, '')}` });
const reports = (directory: string) => readdirSync(resolve(root, directory))
  .filter(name => name.endsWith('.md'))
  .sort()
  .map(name => {
    const file = `${directory}/${name}`;
    const title = readFileSync(resolve(root, file), 'utf8').match(/^#\s+(.+)$/m)![1];
    return page(title, file);
  });

export default withMermaid(defineConfig({
  title: 'Smash Suite',
  description: '羽毛球视频套件：使用、模块开发和实验文档',
  lang: 'zh-CN',
  srcDir: root,
  srcExclude: [
    '**/node_modules/**', '**/.*/**', '**/dist/**', '**/build/**',
    'backup/**', 'docs/ai/**', 'datasets/badminton-v1/local/**',
    'AGENTS.md', 'CLAUDE.md',
  ],
  rewrites: { 'README.md': 'index.md' },
  cacheDir: './.vitepress/cache',
  outDir: './.vitepress/dist',
  markdown: { config: references.markdown },
  vite: {
    plugins: [references.vite, dependencyRoots],
    server: { watch: { ignored: ['**/tools/docs-site/.vitepress/{cache,dist,.temp}/**'] } },
    resolve: { alias: {
      'vitepress-plugin-mermaid/Mermaid.vue': require.resolve('vitepress-plugin-mermaid/Mermaid.vue'),
      vue: packageRoots.vue,
      mermaid: packageRoots.mermaid,
    } },
  },
  buildEnd: references.buildEnd,
  mermaid: {
    theme: 'neutral',
    themeVariables: { fontSize: '14px' },
    flowchart: { useMaxWidth: false, nodeSpacing: 18, rankSpacing: 34 },
  },
  themeConfig: {
    nav: [{ text: '首页', link: '/' }, page('文档目录', 'docs/README.md')],
    sidebar: [
      { text: '项目介绍', items: [
        { text: 'Smash Suite', link: '/' },
        page('文档目录', 'docs/README.md'),
      ] },
      { text: '基础模块', items: [
        { ...page('媒体读写', 'modules/media/README.md'), items: reports('modules/media/experiments') },
        { ...page('模型推理', 'modules/models/README.md'), items: [
          page('TrackNet 找球', 'modules/models/tracknet/README.md'),
          page('YOLO11n 人物检测', 'modules/models/yolo11n/README.md'),
          page('Keypoint R-CNN 人物姿态', 'modules/models/keypoint_rcnn/README.md'),
        ] },
        { ...page('回合识别', 'modules/rally/README.md'), items: [
          page('识别需求', 'modules/rally/requirements.md'),
          page('评估规范', 'modules/rally/evaluation.md'),
          page('实验与回放', 'modules/rally/experiments/README.md'),
          { text: '实验报告', collapsed: true, items: reports('modules/rally/experiments/reports') },
        ] },
        page('二维球路分析', 'modules/trajectory/README.md'),
      ] },
      { text: '产品', items: [
        { ...page('自动剪辑', 'apps/video-clipper/README.md'), items: [
          page('产品需求', 'apps/video-clipper/requirements.md'),
          { text: '性能试验', collapsed: true, items: [
            page('自动剪辑性能优化', 'docs/features/performance-optimization/README.md'),
            page('OPT-06 动态粗筛试验', 'apps/video-clipper/reports/opt06-dynamic/README.md'),
            page('OPT-08A 输入画幅试验', 'apps/video-clipper/reports/opt08a-fit320/README.md'),
          ] },
        ] },
        { ...page('Android 场边采集', 'apps/android-capture/README.md'), items: [
          page('采集接收端', 'apps/android-capture/receiver/README.md'),
        ] },
      ] },
      { text: '数据与工具', items: [
        { ...page('数据集', 'datasets/README.md'), items: [
          page('数据规范', 'datasets/requirements.md'),
          page('现用回合测试视频', 'datasets/test-videos.md'),
          ...reports('datasets/reports'),
        ] },
        page('录像采集插件', 'tools/ysp-recorder/README.md'),
        page('文档站', 'tools/docs-site/README.md'),
      ] },
      { text: '项目计划', items: [
        page('路线图', 'docs/plan/roadmap.md'),
        page('成片中的二维球路', 'docs/features/trajectory-overlay/README.md'),
        page('想法与灵感', 'docs/plan/ideas.md'),
      ] },
    ],
    outline: { label: '本页目录', level: [2, 3] },
    docFooter: { prev: '上一章', next: '下一章' },
    sidebarMenuLabel: '章节目录',
    returnToTopLabel: '返回顶部',
    darkModeSwitchLabel: '外观',
    search: { provider: 'local', options: {
      miniSearch: { options: {
        tokenize: text => [...new Intl.Segmenter('zh-CN', { granularity: 'word' }).segment(text)]
          .filter(part => part.isWordLike).map(part => part.segment),
      } },
      translations: {
      button: { buttonText: '搜索文档', buttonAriaLabel: '搜索文档' },
      modal: { noResultsText: '没有找到相关内容', resetButtonTitle: '清除搜索',
        footer: { selectText: '选择', navigateText: '切换', closeText: '关闭' } },
    } } },
  },
}));
