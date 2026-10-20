# Video acquisition and MP4 checks

Use after the collector's preflight. Resolve source ID, URL, part, source-time
window and local paths from the user request or a confirmed dataset record.
Reuse verified local originals or clips first; if missing, download an original
only once per source and cut it using the confirmed parameters. Preserve the
recorded audio policy and source-time mapping. Bilibili cards may combine parts,
and the current collector normalizes away `?p=`: verify the actual selected part
and time axis. Do not overwrite a different source or clip under an existing ID.

## Choose the transfer

- **Discovery:** bounded previews; never remove the section constraint as a
  fallback for a failed preview.
- **Complete source:** when requested, download the selected original to
  `local/source-videos/<source-or-review-id>/source.mp4`, retaining audio.
- **Existing source window:** use [local extraction](#extract-from-a-local-original)
  with confirmed parameters, preserving the recorded audio policy and time mapping.
- **New sampled window:** use `sample-rally`, preferably with `--input` pointing
  to the verified original. It removes audio and accepts 60–300 seconds.

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
SOURCE_ID=CONFIRMED_SOURCE_ID
VIDEO_URL='CONFIRMED_SOURCE_URL'
MEDIA_DIR="datasets/badminton-v1/local/source-videos/$SOURCE_ID"
mkdir -p "$MEDIA_DIR"
"$CURATOR_PY" -m yt_dlp --ignore-config --no-playlist \
  --socket-timeout 20 --retries 1 --fragment-retries 1 --abort-on-unavailable-fragments \
  --no-progress --write-info-json --ffmpeg-location "$FFMPEG_PATH" \
  -S vcodec:h264 -f 'bv*[height<=1080]+ba/b[height<=1080]/bv*[height<=1080]' \
  --merge-output-format mp4 --remux-video mp4 \
  -o "$MEDIA_DIR/source.%(ext)s" "$VIDEO_URL" > "$MEDIA_DIR/download.log" 2>&1
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

## Extract from a local original

Use the variables above for the interpreter and FFmpeg. Set the input and target
from the dataset entry; keep the existing clip intact while checking a candidate.

```bash
SOURCE_VIDEO=INPUT_VIDEO_PATH
CLIP_DIR=CANDIDATE_CLIP_DIR
CLIP_VIDEO="$CLIP_DIR/clip.candidate.mp4"
START_S=START_FROM_DATASET
CUT_DURATION_S=DURATION_FROM_DATASET
mkdir -p "$CLIP_DIR"
"$FFMPEG_PATH" -hide_banner -nostdin -v error \
  -ss "$START_S" -i "$SOURCE_VIDEO" -t "$CUT_DURATION_S" \
  -map 0:v:0 -map '0:a?' -c copy -avoid_negative_ts make_zero \
  -movflags +faststart -n "$CLIP_VIDEO" > "$CLIP_DIR/extract.log" 2>&1
```

`-c copy` copies compressed streams without re-encoding; it does not promise an
arbitrary exact cut. Seeking depends on keyframes (frames that can start decoding
without earlier pictures), and reordered frames can affect the end. `-map '0:a?'`
retains available audio; use `-an` instead only when the recipe calls for silence.
`-avoid_negative_ts make_zero` shifts timestamps for the container; it does not
prove that its time zero is the first displayed video frame. Check actual timing
after extraction and record the offset back to the original.

If an exact non-keyframe boundary requires re-encoding, the existing
`sample-rally --input` workflow is available for new silent 60–300 second samples.
It is not a drop-in reconstruction method for existing tests. For a new derivative
whose native frame sequence must be retained, the following template decodes the
input before seeking and preserves variable frame timing; validate its result:

```bash
CLIP_VIDEO="$CLIP_DIR/clip.reencoded-candidate.mp4"
"$FFMPEG_PATH" -hide_banner -nostdin -v error \
  -i "$SOURCE_VIDEO" -ss "$START_S" -t "$CUT_DURATION_S" \
  -map 0:v:0 -map '0:a?' -c:v libx264 -crf 18 -preset medium \
  -fps_mode:v passthrough -enc_time_base:v demux -c:a aac \
  -movflags +faststart -n "$CLIP_VIDEO" > "$CLIP_DIR/reencode.log" 2>&1
```

This is lossy video/audio conversion, not proof of historical-file equivalence.
Use `-an` instead of the audio map and `-c:a aac` for a deliberately silent
derivative. Do not add a forced frame rate, scaling or interpolation. Keep a new
derivative separate from the established test input until its mapping is checked.

## Verify media

Before using a new or changed clip for model inference, also run the media module's
[complete input preflight](../../../../modules/media/README.md#输入预检).
It consumes the application's actual `FileFrameSource` to EOF and checks its
frame-count and timestamp contract. This video-only check supplements, rather
than replaces, the video/audio and source-mapping checks below.

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

For timestamp-sensitive media, use passthrough frame timing and the demuxer time
base in null-output checks. Investigate output time precision before altering
source timestamps or dropping frames; preserve failed diagnostics.

Successful decoding does not establish fixed framing or editorial continuity.
Those require visual review before test clips or durations are approved.

For a candidate clip, inspect stream metadata, decode every frame and obtain a
frame-by-frame timing and pixel-hash listing as well as the file hash:

```bash
"$FFMPEG_PATH" -hide_banner -nostdin -v info -i "$CLIP_VIDEO" \
  -map 0:v:0 -map '0:a?' -fps_mode passthrough -enc_time_base:v demux \
  -f null - > "$CLIP_DIR/decode.log" 2>&1
"$FFMPEG_PATH" -hide_banner -nostdin -v error -i "$CLIP_VIDEO" \
  -map 0:v:0 -an -fps_mode passthrough -enc_time_base:v demux \
  -f framemd5 -n "$CLIP_DIR/frames.framemd5"
shasum -a 256 "$CLIP_VIDEO"
```

Check each command's result; for complete decoding require a zero exit status
and inspect the decode log for errors. In `frames.framemd5`, use the header time
base to convert frame PTS (presentation timestamps) to seconds; count frame rows,
check first/last PTS and spacing, not just nominal FPS or container duration.
Account for the first displayed frame's offset instead of assuming it is zero.
For stream-copy equivalence, produce the same frame listing from the original
and compare the relevant frames' hashes and relative PTS after applying one
constant source-time offset. Also confirm audio presence and complete decoding.
For a lossy derivative, frame hashes will differ; verify frame count/timing and
visually check the first/last frames against the requested source range instead.

A matching SHA256 confirms identical file bytes. A different SHA256 after a
new download or remux does not by itself establish a different frame sequence;
check source identity, quality and frame correspondence. Existing cached model
observations are reusable only after their input identity and timing are verified.
Retain commands, logs, hashes and actual source/clip offsets with the local
materials and link their evidence from the existing record; do not replace
historical evidence with values inferred from a filename or requested window.
