package dev.smash.capture;

import android.util.Base64;

import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.io.RandomAccessFile;
import java.net.HttpURLConnection;
import java.net.MalformedURLException;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Locale;
import java.util.function.BooleanSupplier;

/** tus 1.0 client. Every retry asks the server for its durable offset first. */
public final class TusUploader {
    private static final int CHUNK_BYTES = 256 * 1024;
    private final SegmentStore store;

    public TusUploader(SegmentStore store) { this.store = store; }

    public static final class UploadException extends IOException {
        public final boolean permanent;
        UploadException(String message, boolean permanent) {
            super(message);
            this.permanent = permanent;
        }
    }

    public static String normalizeEndpoint(String endpoint) {
        try {
            String text = endpoint.trim().replaceAll("/+$", "");
            URL url = new URL(text);
            if (!(url.getProtocol().equals("https") || url.getProtocol().equals("http"))
                    || url.getHost().isEmpty() || url.getUserInfo() != null
                    || url.getQuery() != null || url.getRef() != null) {
                throw new IllegalArgumentException("接收地址必须是 HTTP(S) 服务地址");
            }
            return text;
        } catch (IOException error) {
            throw new IllegalArgumentException("接收地址格式错误", error);
        }
    }

    public long upload(SegmentStore.Segment segment, String endpoint, String token,
                       BooleanSupplier current) throws IOException {
        JSONObject meta = segment.metadata;
        validate(segment);
        String expectedHash = meta.optString("sha256");
        if (!expectedHash.equals(sha256(segment.video))) {
            throw new UploadException("本地片段校验失败，文件已保留", true);
        }
        URL base = new URL(normalizeEndpoint(endpoint));
        String binding = endpoint + "\n" + hash(token.getBytes(StandardCharsets.UTF_8));
        JSONObject state = new JSONObject();
        if (segment.uploadState.isFile()) {
            try { state = SegmentStore.readJson(segment.uploadState); }
            catch (IOException ignored) { /* A damaged offset is recovered from HEAD, never guessed. */ }
        }
        URL uploadUrl = null;
        if (binding.equals(state.optString("binding")) && !state.optString("url").isEmpty()) {
            try {
                uploadUrl = new URL(state.optString("url"));
                requireSameOrigin(base, uploadUrl);
            } catch (MalformedURLException ignored) {
                // A corrupt local URL is recoverable through idempotent session/sequence creation.
                uploadUrl = null;
            }
        }
        checkCurrent(current);
        if (uploadUrl == null) {
            uploadUrl = create(base, token, segment);
            persist(segment, binding, uploadUrl, 0);
        }
        long length = segment.video.length();
        long offset;
        try { offset = head(uploadUrl, token, length); }
        catch (MissingUpload missing) {
            checkCurrent(current);
            uploadUrl = create(base, token, segment);
            persist(segment, binding, uploadUrl, 0);
            offset = head(uploadUrl, token, length);
        }
        persist(segment, binding, uploadUrl, offset);
        int conflicts = 0;
        byte[] buffer = new byte[CHUNK_BYTES];
        try (RandomAccessFile input = new RandomAccessFile(segment.video, "r")) {
            while (offset < length) {
                checkCurrent(current);
                int count = (int) Math.min(buffer.length, length - offset);
                input.seek(offset);
                input.readFully(buffer, 0, count);
                long next = patch(uploadUrl, token, offset, buffer, count);
                if (next < 0) {
                    if (++conflicts > 3) throw new UploadException("服务端上传偏移持续冲突，稍后重试", false);
                    offset = head(uploadUrl, token, length);
                } else {
                    offset = next;
                    conflicts = 0;
                }
                persist(segment, binding, uploadUrl, offset);
            }
        }
        checkCurrent(current);
        verify(uploadUrl, token, expectedHash);
        checkCurrent(current);
        try {
            JSONObject receipt = SegmentStore.readJson(segment.uploadState);
            receipt.put("confirmedSha256", expectedHash);
            SegmentStore.writeJson(segment.uploadState, receipt);
        } catch (org.json.JSONException error) { throw new IOException(error); }
        store.confirmed(segment);
        return System.currentTimeMillis() - meta.optLong("captureEpochMs") - meta.optLong("endUs") / 1000;
    }

