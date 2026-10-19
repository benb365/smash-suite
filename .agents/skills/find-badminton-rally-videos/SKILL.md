---
name: find-badminton-rally-videos
description: Find public badminton recordings through platform searches and uploader catalogs, inspect play-and-break continuity, and propose sources for human confirmation.
---

# Find Badminton Rally Videos

Find original recordings and inspect candidate windows. Use the
[test-video requirements](../../../modules/rally/evaluation.md#回合算法测试视频)
for coverage and [roadmap](../../../docs/plan/roadmap.md) for gaps.

## Reuse before searching

Follow the [collector's preflight and access rules](../curate-badminton-training-data/SKILL.md).
Reuse completed checks within the task; do not restart them at each handoff.
Inspect cached sources, downloaded originals and human main/backup/reject decisions.
A rejected window does not necessarily reject its whole source or uploader.

Read [dated search trials and uploader leads](references/search-notes.md) when
choosing Chinese queries or accounts. These are evidence and leads, not a
permanent approved list.

## Discover sources

Prefer native platform search for Chinese titles and uploaders; use general web
search for direct links and cross-platform replays.

- **Official:** event/year, players or matchup; add `回放`, `清流`, or `Court 2/3`
  when results are highlights or produced broadcasts.
- **Personal:** natural title terms such as `中羽三级/中羽3级`, `单打记录`,
  `单打对抗`, `练习赛`, or venue/date plus `单打`. Test community terms such as
  `平高仙人` and `省退`; they also retrieve teaching, equipment and short clips.
- **View gaps:** `低视角`, `场边视角`, `看台`, `校赛`, or local tournament names.
  Avoid long formal combinations of filming requirements as the default query.

Inspect small batches. When results are noisy, shorten the query or open a
promising uploader's **投稿 / videos** and nearby uploads or match series.
Verify profile ID, not nickname alone. An account may mix singles, doubles,
teaching, highlights and continuous recordings; judge individual videos.
Neither account identity nor player level establishes camera category.
Same uploader also does not establish the same venue/camera or recording session.

## Inspect play and breaks

1. Verify URL, uploader, singles/doubles, selected part and its own duration.
   Bilibili search cards may combine parts. The current collector drops `?p=`
   during URL normalization: verify the resolved ID before using any later part.
2. Inspect separated windows including **rally-to-rally transitions**, retrieval,
   walking back and service preparation. Check main-court coverage and stable
   framing; manual selection of the main court is allowed.
3. Look for omitted breaks, replay, speed changes, pan/zoom and camera switches.
   A static background or a title saying `完整/未剪辑/一镜到底` does not prove
   source time is continuous. Overlays or music alone do not prove a cut.
4. Use contact sheets and scene scores to locate suspect moments, then inspect
   adjacent native frames or full-rate playback. Sparse checks can reject a bad
   window, not certify an entire recording.
5. Record exact source ranges and uncertainties. Access failures leave unseen
   content unverified. Where a source has cutaways, seek a separate continuous
   window; do not stitch isolated rallies into a supposedly continuous test.

## Hand off for confirmation

Report a compact table:

`链接/标题 | UP/频道 | 建议视角 | 分P/时长 | 检查窗口 | 对打与间歇 | 问题/依据 | 建议`

Separate inspected candidates, access failures and unsuitable windows. Record
queries/account trails worth reusing and distinguish source rejection from
window rejection. Do not inflate diversity with related camera sessions or
count original duration as approved test duration.

After human source/category confirmation, hand off identity, windows, grouping,
main/backup decisions and limitations to the
[collector](../curate-badminton-training-data/SKILL.md).
Full-source downloads belong there when requested, not as a preview fallback.
The existing `record-search` accepts only court/people purposes; keep rally-only
search evidence in a linked report rather than mislabeling it as annotation data.
