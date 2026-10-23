import { useEffect, useState } from '@lynx-js/react';
import { action } from './bridge';
import { initialScreen, type CameraType, type Quality, type ScreenState } from './types';
import './styles.css';

const cameras: { key: CameraType; title: string; hint: string; mark: string }[] = [
  { key: 'high', title: '比赛高视角', hint: '从高处俯看，球场完整入镜', mark: '01' },
  { key: 'courtside', title: '场边低视角', hint: '靠近底线，基本正对球场', mark: '02' },
  { key: 'personal', title: '个人斜侧方', hint: '从球场角落或侧面拍摄', mark: '03' },
];
const qualities: { key: Quality; title: string }[] = [
  { key: 'high', title: '高画质' }, { key: 'balanced', title: '均衡' }, { key: 'small', title: '小体积' },
];

function duration(ms: number) {
  const seconds = Math.round(ms / 1000);
  return `${Math.floor(seconds / 60)}分${seconds % 60}秒`;
}

function elapsed(seconds: number) {
  const tenths = Math.round(seconds * 10);
  const minutes = Math.floor(tenths / 600);
  const remainder = ((tenths % 600) / 10).toFixed(1);
  return minutes ? `${minutes}分${remainder}秒` : `${remainder}秒`;
}

export function App() {
  const [screen, setScreen] = useState<ScreenState>(initialScreen);
  const [localError, setError] = useState('');
  useEffect(() => {
    const events = lynx.getJSModule('GlobalEventEmitter');
    const receive = (next: unknown) => setScreen(JSON.parse(String(next)) as ScreenState);
    events.addListener('product-state', receive);
    action('ready').then(setScreen).catch((e) => setError(e.message));
    return () => events.removeListener('product-state', receive);
  }, []);
  function invoke(name: string, data: unknown = {}) {
    setError('');
    action(name, data).then(setScreen).catch((e) => setError(e.message));
  }
  const { job } = screen;
  const busy = job.status === 'running' || job.status === 'uploading';
  const error = localError || screen.error || job.error;
  const progress = job.status === 'uploading' ? screen.uploadProgress : job.progress;
  const timings: [string, number][] = job.timings && job.elapsed_s !== null ? [
    ['准备', job.timings.preparation_s], ['识别', job.timings.recognition_s],
    ['生成成片', job.timings.rendering_s], ['总计', job.elapsed_s],
  ] : [];
  return (
    <scroll-view className="controls" scroll-y>
      <view className="brand"><view className="brand-icon"><text className="brand-letter">S</text></view><view><text className="brand-name">Smash Suite</text><text className="brand-caption">羽毛球录像 · 自动剪辑</text></view></view>
      <view className="intro"><text className="intro-title">开始一份新剪辑</text><text className="muted">只留下比赛中的对打时刻。</text></view>
      <view className="section-label"><text className="step">01</text><text className="section-title">选择拍摄类型</text></view>
      <view className="camera-list">{cameras.map((camera) => <view key={camera.key} className={`camera ${screen.camera === camera.key ? 'selected' : ''}`} bindtap={() => !busy && invoke('options', { camera: camera.key })}>
        <view className="camera-mark"><text className="camera-number">{camera.mark}</text></view><view className="camera-copy"><text className="camera-title">{camera.title}</text><text className="camera-hint">{camera.hint}</text></view><view className={`radio ${screen.camera === camera.key ? 'checked' : ''}`} />
      </view>)}</view>
      <view className="section-label second"><text className="step">02</text><text className="section-title">导入录像</text></view>
      <view className={`upload ${busy ? 'disabled' : ''}`} bindtap={() => !busy && invoke('pick')}>
        <text className="upload-icon">＋</text><text className="upload-title">{job.video ? '更换 MP4 录像' : '选择 MP4 录像'}</text><text className="upload-hint">横屏 · 最高 1080p · 单打</text>
      </view>
      {job.video && <view className="file-info"><text className="file-name">{job.video.name}</text><text className="file-meta">{duration(job.video.duration_ms)} · {job.video.width} × {job.video.height}{job.video.has_audio ? ' · 有原声音' : ' · 无音轨'}</text></view>}
      {job.video && screen.camera === 'high' && !busy && job.status !== 'completed' && <view className="shot-path-option" bindtap={() => invoke('options', { showShotPaths: !screen.showShotPaths })}><view className={`checkbox ${screen.showShotPaths ? 'checked' : ''}`}>{screen.showShotPaths && <text className="checkbox-mark">✓</text>}</view><view className="shot-path-copy"><text className="setting-title">在成片中显示球路</text><text className="muted small">高视角默认开启，可随时关闭</text></view></view>}
      {job.video && screen.camera !== 'high' && !busy && job.status !== 'completed' && <view className="court-actions"><view bindtap={() => invoke('selectCourt')}><text className="link">{screen.selectingCourt ? `继续选角点（${screen.court.length}/4）` : '圈选主球场'}</text></view>{screen.court.length > 0 && <view bindtap={() => invoke('clearCourt')}><text className="muted small">清除</text></view>}</view>}
      <view className="quality-heading"><text className="setting-title">成片质量</text><text className="muted small">前后各保留 0.5 秒</text></view>
      <view className="quality-options">{qualities.map((quality) => <view key={quality.key} className={`quality ${screen.quality === quality.key ? 'active' : ''}`} bindtap={() => !busy && invoke('options', { quality: quality.key })}><text className="quality-text">{quality.title}</text></view>)}</view>
      {busy && <view className="progress-panel"><view className="progress-label"><text className="progress-title">{job.stage}</text><text className="progress-number">{Math.round(progress * 100)}%</text></view><view className="progress-track"><view className="progress-fill" style={{ width: `${Math.max(2, progress * 100)}%` }} /></view><text className="muted small">处理需要一些时间，可以随时取消。</text></view>}
      {job.status === 'completed' && <view className="complete"><text className="complete-title">✓ 成片已生成</text><text className="complete-info">{job.rally_count}段对打 · {duration(job.output_duration_ms ?? 0)} · {((job.output_bytes ?? 0) / 1048576).toFixed(1)} MB</text>{timings.length > 0 && <view className="timings">{timings.map(([label, seconds]) => <view key={label} className="timing-row"><text className="timing-label">{label}</text><text className="timing-value">{elapsed(seconds)}</text></view>)}</view>}</view>}
      {error && <view className="error"><text className="error-text">{error}</text></view>}
      {screen.notice && <view className="notice"><text className="notice-text">{screen.notice}</text></view>}
      {job.warnings.map((warning) => <view key={warning} className="notice"><text className="notice-text">{warning}</text></view>)}
      {busy ? <view className="button secondary" bindtap={() => invoke('cancel')}><text className="button-text dark">取消处理</text></view> : job.status === 'completed' ? <view className={`button ${screen.saving ? 'disabled' : ''}`} bindtap={() => !screen.saving && invoke('save')}><text className="button-text">{screen.saving ? '正在保存…' : '保存 MP4　↗'}</text></view> : <view className={`button ${!job.video || !screen.online ? 'disabled' : ''}`} bindtap={() => job.video && screen.online && invoke('run')}><text className="button-text">开始自动剪辑　→</text></view>}
      {job.status === 'completed' && <view className="restart" bindtap={() => invoke('pick')}><text className="link">再处理一份录像</text></view>}
      {!screen.canSave && <view className="notice"><text className="notice-text">请使用 Chrome 或 Edge，以选择成片保存位置。</text></view>}
      <text className="session-note">关闭页面 60 秒后清理本次临时内容。已保存的成片不会删除。</text>
    </scroll-view>
  );
}
