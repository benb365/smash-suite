# Video acquisition and MP4 checks

Use after the collector's preflight. Resolve URL, video/part ID and duration
before transferring media; reuse a verified local original or an already
resolved public format list. Bilibili cards may combine parts, and the current
collector normalizes away `?p=`: verify the actual selected part and time axis.

## Choose the transfer

- **Discovery:** bounded previews; never remove the section constraint as a
  fallback for a failed preview.
- **Complete source:** when requested, download the selected original to
  `local/source-videos/<source-or-review-id>/source.mp4`, retaining audio.
- **Test window:** use `sample-rally`, preferably with `--input` pointing to the
  verified original. It currently removes audio and accepts 60–300 seconds.

The current helper re-encodes local inputs with libx264 and requests forced
keyframes for remote cuts. Its later remux does not make that sampling lossless
or guarantee original variable-frame-rate timestamps. Verify frame timing for
benchmark use; preserving complete originals and fixing sampling are separate tasks.

A public format failure is not a content rejection. Preserve the failure;
a later requested download may resolve successfully. Do not repeatedly retry
unchanged failures or use login/cookies to obtain unavailable quality.

## Complete-source download

The existing environment is ready after `status`. Run from the repository root,
substituting the confirmed ID and URL:

```bash
CURATOR_PY=.agents/skills/curate-badminton-training-data/.venv/bin/python
FFMPEG_PATH="$("$CURATOR_PY" -c 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())')"
MEDIA_DIR=datasets/badminton-v1/local/source-videos/SOURCE_ID
mkdir -p "$MEDIA_DIR"
"$CURATOR_PY" -m yt_dlp --ignore-config --no-playlist \
  --socket-timeout 20 --retries 1 --fragment-retries 1 --abort-on-unavailable-fragments \
  --no-progress --write-info-json --ffmpeg-location "$FFMPEG_PATH" \
  -S vcodec:h264 -f 'bv*[height<=1080]+ba/b[height<=1080]/bv*[height<=1080]' \
  --merge-output-format mp4 --remux-video mp4 \
  -o "$MEDIA_DIR/source.%(ext)s" VIDEO_URL > "$MEDIA_DIR/download.log" 2>&1
```

For Bilibili add `--impersonate chrome`. Prefer publicly available 1080p; record
actual quality and missing audio, if any. Preserve the selected stream's frame
rate/timestamps; do not force 30fps, upscale, interpolate or re-encode just to
change the container. Remux means changing the container without recompressing.
If codecs cannot be remuxed to the requested container, report that before
choosing a lossy conversion.

Keep raw info JSON and transfer logs local; record source identity/part, selected
format, duration, dimensions, fps, audio, bytes, SHA256 and stable local path in
the linked source record. Do not overwrite a different source under the same ID.

## Verify media

Inspect actual container streams and compare duration with the resolved source,
allowing metadata rounding. Check for skipped fragments/truncation. Decode the
entire file and retain errors/exit status; metadata or a thumbnail alone is not
a completeness check.

For complete originals, check video and any audio without rounding decoded
timestamps to the nominal frame duration:

```bash
"$FFMPEG_PATH" -hide_banner -nostdin -v error -i "$MEDIA_DIR/source.mp4" \
  -map 0:v:0 -map '0:a?' -fps_mode passthrough -enc_time_base:v demux \
  -f null - > "$MEDIA_DIR/decode.log" 2>&1
shasum -a 256 "$MEDIA_DIR/source.mp4"
```

The C1 trial produced false non-monotonic-DTS errors in the null output when it
used nominal-frame timing; passthrough plus demux time base decoded cleanly,
with the source hash unchanged. Investigate output time precision before
altering source timestamps or dropping frames; preserve failed diagnostics.

Successful decoding does not establish fixed framing or editorial continuity.
Those require visual review before test clips or durations are approved.