    private static void validate(SegmentStore.Segment segment) throws UploadException {
        JSONObject m = segment.metadata;
        if (segment.video.length() <= 0 || !m.optString("session").matches("[a-fA-F0-9-]{36}")
                || !m.has("sequence") || m.optLong("sequence", -1) < 0
                || !m.has("startUs") || m.optLong("startUs", -1) < 0
                || !m.has("endUs") || m.optLong("endUs", -1) <= m.optLong("startUs")
                || m.optLong("captureEpochMs", 0) <= 0
                || !m.optString("sha256").matches("[a-f0-9]{64}")
                || !(m.opt("final") instanceof Boolean)) {
            throw new UploadException("本地片段清单字段无效，文件已保留", true);
        }
    }

    private static URL create(URL base, String token, SegmentStore.Segment segment) throws IOException {
        HttpURLConnection connection = connection(new URL(base.toString() + "/files"), token, "POST");
        connection.setRequestProperty("Upload-Length", Long.toString(segment.video.length()));
        String[] keys = {"session", "sequence", "startUs", "endUs", "captureEpochMs", "sha256", "final"};
        StringBuilder metadata = new StringBuilder();
        for (String key : keys) {
            if (metadata.length() > 0) metadata.append(',');
            metadata.append(key).append(' ').append(Base64.encodeToString(
                    String.valueOf(segment.metadata.opt(key)).getBytes(StandardCharsets.UTF_8), Base64.NO_WRAP));
        }
        connection.setRequestProperty("Upload-Metadata", metadata.toString());
        connection.setDoOutput(true);
        connection.setFixedLengthStreamingMode(0);
        try {
            try (OutputStream output = connection.getOutputStream()) { output.flush(); }
            int status = connection.getResponseCode();
            requireStatus(status, 201);
            String location = connection.getHeaderField("Location");
            if (location == null || location.isEmpty()) throw new UploadException("接收端没有返回上传地址", true);
            URL result = new URL(connection.getURL(), location);
            requireSameOrigin(base, result);
            return result;
        } finally { connection.disconnect(); }
    }

    private static long head(URL url, String token, long length) throws IOException {
        HttpURLConnection connection = connection(url, token, "HEAD");
        try {
            int status = connection.getResponseCode();
            if (status == 404 || status == 410) throw new MissingUpload();
            if (status != 200 && status != 204) requireStatus(status, 204);
            long offset = offset(connection);
            String remoteLength = connection.getHeaderField("Upload-Length");
            if (offset < 0 || offset > length
                    || (remoteLength != null && !Long.toString(length).equals(remoteLength))) {
                throw new UploadException("接收端片段长度或偏移不匹配", true);
            }
            return offset;
        } finally { connection.disconnect(); }
    }

    private static long patch(URL url, String token, long offset, byte[] data, int count) throws IOException {
        HttpURLConnection connection = connection(url, token, "PATCH");
        connection.setRequestProperty("Content-Type", "application/offset+octet-stream");
        connection.setRequestProperty("Upload-Offset", Long.toString(offset));
        connection.setDoOutput(true);
        connection.setFixedLengthStreamingMode(count);
        try {
            try (OutputStream output = connection.getOutputStream()) { output.write(data, 0, count); }
            int status = connection.getResponseCode();
            if (status == 409) return -1;
            if (status == 460) throw new UploadException("接收端 SHA-256 校验失败，文件已保留，请检查后重试", true);
            requireStatus(status, 204);
            long next = offset(connection);
            if (next != offset + count) throw new UploadException("接收端偏移确认不匹配，将重新同步", false);
            return next;
        } finally { connection.disconnect(); }
    }

