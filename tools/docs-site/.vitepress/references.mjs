import { copyFileSync, createReadStream, existsSync, mkdirSync, realpathSync, statSync } from 'node:fs';
import { dirname, extname, relative, resolve, sep } from 'node:path';

// Markdown stays in its owning directory. Only referenced small text files
// become attachments; recordings, weights and environments are never copied.
export function repositoryReferences(root) {
  const attachments = new Map();
  const textExtensions = new Set(['.json', '.jsonl', '.txt', '.md', '.py', '.js', '.ts', '.csv', '.toml', '.yaml', '.yml']);
  const slash = path => path.split(sep).join('/');
  const route = path => path === 'README.md' ? '/' : `/${path.replace(/\.md$/, '.html')}`;
  const isPage = path => path.endsWith('.md') &&
    !path.split('/').some(part => part.startsWith('.') || ['node_modules', 'backup', 'dist', 'build'].includes(part)) &&
    !['AGENTS.md', 'CLAUDE.md'].includes(path) && !path.startsWith('docs/ai/') &&
    !path.startsWith('datasets/badminton-v1/local/');

  return {
    markdown(md) {
      md.core.ruler.after('inline', 'repository-references', state => {
        for (const block of state.tokens) {
          const tokens = block.children;
          if (!tokens) continue;
          for (let i = 0; i < tokens.length; i++) {
            const token = tokens[i];
            if (token.type !== 'link_open') continue;
            const href = token.attrGet('href');
            if (!href || /^(?:[a-z]+:|\/\/|#)/i.test(href)) continue;
            const url = new URL(href, 'http://docs.local');
            // URL.pathname is root-relative; resolve relative links from the
            // Markdown directory; the homepage rewrite stays in the same directory.
            let file = href.startsWith('/') ? resolve(root, `.${decodeURIComponent(url.pathname)}`)
              : resolve(dirname(state.env.path), decodeURIComponent(href.split(/[?#]/)[0]));
            if (existsSync(file) && statSync(file).isDirectory()) file = resolve(file, 'README.md');
            const path = slash(relative(root, file));
            if (path.startsWith('../')) continue;
            if (isPage(path) && existsSync(file)) {
              token.attrSet('href', route(path) + url.search + url.hash);
              continue;
            }
            if (!path.startsWith('docs/ai/') && existsSync(file) && statSync(file).isFile() &&
                !slash(relative(root, realpathSync(file))).startsWith('../') &&
                textExtensions.has(extname(file)) && statSync(file).size <= 8 * 1024 * 1024) {
              const attachment = `/references/${path}`;
              attachments.set(attachment, file);
              token.attrSet('href', attachment);
              token.attrSet('target', '_blank');
              continue;
            }
            // Historical reports keep their original paths in Git. A missing
            // workspace artifact is explained inline instead of becoming a 404.
            token.tag = 'span';
            token.attrs = [['class', 'workspace-reference'], ['title', href]];
            const end = tokens.findIndex((t, j) => j > i && t.type === 'link_close');
            tokens[end].tag = 'span';
            const note = new state.Token('text', '', 0);
            note.content = `（工作区路径：${href}）`;
            tokens.splice(end, 0, note);
            i = end + 1;
          }
        }
      });
    },
    vite: {
      name: 'repository-reference-attachments',
      configureServer(server) {
        server.middlewares.use((request, response, next) => {
          const path = decodeURIComponent(new URL(request.url, 'http://docs.local').pathname);
          const file = attachments.get(path);
          if (!file) return next();
          response.setHeader('Content-Type', 'text/plain; charset=utf-8');
          createReadStream(file).pipe(response);
        });
      },
    },
    buildEnd(config) {
      for (const [url, file] of attachments) {
        const destination = resolve(config.outDir, `.${url}`);
        mkdirSync(dirname(destination), { recursive: true });
        copyFileSync(file, destination);
      }
    },
  };
}
