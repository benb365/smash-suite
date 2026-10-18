package dev.smash.capture;

import android.util.AtomicFile;

import org.json.JSONObject;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

/** Durable queue: only a sealed MP4 and its manifest are eligible for upload. */
public final class SegmentStore {
    public static final long LIMIT_BYTES = 2L * 1024 * 1024 * 1024;
    public static final long FREE_RESERVE_BYTES = 64L * 1024 * 1024;
    private final File directory;
    private volatile String warning = "";

    public SegmentStore(File directory) {
        this.directory = directory;
        if (!directory.isDirectory() && !directory.mkdirs()) {
            warning = "无法创建录像缓存目录";
        }
    }

    public File directory() { return directory; }
    public String warning() { return warning; }

    public static final class Segment {
        public final File video;
        public final File manifest;
        public final File uploadState;
        public final JSONObject metadata;

        Segment(File video, File manifest, JSONObject metadata) {
            this.video = video;
            this.manifest = manifest;
            this.uploadState = new File(manifest.getParentFile(),
                    manifest.getName().replace(".json", ".upload.json"));
            this.metadata = metadata;
        }
    }

    public synchronized List<Segment> pending() {
        List<Segment> segments = new ArrayList<>();
        String problem = "";
        File[] files = directory.listFiles();
        if (files == null) return segments;
        for (File manifest : files) {
            String name = manifest.getName();
            if (name.endsWith(".mp4") && !new File(directory,
                    name.substring(0, name.length() - 4) + ".json").isFile()) {
                problem = "缓存视频缺少清单，已保留等待检查：" + name;
            }
            if (!name.endsWith(".json") || name.endsWith(".upload.json")) continue;
            File video = new File(directory, name.substring(0, name.length() - 5) + ".mp4");
            try {
                Segment segment = new Segment(video, manifest, readJson(manifest));
                if (segment.uploadState.isFile()) {
                    try {
                        String confirmedHash = readJson(segment.uploadState).optString("confirmedSha256");
                        if (!confirmedHash.isEmpty() && confirmedHash.equals(segment.metadata.optString("sha256"))) {
                            confirmed(segment);
                            continue;
                        }
                    } catch (IOException error) {
                        problem = "已确认片段的清理尚未完成：" + name;
                    }
                }
                if (!video.isFile()) {
                    problem = "缓存清单缺少视频，已保留等待检查：" + name;
                    continue;
                }
                segments.add(segment);
            } catch (Exception error) {
                problem = "缓存清单损坏，已保留等待检查：" + name;
            }
        }
        segments.sort(Comparator
                .comparingLong((Segment s) -> s.metadata.optLong("captureEpochMs", Long.MAX_VALUE))
                .thenComparing(s -> s.metadata.optString("session"))
                .thenComparingLong(s -> s.metadata.optLong("sequence", Long.MAX_VALUE)));
        warning = problem;
        return segments;
    }

    public synchronized long totalBytes() {
        long size = 0;
        File[] files = directory.listFiles();
        if (files != null) for (File file : files) if (file.isFile()) size += file.length();
        return size;
    }

    public synchronized int interruptedParts() {
        return interruptedParts("");
    }

    public synchronized int interruptedParts(String activeSession) {
        Set<String> parts = new HashSet<>();
        File[] files = directory.listFiles();
        if (files != null) for (File file : files) {
            if (file.getName().endsWith(".part")
                    && (activeSession.isEmpty() || !file.getName().startsWith(activeSession + "-"))) {
                parts.add(file.getName().replaceFirst("\\.(mp4|json)\\.part$", ""));
            }
        }
        return parts.size();
    }

    public synchronized boolean canWrite(long nextBytes) {
        long amount = Math.max(0, nextBytes);
        return amount <= LIMIT_BYTES - totalBytes()
                && directory.getUsableSpace() >= FREE_RESERVE_BYTES + amount;
    }

    public synchronized void confirmed(Segment segment) throws IOException {
        // The fsynced confirmedSha256 receipt makes interrupted cleanup safe to repeat on restart.
        if (segment.video.exists() && !segment.video.delete()) {
            throw new IOException("接收端已确认，但无法删除本地视频");
        }
        if (segment.manifest.exists() && !segment.manifest.delete()) {
            throw new IOException("接收端已确认，但无法删除本地清单");
        }
        new AtomicFile(segment.uploadState).delete();
    }

    static JSONObject readJson(File file) throws IOException {
        try (FileInputStream input = new AtomicFile(file).openRead()) {
            if (input.getChannel().size() > 64 * 1024) throw new IOException("缓存清单过大");
            byte[] bytes = new byte[(int) input.getChannel().size()];
            int offset = 0;
            while (offset < bytes.length) {
                int read = input.read(bytes, offset, bytes.length - offset);
                if (read < 0) throw new IOException("缓存清单不完整");
                offset += read;
            }
            try { return new JSONObject(new String(bytes, StandardCharsets.UTF_8)); }
            catch (Exception error) { throw new IOException("缓存清单格式错误", error); }
        }
    }

    static void writeJson(File file, JSONObject value) throws IOException {
        AtomicFile atomic = new AtomicFile(file);
        FileOutputStream output = null;
        try {
            output = atomic.startWrite();
            output.write(value.toString().getBytes(StandardCharsets.UTF_8));
            output.getFD().sync();
            atomic.finishWrite(output);
        } catch (IOException error) {
            if (output != null) atomic.failWrite(output);
            throw error;
        }
    }
}