    private static void verify(URL url, String token, String hash) throws IOException {
        HttpURLConnection connection = connection(url, token, "GET");
        try {
            requireStatus(connection.getResponseCode(), 200);
            ByteArrayOutputStream bytes = new ByteArrayOutputStream();
            try (InputStream input = connection.getInputStream()) {
                byte[] buffer = new byte[2048];
                int count;
                while ((count = input.read(buffer)) != -1) {
                    if (bytes.size() + count > 64 * 1024) throw new UploadException("接收端确认响应过大", true);
                    bytes.write(buffer, 0, count);
                }
            }
            JSONObject result;
            try { result = new JSONObject(bytes.toString("UTF-8")); }
            catch (Exception error) { throw new UploadException("接收端确认格式错误", true); }
            if (!result.optBoolean("complete", false)) throw new UploadException("片段已上传，等待接收端完成校验", false);
            if (!hash.equals(result.optString("sha256"))) throw new UploadException("接收端校验和不一致，文件已保留", true);
        } finally { connection.disconnect(); }
    }

    private static HttpURLConnection connection(URL url, String token, String method) throws IOException {
        HttpURLConnection connection = (HttpURLConnection) url.openConnection();
        connection.setInstanceFollowRedirects(false);
        connection.setConnectTimeout(10_000);
        connection.setReadTimeout(20_000);
        connection.setUseCaches(false);
        connection.setRequestMethod(method);
        connection.setRequestProperty("Tus-Resumable", "1.0.0");
        connection.setRequestProperty("Authorization", "Bearer " + token);
        return connection;
    }

    private static void requireStatus(int actual, int expected) throws UploadException {
        if (actual == expected) return;
        boolean permanent = actual >= 300 && actual < 500
                && actual != 408 && actual != 423 && actual != 429;
        throw new UploadException("接收端返回 HTTP " + actual
                + (permanent ? "，请检查地址、令牌或片段后重试" : "，稍后自动重试"), permanent);
    }

    private static long offset(HttpURLConnection connection) throws UploadException {
        try { return Long.parseLong(connection.getHeaderField("Upload-Offset")); }
        catch (Exception error) { throw new UploadException("接收端没有返回有效上传偏移", true); }
    }

    private static void requireSameOrigin(URL origin, URL target) throws UploadException {
        int firstPort = origin.getPort() < 0 ? origin.getDefaultPort() : origin.getPort();
        int secondPort = target.getPort() < 0 ? target.getDefaultPort() : target.getPort();
        if (!origin.getProtocol().equalsIgnoreCase(target.getProtocol())
                || !origin.getHost().equalsIgnoreCase(target.getHost()) || firstPort != secondPort
                || target.getUserInfo() != null || target.getRef() != null) {
            throw new UploadException("接收端返回了不同来源的上传地址，已停止以保护令牌", true);
        }
    }

    private static void persist(SegmentStore.Segment segment, String binding, URL url, long offset) throws IOException {
        try {
            SegmentStore.writeJson(segment.uploadState, new JSONObject()
                    .put("binding", binding).put("url", url.toString()).put("offset", offset));
        } catch (org.json.JSONException error) { throw new IOException(error); }
    }

    private static void checkCurrent(BooleanSupplier current) throws IOException {
        if (!current.getAsBoolean()) throw new IOException("上传配置已改变，正在重新连接");
    }

    private static String sha256(java.io.File file) throws IOException {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            try (InputStream input = new FileInputStream(file)) {
                byte[] buffer = new byte[64 * 1024];
                int count;
                while ((count = input.read(buffer)) != -1) digest.update(buffer, 0, count);
            }
            return hex(digest.digest());
        } catch (java.security.NoSuchAlgorithmException error) { throw new IOException(error); }
    }

    private static String hash(byte[] bytes) throws IOException {
        try { return hex(MessageDigest.getInstance("SHA-256").digest(bytes)); }
        catch (java.security.NoSuchAlgorithmException error) { throw new IOException(error); }
    }

    private static String hex(byte[] bytes) {
        StringBuilder text = new StringBuilder(bytes.length * 2);
        for (byte value : bytes) text.append(String.format(Locale.ROOT, "%02x", value & 0xff));
        return text.toString();
    }

    private static final class MissingUpload extends IOException { }
}
