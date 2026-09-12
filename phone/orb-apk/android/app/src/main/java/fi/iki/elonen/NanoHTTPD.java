/*
 * NanoHTTPD -- Tiny HTTP server in Java
 * Copyright (c) 2012-2022 by Jarno Elonen <elonen@iki.fi> and contributors
 * This software is provided 'as-is', without any express or implied warranty.
 */
package fi.iki.elonen;

import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.*;

public class NanoHTTPD {

    public static final String VERSION = "2.3.1";

    public enum StartType {
        RUNNING, STARTING, STOPPED
    }

    public interface ServerRunnable {
        void run();
    }

    public static class Response {
        public enum Status {
            OK(200, "OK"),
            CREATED(201, "Created"),
            ACCEPTED(202, "Accepted"),
            NO_CONTENT(204, "No Content"),
            REDIRECT(301, "Moved Permanently"),
            NOT_MODIFIED(304, "Not Modified"),
            BAD_REQUEST(400, "Bad Request"),
            UNAUTHORIZED(401, "Unauthorized"),
            FORBIDDEN(403, "Forbidden"),
            NOT_FOUND(404, "Not Found"),
            METHOD_NOT_ALLOWED(405, "Method Not Allowed"),
            INTERNAL_ERROR(500, "Internal Server Error");

            public final int requestStatus;
            public final String description;

            Status(int requestStatus, String description) {
                this.requestStatus = requestStatus;
                this.description = description;
            }
        }

        public Status status = Status.OK;
        public String mimeType = "text/html";
        public Map<String, String> header = new HashMap<>();
        public InputStream data;
        public long contentLength = -1;
        public Map<String, String> chunkedHeader = new HashMap<>();

        public Response() {}

        public Response(Status status, String mimeType, InputStream data) {
            this.status = status;
            this.mimeType = mimeType;
            this.data = data;
        }

        public Response(Status status, String mimeType, String txt) {
            this.status = status;
            this.mimeType = mimeType;
            try {
                this.data = new ByteArrayInputStream(txt.getBytes(StandardCharsets.UTF_8));
            } catch (Exception e) {
                throw new RuntimeException(e);
            }
        }

        public Response(Status status, String mimeType, File file) {
            this.status = status;
            this.mimeType = mimeType;
            try {
                this.data = new FileInputStream(file);
                this.contentLength = file.length();
            } catch (Exception e) {
                throw new RuntimeException(e);
            }
        }

        public Response(Status status, String mimeType, FileDescriptor fd, long startPos, long length) {
            this.status = status;
            this.mimeType = mimeType;
            try {
                this.data = new FileInputStream(fd);
                this.data.skip(startPos);
                this.contentLength = length;
            } catch (Exception e) {
                throw new RuntimeException(e);
            }
        }

        public void addHeader(String name, String value) {
            header.put(name, value);
        }
    }

    public static class IHTTPSession {
        public String uri;
        public Method method;
        public Map<String, String> headers = new HashMap<>();
        public Map<String, String> parms = new HashMap<>();
        public InputStream inputStream;

        public enum Method { GET, PUT, POST, DELETE, HEAD, OPTIONS, PATCH, TRACE }

        public String getUri() { return uri; }
        public Method getMethod() { return method; }
        public Map<String, String> getHeaders() { return headers; }
        public Map<String, String> getParms() { return parms; }
        public InputStream getInputStream() { return inputStream; }
    }

    public static class CookieHandler {
        public static String parse(String cookieHeader) {
            return cookieHeader;
        }
    }

    private ServerSocket serverSocket;
    private Thread serverThread;
    private volatile boolean running = false;
    private int port;
    private int localPort;
    private final ExecutorService executor = Executors.newCachedThreadPool();
    private StartType startType = StartType.STOPPED;

    public NanoHTTPD(int port) {
        this.port = port;
    }

    public int getListeningPort() { return localPort; }
    public boolean isRunning() { return running; }
    public StartType getStartType() { return startType; }

    public void start() throws IOException {
        start(StartType.RUNNING);
    }

    public void start(StartType startType) throws IOException {
        this.startType = startType;
        if (running) return;
        serverSocket = new ServerSocket(port);
        localPort = serverSocket.getLocalPort();
        running = true;
        serverThread = new Thread(() -> {
            while (running) {
                try {
                    Socket socket = serverSocket.accept();
                    executor.submit(() -> handleRequest(socket));
                } catch (IOException e) {
                    if (running) e.printStackTrace();
                }
            }
        });
        serverThread.setDaemon(true);
        serverThread.start();
    }

    public void stop() {
        running = false;
        startType = StartType.STOPPED;
        try {
            if (serverSocket != null) serverSocket.close();
        } catch (IOException ignored) {}
        executor.shutdownNow();
    }

    private void handleRequest(Socket socket) {
        try (BufferedReader in = new BufferedReader(new InputStreamReader(socket.getInputStream(), StandardCharsets.UTF_8));
             OutputStream out = socket.getOutputStream()) {

            String requestLine = in.readLine();
            if (requestLine == null) return;
            String[] parts = requestLine.split(" ");
            if (parts.length < 3) return;

            IHTTPSession session = new IHTTPSession();
            session.method = IHTTPSession.Method.valueOf(parts[0]);
            session.uri = decodeUri(parts[1]);

            String line;
            while ((line = in.readLine()) != null && !line.isEmpty()) {
                int idx = line.indexOf(':');
                if (idx > 0) {
                    session.headers.put(line.substring(0, idx).trim().toLowerCase(), line.substring(idx + 1).trim());
                }
            }

            if ("post".equalsIgnoreCase(parts[0]) || "put".equalsIgnoreCase(parts[0])) {
                String contentLength = session.headers.get("content-length");
                if (contentLength != null) {
                    int len = Integer.parseInt(contentLength);
                    char[] buf = new char[len];
                    in.read(buf, 0, len);
                    session.inputStream = new ByteArrayInputStream(new String(buf).getBytes(StandardCharsets.UTF_8));
                }
            }

            Response response = serve(session);
            sendResponse(out, response);

        } catch (Exception e) {
            e.printStackTrace();
        } finally {
            try { socket.close(); } catch (IOException ignored) {}
        }
    }

    private String decodeUri(String uri) {
        int q = uri.indexOf('?');
        if (q >= 0) {
            String path = uri.substring(0, q);
            String query = uri.substring(q + 1);
            return path + "?" + query;
        }
        return uri;
    }

    private void sendResponse(OutputStream out, Response response) throws IOException {
        String statusLine = "HTTP/1.1 " + response.status.requestStatus + " " + response.status.description + "\r\n";
        out.write(statusLine.getBytes(StandardCharsets.UTF_8));
        out.write(("Content-Type: " + response.mimeType + "\r\n").getBytes(StandardCharsets.UTF_8));
        if (response.contentLength >= 0) {
            out.write(("Content-Length: " + response.contentLength + "\r\n").getBytes(StandardCharsets.UTF_8));
        }
        for (Map.Entry<String, String> e : response.header.entrySet()) {
            out.write((e.getKey() + ": " + e.getValue() + "\r\n").getBytes(StandardCharsets.UTF_8));
        }
        out.write("\r\n".getBytes(StandardCharsets.UTF_8));
        if (response.data != null) {
            byte[] buf = new byte[8192];
            int read;
            while ((read = response.data.read(buf)) > 0) {
                out.write(buf, 0, read);
            }
        }
        out.flush();
    }

    public Response serve(IHTTPSession session) {
        return new Response(Response.Status.INTERNAL_ERROR, "text/plain", "Not implemented");
    }
}