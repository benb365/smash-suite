import { existsSync, statSync } from 'node:fs';
import { delimiter, dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const suffix = process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python';
const configured = process.env.SMASH_SUITE_PYTHON;
const candidates = configured === undefined
  ? ['.venv-clip', '.venv'].map(name => join(root, name, suffix))
  : [resolve(root, configured)];
const python = candidates.find(path => existsSync(path) && statSync(path).isFile());

if (!python) {
  console.error(configured === undefined
    ? '未找到 Python 环境。请按 README.md 安装 .venv，或设置 SMASH_SUITE_PYTHON 指向 Python 可执行文件。'
    : `SMASH_SUITE_PYTHON 指向的文件不存在：${candidates[0]}。请设置 Python 可执行文件的绝对路径或仓库相对路径。`);
  process.exit(1);
}

const child = spawn(python, process.argv.slice(2), {
  cwd: root,
  stdio: 'inherit',
  windowsHide: true,
  env: {
    ...process.env,
    PYTHONUTF8: '1',
    PYTHONIOENCODING: 'utf-8',
    PYTHONPATH: [join(root, 'apps/video-clipper/backend'), root, process.env.PYTHONPATH]
      .filter(Boolean).join(delimiter),
  },
});
child.on('error', error => {
  console.error(`无法启动 Python（${python}）：${error.message}`);
  process.exitCode = 1;
});
child.on('exit', code => { process.exitCode = code ?? 1; });
