package com.ultron.orb.server

import android.content.Context
import android.util.Log
import fi.iki.elonen.NanoHTTPD
import fi.iki.elonen.NanoHTTPD.IHTTPSession
import fi.iki.elonen.NanoHTTPD.Response
import fi.iki.elonen.NanoHTTPD.Response.Status
import java.io.ByteArrayInputStream
import java.net.URLDecoder

class AssetHttpServer(
    private val context: Context,
    port: Int = 0,
    private val assetPrefix: String = "public"
) : NanoHTTPD(port) {

    var boundPort: Int = 0
        private set

    override fun serve(session: IHTTPSession): Response {
        var uri = session.uri
        if (uri == "/") uri = "/index.html"

        uri = URLDecoder.decode(uri, "UTF-8")
        val assetPath = assetPrefix + uri

        val mimeType = when {
            uri.endsWith(".html") || uri.endsWith(".htm") -> "text/html"
            uri.endsWith(".css") -> "text/css"
            uri.endsWith(".js") -> "application/javascript"
            uri.endsWith(".mjs") -> "application/javascript"
            uri.endsWith(".json") -> "application/json"
            uri.endsWith(".png") -> "image/png"
            uri.endsWith(".jpg") || uri.endsWith(".jpeg") -> "image/jpeg"
            uri.endsWith(".gif") -> "image/gif"
            uri.endsWith(".svg") -> "image/svg+xml"
            uri.endsWith(".wasm") -> "application/wasm"
            uri.endsWith(".task") -> "application/octet-stream"
            else -> "application/octet-stream"
        }

        return try {
            val stream = context.assets.open(assetPath)
            val bytes = stream.readBytes()
            stream.close()
            Response(Status.OK, mimeType, ByteArrayInputStream(bytes))
        } catch (e: Exception) {
            Response(Status.NOT_FOUND, "text/plain", "Not found: $assetPath")
        }
    }

    override fun start(startType: NanoHTTPD.StartType) {
        super.start(startType)
        try {
            val field = NanoHTTPD::class.java.getDeclaredField("localPort")
            field.isAccessible = true
            boundPort = field.getInt(this)
        } catch (e: Exception) {
            e.printStackTrace()
        }
        Log.d("AssetHttpServer", "Serving on port $boundPort")
    }

    override fun stop() {
        super.stop()
        Log.d("AssetHttpServer", "Server stopped")
    }

    companion object {
        private const val TAG = "AssetHttpServer"
    }
}