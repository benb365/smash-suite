# 视频接收端

Python 3.9+，仅使用标准库，可使用项目共同环境。tus 1.0 core + creation 接收 MP4，SQLite 保存上传状态；
FFmpeg 只负责无损重封装为 MPEG-TS，原 MP4 校验成功后立即可供分析，不等待 HLS。
这是独立验证接收端，本次不运行回合识别或精彩片段剪辑。

在仓库根目录运行：

```sh
export CAPTURE_TOKEN='replace-with-a-long-random-token'
python3 apps/android-capture/receiver/server.py \
  --host 0.0.0.0 --port 8787 --data apps/android-capture/.runtime/receiver \
  --ffmpeg /absolute/path/to/ffmpeg
```

`--ffmpeg` 默认查找 PATH；找不到时仍可接收和分析，但不生成 HLS。
不设置令牌则启动时生成并输出一个，重启会变化；`--token` 或 `CAPTURE_TOKEN` 可固定令牌，
至少 16 字符。App 接收地址填写 `http://电脑局域网IP:8787`，令牌填写相同内容。
手机与电脑需要互通，并允许电脑接收 8787 端口连接。默认仅绑定 `127.0.0.1`。

浏览器打开同一地址，可输入令牌查看会话、上传延迟及 HLS 播放。登录签发 12 小时
HttpOnly / SameSite=Strict 签名 cookie，令牌不放进播放 URL；支持原生 HLS 的浏览器
可直接观看（如 Safari），其他浏览器需使用支持 HLS 且能携带鉴权头的播放器。
首页没有在线 CDN 或第三方播放器依赖。刷新按钮重新读取状态。

HTTP 只用于受信任局域网验证。远程使用时在前面部署 HTTPS 反向代理，保留
`Authorization`、`Upload-*` 和 `Tus-*` 请求头，关闭请求缓冲，允许至少 32 MiB 请求，
并设置 `X-Forwarded-Proto: https` 以使浏览器凭据带 `Secure`。例如 Nginx 对应 location：

```nginx
location / {
    proxy_pass http://127.0.0.1:8787;
    proxy_http_version 1.1;
    proxy_request_buffering off;
    proxy_read_timeout 90s;
    client_max_body_size 32m;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header Host $host;
}
```

此配置片段不创建域名、证书、公共部署或多用户权限体系。单进程独占一个数据目录；
服务端不自动删除录像，磁盘保留策略由后续部署确定。

## 上传契约

所有上传请求使用 `Authorization: Bearer <token>`。`OPTIONS /files` 声明 tus 版本、
creation 扩展和大小上限。`POST/HEAD/PATCH` 都需要 `Tus-Resumable: 1.0.0`。
不支持 creation-with-upload、分块 Transfer-Encoding、删除或 tus checksum 扩展；
SHA256 是此应用完成确认的一部分。

1. `POST /files`：`Upload-Length` 为完整文件字节数，正文为空，返回 `201` 和相对 `Location`。
2. `HEAD <Location>`：返回持久化 `Upload-Offset`、`Upload-Length`，禁止缓存。
3. `PATCH <Location>`：`Content-Type: application/offset+octet-stream`，
   `Upload-Offset` 必须等于当前偏移；`Content-Length` 为本次字节数。服务端边接收边落盘，
   fsync 后才更新偏移并确认 `204`；连接中断时尽量保留已到达字节，重新 HEAD 再传。
4. 全部到齐后验证 SHA256。再 `GET <Location>`，只有 `complete: true` 且 `sha256`
   与本地相同才能删除手机缓存。HLS 出错不影响这个确认。

`Upload-Metadata` 是以下键值的逗号分隔列表，每个值为 UTF-8 文本的标准 Base64：

| 键 | 含义 |
| --- | --- |
| `session` | 小写、带连字符的标准 UUID；每次录制新建 |
| `sequence` | 从 0 开始的非负整数，不重复、不跳号 |
| `startUs` / `endUs` | 会话源时间轴上的视频区间，微秒，左闭右开；首片从 0 开始，相邻片边界严格相接 |
| `captureEpochMs` | 第一视频帧的手机墙钟毫秒；整个会话相同 |
| `sha256` | 完整 MP4 的小写十六进制 SHA256 |
| `final` | 文本 `true` / `false`；最后一片为 true，之后不能增加片段 |

