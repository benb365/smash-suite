import '@lynx-js/web-core/client';
import type { LynxViewElement } from '@lynx-js/web-core/client';
import { initialScreen, type JobState, type Point, type ScreenState } from './types';
import './host.css';

type Session = { id: string; token: string; preferences?: Pick<ScreenState, 'camera' | 'quality' | 'court'> };
type SaveHandle = { createWritable(): Promise<WritableStream<Uint8Array> & { abort(): Promise<void> }> };
type SaveWindow = Window & { showSaveFilePicker?: (options: unknown) => Promise<SaveHandle> };
const view = document.querySelector('#controls') as LynxViewElement;
const picker = document.querySelector('#file-picker') as HTMLInputElement;
const image = document.querySelector('#court-image') as HTMLImageElement;
const overlay = document.querySelector('#court-overlay') as SVGElement;
const video = document.querySelector('#result-video') as HTMLVideoElement;
const screen: ScreenState = { ...initialScreen, job: { ...initialScreen.job }, canSave: !!(window as SaveWindow).showSaveFilePicker };
let session: Session;
let connection: WebSocket | undefined;
let imageUrl = '';
let ready = false;
let ping: ReturnType<typeof setInterval> | undefined;
let reconnect: ReturnType<typeof setTimeout> | undefined;
let upload: XMLHttpRequest | undefined;
let requestedFrame = '';

function publish() {
  if (session) {
    session.preferences = { camera: screen.camera, quality: screen.quality, court: screen.court };
    sessionStorage.setItem('smash-session', JSON.stringify(session));
  }
  if (ready) view.sendGlobalEvent('product-state', [JSON.stringify(screen)]);
  const complete = screen.job.status === 'completed';
  document.querySelector<HTMLElement>('#welcome')!.hidden = !!screen.job.video;
  document.querySelector<HTMLElement>('#court-panel')!.hidden = !screen.job.video || complete;
  document.querySelector<HTMLElement>('#result-panel')!.hidden = !complete;
  if (complete && screen.job.output_url && video.getAttribute('src') !== screen.job.output_url) {
    video.src = screen.job.output_url;
  } else if (!complete && video.hasAttribute('src')) {
    video.pause(); video.removeAttribute('src'); video.load();
  }
  overlay.style.pointerEvents = screen.selectingCourt ? 'auto' : 'none';
  overlay.innerHTML = screen.court.length ? `<polygon points="${screen.court.map(([x, y]) => `${x * 1000},${y * 1000}`).join(' ')}" />${screen.court.map(([x, y], i) => `<circle cx="${x * 1000}" cy="${y * 1000}" r="9"/><text x="${x * 1000 + 14}" y="${y * 1000 - 14}">${i + 1}</text>`).join('')}` : '';
  document.querySelector('#court-hint')!.textContent = screen.selectingCourt
    ? `请沿顺时针或逆时针依次点击球场四角（已选 ${screen.court.length}/4）`
    : screen.court.length === 4 ? '已指定主球场。该区域只辅助识别，成片保留完整画面。'
    : screen.camera === 'high' ? '确认录像来自固定高视角，且主球场完整入镜。' : '确认录像画面。邻场干扰明显时，可在左侧选择“圈选主球场”。';
}

async function request(path: string, init: RequestInit = {}) {
  const response = await fetch(`/api/sessions/${session.id}${path}`, {
    ...init, headers: { Authorization: `Bearer ${session.token}`, ...init.headers },
  });
  if (!response.ok) {
    let message = `请求失败（${response.status}）`;
    try {
      const body = await response.json();
      message = typeof body.detail === 'string' ? body.detail : body.detail?.[0]?.msg ?? message;
    } catch { /* A stopped server may return no JSON body. */ }
    throw new Error(message);
  }
  return response;
}

