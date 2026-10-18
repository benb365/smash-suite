# 场边视频采集

独立 Android App 和最小接收端，不依赖现有网页应用，不接入或修改现有回合算法。
主要验证目标是红米 Note 8 Pro / Android 11；安装最低要求 Android 8.0、arm64。
其他机型和系统版本尚需实测，不能仅凭安装成功认定录制与音画同步通过。

## 数据路径

```text
Camera2 + 麦克风 → H.264 / AAC 连续编码 → 约 2 秒的独立 MP4
  → 手机持久队列 → tus 1.0 / HTTP(S) → 服务端保存并校验 SHA256
      ├─ 连续原始片段与时间索引 → 后续分析接口
      └─ FFmpeg 仅重封装 → HLS 观看
```

Lynx 页面负责开始/停止、接收设置、缓存和延迟状态；相机、编码、文件和上传留在
Android 服务中。以后跨端可复用 `ui/src/bridge.ts` 接口与页面，设备能力需各端实现。
App 不包含 FFmpeg、播放器、图片库或分析模型，使用系统硬件编码器；Lynx Bundle
内置于安装包，运行不依赖开发服务器。
安装包压缩原生库以减少下载体积，Android 安装时会解压，安装后占用会大于 APK 文件大小。

默认后置主摄、横屏、1920×1080 / 30fps、H.264 Baseline 4Mbps，
AAC-LC 48kHz 单声道 128kbps。能力不满足时明确报错，不悄悄降帧、降分辨率或省略录音。
通过持续编码和关键帧切片保持源时间轴；片长通常约 2 秒，上限 6 秒。
采集使用相机像素正向的横屏方向；反向横屏时提示换到另一侧，避免原片、HLS 和后续
图像分析对 MP4 旋转元数据的处理不同。

## 构建与安装

需要 Node 20.19+ 或 22.12+、JDK 17/21、Android SDK Platform 35 与 Build Tools 35.0.0。
依赖版本和 Gradle 分发校验值已固定，首次构建需要联网。

从本目录执行：

```sh
./build.sh
adb install -r dist/smash-capture-0.1.0-arm64-release.apk
```

输出经过压缩和资源裁减的、**使用本地调试密钥签名的测试安装包**。
它用于当前设备验证，正式分发时需替换 `android/app/build.gradle` 中的签名配置。
密钥和构建缓存保存在忽略管理的 `android/.android-home/`、`android/.gradle-home/`。
需要可调试版本时运行 `./build.sh debug`。APK、缓存和依赖均不提交 Git。

## 启动接收端

需要 Python 3.10+。接收与分析索引仅用标准库；HLS 还需要 FFmpeg。
从本目录执行，电脑和手机处于可互通网络：

```sh
python3 receiver/server.py --host 0.0.0.0 --port 8787
```

启动时会显示随机接收令牌。要跨重启沿用令牌，通过环境变量 `CAPTURE_TOKEN`
提供至少 16 字符的值。FFmpeg 不在环境路径中时，用 `--ffmpeg /absolute/path/to/ffmpeg`
指定；缺少 FFmpeg 时仍可接收原片和提供分析索引，HLS 不可用。
服务数据默认放在执行目录下的 `.runtime/receiver/`，重启复用同一目录。

打开手机 App 的“接收设置”，填写电脑局域网地址（例如 `http://192.168.1.2:8787`）
和接收令牌，保存后点击“开始拍摄”，授予相机和麦克风权限。手机地址不能填
`localhost` 或 `0.0.0.0`。局域网调试可用 HTTP；通过公网部署时使用具有受信任证书的
HTTPS 反向代理，App 原生支持 HTTPS。不要把令牌写入 URL。

电脑打开 `http://127.0.0.1:8787/`，用相同令牌登录后可查看会话、接收延迟和 HLS。
网页原生播放要求浏览器支持 HLS，例如 Safari；其他浏览器可使用支持携带鉴权头的
播放器。没有外部 CDN 或在线脚本依赖。

## 缓存与后台行为

- 手动开始后使用带通知的前台服务，支持后台/熄屏持续录制；系统强停、撤销权限、
  相机被占用或厂商省电策略仍可终止服务。红米设备需在系统设置中允许本 App 后台运行。
- Wi-Fi 和移动网络均可自动上传。断网继续录制，恢复后按会话/片段顺序补传；
  自动退避最长约 30 秒，检测到网络切换会提前重试。
