# YSP HLS Recorder

Standalone Chrome Manifest V3 DevTools extension for selecting a player area,
capturing ordinary HLS `.m3u8` requests, and recording them as a single `.ts`
file.

This tool does not use `yt-dlp`, `ffmpeg`, Native Messaging, or any local
command-line helper. It does not refresh signatures, bypass login checks, or
handle DRM/EME streams.

## Install

1. Open `chrome://extensions`.
2. Enable `Developer mode`.
3. Click `Load unpacked`.
4. Choose this directory: `tools/ysp-recorder`.
5. Open the target page and then open DevTools.
6. Select the `YSP HLS Recorder` DevTools panel.

## Use

1. Click `Pick Player Area` and select the player or its container.
2. Click `Bind Source`.
3. Replay or refresh the selected player if no source appears.
4. Select the desired `.m3u8` candidate when multiple sources are shown.
5. Click `Start Recording`.
6. Leave the page and DevTools panel open while recording.
7. Click `Stop & Merge` to create and download the final `ysp_*.ts` file.

The complete `.m3u8` URL is preserved, including query parameters such as
`ysign`, `ytime`, and `svrtime`.

## Recording model

- The recorder polls the media playlist every 2 seconds.
- New TS segments are downloaded once and appended in playlist order.
- Every 5 minutes, the current recording data is sealed as an internal chunk.
- Small TS segment blobs are not written as visible user files.
- Temporary chunks are stored in browser storage, preferably OPFS.
- When recording stops, all chunks are merged into one final `.ts` file.
- After the final download starts, temporary chunks are cleaned up shortly
  afterward.

## Limits

- Ordinary HLS TS streams only.
- `#EXT-X-KEY` encrypted HLS is rejected in v1.
- `.mp4` remuxing is not included.
- If the page closes or the signed `.m3u8` expires, recording can stop.
- Very long recordings are limited by available browser storage and memory.
- The extension requests broad host permissions so DevTools can observe m3u8
  requests in the inspected tab. Keep it installed only when you need it.

## Troubleshooting

- No sources appear: click `Bind Source`, then replay or refresh the player.
- Multiple sources appear: choose the source with the expected host/quality.
- Recording fails with 403: refresh the page to get a fresh signed m3u8.
- Final file does not play: confirm the stream is unencrypted HLS TS and not
  DRM/EME or fragmented MP4.