async function firstFrame() {
  if (upload || !screen.job.video) return;
  const identity = `${session.id}:${screen.job.video.name}:${screen.job.video.duration_ms}`;
  if (requestedFrame === identity) return;
  requestedFrame = identity;
  try {
    const response = await request('/frame.jpg');
    const next = URL.createObjectURL(await response.blob());
    if (imageUrl) URL.revokeObjectURL(imageUrl);
    imageUrl = next; image.src = next;
  } catch (error) {
    requestedFrame = ''; screen.error = (error as Error).message; publish();
  }
}

function connect() {
  clearInterval(ping); clearTimeout(reconnect);
  const ws = new WebSocket(`${location.origin.replace(/^http/, 'ws')}/ws/sessions/${session.id}`);
  connection = ws;
  ws.onopen = () => {
    ws.send(JSON.stringify({ token: session.token }));
    ping = setInterval(() => { if (ws.readyState === WebSocket.OPEN) ws.send('ping'); }, 10000);
  };
  ws.onmessage = (event) => {
    if (screen.notice.startsWith('连接中断，')) screen.notice = '';
    screen.online = true;
    screen.job = JSON.parse(event.data);
    publish();
    void firstFrame();
  };
  ws.onclose = (event) => {
    if (connection !== ws) return;
    clearInterval(ping); screen.online = false;
    if (event.code === 4409) {
      // Duplicating a tab can copy sessionStorage. The existing connection
      // keeps ownership; the new tab gets an empty independent workspace.
      sessionStorage.removeItem('smash-session');
      void initialize(true);
    } else if (event.code === 4404) {
      sessionStorage.removeItem('smash-session');
      screen.error = '本次页面会话已过期，临时内容已清理，请重新选择录像。';
      void initialize(true);
    } else {
      screen.notice = '连接中断，正在重连；60 秒内恢复可继续本次工作。';
      reconnect = setTimeout(connect, 1500);
    }
    publish();
  };
  ws.onerror = () => ws.close();
}

async function initialize(fresh = false) {
  try {
    const saved = fresh ? null : sessionStorage.getItem('smash-session');
    if (saved) {
      session = JSON.parse(saved);
      const response = await request('');
      screen.job = await response.json();
      if (session.preferences) {
        Object.assign(screen, session.preferences);
        screen.selectingCourt = screen.court.length > 0 && screen.court.length < 4;
      }
    } else {
      const response = await fetch('/api/sessions', { method: 'POST' });
      if (!response.ok) throw new Error('暂时无法开始，请刷新页面重试。');
      const created = await response.json();
      session = { id: created.id, token: created.token }; screen.job = created.state;
      sessionStorage.setItem('smash-session', JSON.stringify(session));
      screen.court = []; requestedFrame = '';
    }
    connect(); publish();
  } catch (error) {
    if (!fresh && sessionStorage.getItem('smash-session')) {
      sessionStorage.removeItem('smash-session');
      return initialize(true);
    }
    screen.error = `${(error as Error).message} 请稍后重试。`; publish();
  }
}

picker.onchange = () => {
  const file = picker.files?.[0];
  picker.value = '';
  if (!file) return;
  screen.error = ''; screen.notice = ''; screen.court = []; screen.selectingCourt = false;
  requestedFrame = ''; screen.uploadProgress = 0;
  screen.job = { ...screen.job, status: 'uploading', stage: '正在导入录像', error: null, output_url: null };
  publish();
  const xhr = new XMLHttpRequest(); upload = xhr;
  xhr.open('POST', `/api/sessions/${session.id}/video`);
  xhr.setRequestHeader('Authorization', `Bearer ${session.token}`);
  xhr.setRequestHeader('Content-Type', 'video/mp4');
  xhr.setRequestHeader('X-File-Name', encodeURIComponent(file.name));
  xhr.upload.onprogress = (event) => {
    screen.uploadProgress = event.lengthComputable ? event.loaded / event.total : 0; publish();
  };
  xhr.onload = () => {
    upload = undefined;
    try {
      const body = JSON.parse(xhr.responseText);
      if (xhr.status < 200 || xhr.status >= 300) throw new Error(body.detail ?? '录像导入失败。');
      screen.job = body; void firstFrame();
    } catch (error) {
      screen.error = (error as Error).message;
      screen.job = { ...screen.job, status: 'failed', video: null };
    }
    publish();
  };
  xhr.onerror = () => { upload = undefined; screen.error = '导入中断，请重试。'; screen.job.status = 'failed'; publish(); };
  xhr.send(file);
};

