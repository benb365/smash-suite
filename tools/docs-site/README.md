# 项目文档站

把仓库中的 README 和项目文档组合成可连续阅读的网页，提供章节侧栏、本地搜索和 Mermaid 架构图。正文仍在各自目录维护。

查看文档只需 Node.js 和 pnpm，无需准备 Python 环境或模型权重。

## 查看

需要 Node.js 20.19+ 和 pnpm 9+。在仓库根目录执行：

```sh
pnpm install --frozen-lockfile
pnpm run docs:dev
```

浏览器会打开 `http://127.0.0.1:5173/`；端口占用时使用下一个可用端口，以终端显示的网址为准。通过侧栏选择章节，使用搜索查找内容。搜索在浏览器本地运行，支持中文关键词。修改 Markdown 后页面自动刷新，按 `Ctrl-C` 停止服务。

只安装文档工具的依赖时，可将第一条命令换为 `pnpm --filter @smash-suite/docs-site install --frozen-lockfile`。

## 构建与预览

```sh
pnpm run docs:build
pnpm run docs:preview
```

构建产物位于本目录 `.vitepress/dist/`，缓存位于 `.vitepress/cache/`，均不提交 Git。预览也会打开浏览器，使用终端显示的实际地址。本工具提供本地阅读与静态构建。

## 文档与导航

- 顶层 [README](../../README.md) 是首页；模块、应用、工具和数据说明继续放在各自目录。
- [文档目录](../../docs/README.md) 提供阅读入口。章节顺序和站点设置在 `.vitepress/config.mts`，新增说明或嵌套目录中的报告时在对应侧栏分组加入链接；媒体、回合和数据集报告目录中的 Markdown 文件自动收录。
- Mermaid 图直接写在 Markdown 的 `mermaid` 代码块中，仓库页面和文档站共用同一份图。
- 正文引用的配置、说明等小型文本作为附件打开。历史报告中的失效路径以“工作区路径”显示，供在本地追溯；录像、模型权重及环境不打入站点。
- Agent 规则、`docs/ai/` 执行流水、归档和运行缓存不作为阅读章节，也不进入站内搜索；构建不修改原始正文。