- 本地总缓存上限 2 GiB，并给设备剩余存储保留至少 64 MiB。接近上限时停止拍摄并提示，
  不覆盖尚未确认保存的片段。停止拍摄后继续传剩余片段。
- 只有服务端确认文件完整且 SHA256 一致后才删除本地文件；上传偏移和完成收据持久化。
  应用重启后点击“继续补传”恢复已封口片段，不自动重新打开摄像头。
- 强杀/断电时正在写入的 `.part` 文件无法承诺恢复，保留在本地并提示，不伪装成完整录像。
  停止录制时等待最后片段保存，资源未释放前禁止新录制。
- 仅补传模式连续运行 4 小时会暂停并保留队列，需打开 App 继续；这也规避较新 Android
  的长时间后台数据同步限制。采集期间不使用这项补传时限。

## 延迟与分析接口

本轮验收覆盖采集端和接收端。正常网络无积压时，采集加上传按 5–10 秒预算设计，
这是待真机测量的目标，不是已测得的保证。回合结束至精彩片段可访问 ≤60 秒，
仍需后续接入分析和剪辑再做闭环验收。断网回合按完整性优先，恢复后延迟出片。

App 显示“片段拍摄结束至上传确认”的最近耗时；接收端索引的 `latencyMs` 是
`receivedAtMs - (captureEpochMs + endUs / 1000)`，两者都包含手机与电脑的时钟差。
先将两端时间校准，结合待传片段数和最早积压年龄判断网络是否跟得上。
保持平均上传速度高于录像码率，才能清空积压。

后续分析通过带 `Authorization: Bearer …` 的下列接口消费原始片段，无需等待 HLS：

| 接口 | 内容 |
| --- | --- |
| `GET /sessions` | 会话状态、接收数量、HLS 状态、延迟与错误 |
| `GET /sessions/{session}/segments` | 从 0 开始、无缺口的已校验片段列表 |
| `GET /sessions/{session}/segments.jsonl` | 同一列表的 JSONL 表示 |
| `GET /files/{id}/raw.mp4` | 单个原始音视频片段 |
| `GET /sessions/{session}/index.m3u8` | HLS EVENT，最终片段到齐后结束 |

每个片段带 `sequence`、`startUs`、`endUs`、`captureEpochMs`、`sha256`、
`final`、`receivedAtMs`、`latencyMs`、`rawPath` 和 `rawUrl`。
同机分析也可读 `.runtime/receiver/analysis/{session}.jsonl`；文件原子更新，消费者
按 session/sequence 去重并保留跨片段算法状态。`startUs/endUs` 是连续的视频源时间轴，
`endUs` 为不含尾边界；解码时将片内实际 PTS 加上 `startUs`，不要用片段容器时长累加。
AAC 一包约 21.33ms，可能跨视频切点；每包只保存一次，音轨保留相对偏移。

## 验证

接收端集成测试（生成测试音视频，不使用或改动羽毛球素材）：

```sh
FFMPEG=/absolute/path/to/ffmpeg python3 -m unittest discover -s receiver -v
```

Android 上传集成测试使用实际 Android 网络和文件 API，需连接已授权的设备和接收端：

```sh
./build.sh debug
adb install -r dist/smash-capture-0.1.0-arm64-debug.apk
adb shell run-as dev.smash.capture mkdir -p files
adb shell "run-as dev.smash.capture sh -c 'cat > files/tus-fixture.mp4'" < /path/to/2-second-av-fixture.mp4
cd android
./gradlew connectedDebugAndroidTest \
  -Pandroid.testInstrumentationRunnerArguments.endpoint=http://192.168.1.2:8787 \
  -Pandroid.testInstrumentationRunnerArguments.token="$CAPTURE_TOKEN"
```

该测试预传半个真实 MP4，模拟本地偏移未写入的中断，重新建立队列，从服务端偏移续传，
并验证鉴权失败不删文件、完整校验确认后才删。录制兼容性仍应在红米上实测：
连续录制、音画同步、停拍立即重录、断网/恢复、后台/熄屏、存储满停止，以及画质与发热。
各片段保存日志含实际视频帧数与帧率；不能仅凭配置为 30fps 就当作实际达到 30fps。

协议依据：[tus 1.0](https://tus.io/protocols/resumable-upload)、
[HLS RFC 8216](https://www.rfc-editor.org/rfc/rfc8216.html)、
[Lynx 原生模块](https://lynxjs.org/guide/use-native-modules.html)。