overlay.addEventListener('pointerdown', (event) => {
  if (!screen.selectingCourt || screen.court.length >= 4) return;
  const rect = overlay.getBoundingClientRect();
  screen.court.push([Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width)),
                     Math.max(0, Math.min(1, (event.clientY - rect.top) / rect.height))]);
  if (screen.court.length === 4) screen.selectingCourt = false;
  publish();
});

async function save() {
  const savePicker = (window as SaveWindow).showSaveFilePicker;
  if (!savePicker) throw new Error('请使用 Chrome 或 Edge，以选择保存目录和文件名。');
  if (screen.saving) return;
  const name = (screen.job.video?.name ?? 'badminton.mp4').replace(/\.mp4$/i, '') + '-精简.mp4';
  // Open the system dialog before any network await so user activation is
  // preserved. The encoder result remains available if saving is cancelled.
  let writable: Awaited<ReturnType<SaveHandle['createWritable']>> | undefined;
  try {
    const handle = await savePicker.call(window, { suggestedName: name, types: [{ description: 'MP4 视频', accept: { 'video/mp4': ['.mp4'] } }] });
    screen.saving = true; screen.notice = ''; publish();
    writable = await handle.createWritable();
    const response = await request('/output.mp4');
    if (!response.body) throw new Error('没有可下载的成片内容。');
    await response.body.pipeTo(writable);
    screen.notice = '成片已保存到你选择的位置。';
  } catch (error) {
    if (writable) { try { await writable.abort(); } catch { /* pipeTo may already abort it. */ } }
    if ((error as Error).name !== 'AbortError') throw error;
  } finally {
    screen.saving = false; publish();
  }
}

const initialized = initialize();
view.nativeModulesMap = { Product: `${location.origin}/product-module.mjs` };
view.onNativeModulesCall = async (name: string, data: Record<string, unknown>) => {
  try {
    screen.error = '';
    if (name === 'ready') { ready = true; await initialized; }
    else if (name === 'pick') picker.click();
    else if (name === 'options') {
      if (data.camera) {
        screen.camera = data.camera as ScreenState['camera'];
        screen.court = []; screen.selectingCourt = false;
      }
      if (data.quality) screen.quality = data.quality as ScreenState['quality'];
    } else if (name === 'selectCourt') {
      if (!screen.selectingCourt) screen.court = [];
      screen.selectingCourt = true;
    }
    else if (name === 'clearCourt') { screen.court = []; screen.selectingCourt = false; }
    else if (name === 'run') {
      if (screen.court.length && screen.court.length !== 4) throw new Error('请选完球场四角，或清除后再开始。');
      const response = await request('/run', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ camera_type: screen.camera, quality: screen.quality, court: screen.court.length === 4 ? screen.court : null }) });
      screen.notice = ''; screen.job = await response.json();
    } else if (name === 'cancel') {
      upload?.abort(); upload = undefined;
      const response = await request('/cancel', { method: 'POST' }); screen.job = await response.json();
    } else if (name === 'save') await save();
    else throw new Error('不支持的页面操作。');
    publish(); return JSON.stringify(screen);
  } catch (error) {
    // Return the published state: Lynx for Web does not preserve a rejected
    // host Error across its worker bridge and can replace its message.
    screen.error = (error as Error).message; publish(); return JSON.stringify(screen);
  }
};
view.setAttribute('url', '/lynx/main.web.bundle');
