package dev.smash.capture;

import android.os.Bundle;
import android.test.InstrumentationTestCase;
import android.test.InstrumentationTestRunner;
import android.util.Base64;

import org.json.JSONObject;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Locale;
import java.util.UUID;

/** Opt-in integration test against the real receiver; no camera permission is needed. */
@SuppressWarnings("deprecation")
public final class TusUploaderTest extends InstrumentationTestCase {
    public void testResumeFromServerOffsetAndDeleteOnlyAfterVerifiedReceipt() throws Exception {
        Bundle args = ((InstrumentationTestRunner) getInstrumentation()).getArguments();
        String endpoint = args.getString("endpoint", "");
        String token = args.getString("token", "");
        assertFalse("Pass -e endpoint http://receiver:8765", endpoint.isEmpty());
        assertFalse("Pass -e token <receiver token>", token.isEmpty());
        endpoint = TusUploader.normalizeEndpoint(endpoint);
        File files = getInstrumentation().getTargetContext().getFilesDir();
        File fixture = new File(files, "tus-fixture.mp4");
        assertTrue("Copy a real MP4 to the debug app's files/tus-fixture.mp4 first", fixture.isFile());
        assertTrue("Fixture must contain at least two bytes", fixture.length() >= 2);
        String session = UUID.randomUUID().toString();
        File directory = new File(files, "tus-test-" + session);
        SegmentStore store = new SegmentStore(directory);
        File video = new File(directory, session + "-000000.mp4");
        try (InputStream input = new FileInputStream(fixture); OutputStream output = new FileOutputStream(video)) {
            byte[] buffer = new byte[64 * 1024];
            int count;
            while ((count = input.read(buffer)) != -1) output.write(buffer, 0, count);
        }
        String sha = digest(video);
        JSONObject metadata = new JSONObject().put("session", session).put("sequence", 0)
                .put("startUs", 0).put("endUs", 2_000_000)
                .put("captureEpochMs", System.currentTimeMillis() - 2000)
                .put("sha256", sha).put("final", true);
        File manifest = new File(directory, session + "-000000.json");
        SegmentStore.writeJson(manifest, metadata);
        SegmentStore.Segment segment = store.pending().get(0);

        StringBuilder encoded = new StringBuilder();
        String[] keys = {"session", "sequence", "startUs", "endUs", "captureEpochMs", "sha256", "final"};
        for (String key : keys) {
            if (encoded.length() > 0) encoded.append(',');
            encoded.append(key).append(' ').append(Base64.encodeToString(
                    String.valueOf(metadata.get(key)).getBytes(StandardCharsets.UTF_8), Base64.NO_WRAP));
        }
        HttpURLConnection create = request(new URL(endpoint + "/files"), token, "POST");
        URL upload;
        try {
            create.setRequestProperty("Upload-Length", Long.toString(video.length()));
            create.setRequestProperty("Upload-Metadata", encoded.toString());
            create.setDoOutput(true);
            create.setFixedLengthStreamingMode(0);
            create.getOutputStream().close();
            assertEquals(201, create.getResponseCode());
            upload = new URL(create.getURL(), create.getHeaderField("Location"));
            assertEquals("Receiver must return the same host", create.getURL().getHost(), upload.getHost());
        } finally { create.disconnect(); }
        int partial = (int) Math.min(128 * 1024, video.length() / 2);
        HttpURLConnection patch = request(upload, token, "PATCH");
        try {
            patch.setRequestProperty("Content-Type", "application/offset+octet-stream");
            patch.setRequestProperty("Upload-Offset", "0");
            patch.setDoOutput(true);
            patch.setFixedLengthStreamingMode(partial);
            byte[] bytes = new byte[partial];
            try (java.io.RandomAccessFile input = new java.io.RandomAccessFile(video, "r")) { input.readFully(bytes); }
            try (OutputStream output = patch.getOutputStream()) { output.write(bytes); }
            assertEquals(204, patch.getResponseCode());
            assertEquals(Integer.toString(partial), patch.getHeaderField("Upload-Offset"));
        } finally { patch.disconnect(); }

        // Simulate a crash after the server stored bytes but before the phone saved its offset.
        SegmentStore.writeJson(segment.uploadState, new JSONObject().put("url", upload.toString())
                .put("binding", endpoint + "\n" + digest(token.getBytes(StandardCharsets.UTF_8)))
                .put("offset", 0));
        SegmentStore restarted = new SegmentStore(directory);
        assertEquals(1, restarted.pending().size());
        try {
            new TusUploader(restarted).upload(restarted.pending().get(0), endpoint, token + "-invalid", () -> true);
            fail("Receiver must reject an invalid token");
        } catch (TusUploader.UploadException expected) { assertTrue(expected.permanent); }
        assertTrue("Authentication failure must preserve the video", video.isFile());
        assertTrue("Authentication failure must preserve its manifest", manifest.isFile());
        new TusUploader(restarted).upload(restarted.pending().get(0), endpoint, token, () -> true);
        assertEquals(0, restarted.pending().size());
        assertFalse(video.exists());
        assertFalse(manifest.exists());
        assertFalse(segment.uploadState.exists());
        assertTrue(directory.delete());
    }

    private static HttpURLConnection request(URL url, String token, String method) throws Exception {
        HttpURLConnection request = (HttpURLConnection) url.openConnection();
        request.setInstanceFollowRedirects(false);
        request.setConnectTimeout(10_000);
        request.setReadTimeout(20_000);
        request.setRequestMethod(method);
        request.setRequestProperty("Tus-Resumable", "1.0.0");
        request.setRequestProperty("Authorization", "Bearer " + token);
        return request;
    }

    private static String digest(File file) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        try (InputStream input = new FileInputStream(file)) {
            byte[] buffer = new byte[64 * 1024];
            int count;
            while ((count = input.read(buffer)) != -1) digest.update(buffer, 0, count);
        }
        return hex(digest.digest());
    }

    private static String digest(byte[] bytes) throws Exception {
        return hex(MessageDigest.getInstance("SHA-256").digest(bytes));
    }

    private static String hex(byte[] bytes) {
        StringBuilder text = new StringBuilder();
        for (byte value : bytes) text.append(String.format(Locale.ROOT, "%02x", value & 0xff));
        return text.toString();
    }
}
