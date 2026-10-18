import { useEffect, useState } from '@lynx-js/react';
import { capture, type CaptureState } from './bridge.js';
import './style.css';

const initial: CaptureState = {
  recording: false, starting: false, stopping: false, pendingSegments: 0, pendingBytes: 0,
  uploadedSegments: 0, endpoint: '', lastError: '', lastUploadLatencyMs: 0,
  oldestPendingAgeMs: 0, interruptedParts: 0, warning: '',
};

export function App() {
  const [state, setState] = useState(initial);
  const [bridgeError, setBridgeError] = useState('');
  useEffect(() => {
    let alive = true;
    const refresh = () => {
      try { capture.read((next) => { if (alive) setState(next); }); }
      catch { setBridgeError('未连接采集服务，请使用 Android 安装包打开。'); }
    };
    refresh();
    const timer = setInterval(refresh, 1000);
    return () => { alive = false; clearInterval(timer); };
  }, []);

  const active = state.recording || state.starting || state.stopping;
  const queued = state.pendingSegments > 0;
  const title = state.stopping ? '正在保存' : state.starting ? '正在启动' : state.recording ? '正在拍摄' : queued ? '正在补传' : '准备拍摄';
  const latency = state.uploadedSegments === 0 ? '—' : state.lastUploadLatencyMs < 0 ? '需校准时钟' : `${(state.lastUploadLatencyMs / 1000).toFixed(1)} 秒`;
  const error = state.lastError || bridgeError;
  return (
    <view className="page">
      <scroll-view className="content" scroll-y>
      <view className="heading">
        <text className="eyebrow">SMASH / CAPTURE</text>
        <view className="state-line">
          <view className={active ? 'dot live' : 'dot'} />
          <text className="title">{title}</text>
        </view>
        <text className="subtitle">开始后显示预览，同时采集原声</text>
      </view>

      <view className="spec"><text className="spec-text">1080p / 30fps · 约 2 秒一段</text></view>
      <view className="metrics">
        <view className="metric"><text className="number">{state.pendingSegments}</text><text className="label">待上传片段</text></view>
        <view className="metric"><text className="number">{(state.pendingBytes / 1048576).toFixed(0)}<text className="unit"> MB</text></text><text className="label">本地待传 / 2GB</text></view>
      </view>
      <view className="detail"><text className="label">最近上传用时</text><text className="value">{latency}</text></view>
      <text className="hint">从片段拍摄结束到接收确认；手机与电脑需校准时间。</text>
      {state.oldestPendingAgeMs > 10000 && <text className="warning">最早待传画面已积压 {Math.floor(state.oldestPendingAgeMs / 1000)} 秒，后端出片会延迟。</text>}
      {state.warning && <text className="warning">{state.warning}</text>}
      {!error && <text className="hint">断网继续保存，联网后按拍摄顺序补齐。</text>}
      <text className="footnote">开始后支持后台与熄屏录制。停止拍摄后，剩余片段继续上传。</text>
      </scroll-view>
      <view className="controls">
      {error && <text className="error">{error}</text>}
      <view className={active ? 'button stop' : 'button start'} bindtap={() => capture.command(active ? 'stop' : 'start')}>
        <text className="button-text">{state.stopping ? '保存最后片段中' : active ? '停止拍摄' : '开始拍摄'}</text>
      </view>
      <view className="actions">
        <view className="secondary" bindtap={() => capture.command('settings')}><text className="secondary-text">接收设置</text></view>
        <view className="secondary" bindtap={() => capture.command('retry')}><text className="secondary-text">继续补传</text></view>
      </view>
      <text className="endpoint">{state.endpoint || '先设置电脑的接收地址和令牌'}</text>
      </view>
    </view>
  );
}