片段必须是可独立解码的 H.264 + AAC MP4，视频从关键帧开始，内部 PTS 相对该片视频
起点，音轨保留其相对偏移。正常片段约 2 秒；单片视频区间上限 **6 秒**，字节数上限
**32 MiB**。服务端拒绝未知/重复元数据、无效 UUID、路径、逆序或重叠的源区间。
同一 `session + sequence` 的相同长度和全部相同元数据重复 POST 返回同一 Location；
不同内容或元数据返回 `409`。允许片段乱序到达。

主要错误：`401` 鉴权失败，`412` tus 版本不符，`409` 偏移或会话冲突，`413` 文件过大，
`415` PATCH 类型错误，`460` SHA256 不符。哈希不符时清空上传偏移，`complete` 保持 false，
手机应保留原片并显示错误供排查。各错误带 JSON `error`。

## 分析接口和时间口径

除 `/health` 和静态首页外，读取也需要 Bearer 或浏览器登录 cookie。

| 入口 | 内容 |
| --- | --- |
| `GET /health` | 存活、服务端当前 epoch 毫秒、HLS 是否配置 |
| `GET /sessions` | 每会话已校验数、连续前缀长度、HLS 数量、最新时延、错误 |
| `GET /sessions/{session}/segments` | JSON 分析索引；只发布从 sequence 0 开始且全部 SHA 校验通过的连续前缀 |
| `GET /sessions/{session}/segments.jsonl` | 同一索引的逐行 JSON 文件 |
| `GET /files/{id}/raw.mp4` | 已验证原 MP4，完整保存录音 |
| `GET /sessions/{session}/index.m3u8` | EVENT HLS，固定 TARGETDURATION 6；首片没准备好时为 503 |
| `GET /hls/{id}.ts` | 重封装后的双轨 MPEG-TS |

每条分析记录包含 `sequence/startUs/endUs/captureEpochMs/sha256/final`，还包含
`rawPath`（同机消费的绝对路径）、`rawUrl`、`receivedAtMs` 和 `latencyMs`：

```text
latencyMs = 服务端完整接收并校验的时间 - (手机第一视频帧墙钟 + 当前视频 endUs / 1000)
```

这个值含切片封装、排队、传输、校验耗时，**也含手机与服务端时钟差**，可能为负数。
测量前应让两端校时；它不等于单纯网络 RTT，也不含分析、剪辑、HLS 播放缓冲。
完整端到端一分钟出片不在本次验收范围。

分析进程按 `session + sequence` 自行保存消费进度，读取新前缀并消费原片，保留跨片算法状态。
`analysis/{session}.jsonl` 是原子替换的完整快照，不能持有旧文件描述符直接 tail；
重读快照或轮询 JSON 接口即可。手机全部上传完且 final 片属于连续前缀时，JSON `complete`
才为 true。录制异常终止且没有 final 时不声称会话完结。

HLS 为每片加入 DISCONTINUITY，并以 `startUs` 给两轨的原始 PTS 加源时间偏移；
不会累加 MP4 容器时长。AAC 包边界可以超出视频边界约一包，各包只属于一个原片。
最后一片成功重封装、全部前片也到齐后才发布 ENDLIST。FFmpeg 错误保存在会话状态中，
每 5 秒重试，重启后继续；分析接口不受这些错误阻塞。

## 验证

在仓库根目录运行：

```sh
FFMPEG=/absolute/path/to/ffmpeg python3 -B -m unittest discover \
  -s apps/android-capture/receiver -v
```

测试覆盖真实 HTTP 连接中断、持久偏移、进程状态重建、fsync/数据库提交窗口恢复、错误偏移、
SHA 失败、鉴权、幂等、乱序、final、分析前缀、浏览器凭据、真实 H.264/AAC 连续编码片段
及双轨 HLS 解码；逐包验证重封装 PTS 和跨片 AAC 连续性。找不到 FFmpeg 时仅跳过媒体测试。

参考：[tus 1.0](https://tus.io/protocols/resumable-upload)、[HLS RFC 8216](https://www.rfc-editor.org/rfc/rfc8216.html)。
