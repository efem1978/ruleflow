package com.ruleflow

import com.intellij.openapi.project.Project
import com.intellij.openapi.ui.Messages
import java.io.BufferedReader
import java.io.BufferedWriter
import java.io.InputStreamReader
import java.io.OutputStreamWriter
import java.nio.charset.StandardCharsets
import java.util.concurrent.CompletableFuture
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.atomic.AtomicInteger

class McpClient {
    @Volatile private var proc: Process? = null
    private var writer: BufferedWriter? = null
    private var reader: BufferedReader? = null
    private val seq = AtomicInteger(0)
    private val pending = ConcurrentHashMap<Int, CompletableFuture<String>>()

    fun start(project: Project) {
        if (proc != null) return
        try {
            val cfgBin = try { RuleFlowSettingsState.getInstance().pythonBin.trim() } catch (_: Exception) { "" }
            val envBin = System.getenv("MCP_PYTHON_BIN")?.takeIf { it.isNotBlank() }
            // Prefer workspace .mcp/venv first for out-of-the-box experience
            val base = project.basePath
            val venvPy = if (base != null) {
                val isWin = System.getProperty("os.name").lowercase().contains("win")
                val p = if (isWin) java.io.File(base, ".mcp/venv/Scripts/python.exe") else java.io.File(base, ".mcp/venv/bin/python")
                if (p.exists()) p.absolutePath else null
            } else null
            val py = when {
                !venvPy.isNullOrEmpty() -> venvPy
                !cfgBin.isNullOrEmpty() -> cfgBin
                envBin != null -> envBin
                System.getProperty("os.name").lowercase().contains("win") -> "python"
                else -> "python3"
            }
            val pb = ProcessBuilder(py, "-m", "mcp_rules_assistant.cli", "start")
            if (project.basePath != null) pb.directory(java.io.File(project.basePath!!))
            pb.redirectErrorStream(true)
            val p = pb.start()
            proc = p
            writer = BufferedWriter(OutputStreamWriter(p.outputStream, StandardCharsets.UTF_8))
            reader = BufferedReader(InputStreamReader(p.inputStream, StandardCharsets.UTF_8))
            // background reader
            val t = Thread {
                try {
                    while (true) {
                        val line = reader?.readLine() ?: break
                        if (line.isBlank()) continue
                        val id = extractId(line)
                        if (id != null) {
                            val fut = pending.remove(id)
                            fut?.complete(line)
                        }
                    }
                } catch (_: Exception) {
                } finally {
                    // complete any pending exceptionally
                    val ex = IllegalStateException("MCP server closed")
                    pending.forEach { (_, f) -> f.completeExceptionally(ex) }
                    pending.clear()
                }
            }
            t.isDaemon = true
            t.start()
        } catch (e: Exception) {
            proc = null
            writer = null
            reader = null
            Messages.showErrorDialog(project, "启动 MCP 失败: ${e.message}", "RuleFlow")
        }
    }

    fun isRunning(): Boolean = proc?.isAlive == true

    fun stop() {
        try { writer?.flush() } catch (_: Exception) {}
        try { writer?.close() } catch (_: Exception) {}
        try { reader?.close() } catch (_: Exception) {}
        try { proc?.destroy() } catch (_: Exception) {}
        proc = null
        writer = null
        reader = null
    }

    fun request(method: String, paramsJson: String = "{}", timeoutMs: Long = 4000): String {
        val id = seq.incrementAndGet()
        val payload = "{" +
                "\"jsonrpc\":\"2.0\"," +
                "\"id\":$id," +
                "\"method\":\"${escape(method)}\"," +
                "\"params\":$paramsJson" +
                "}\n"
        val fut = CompletableFuture<String>()
        pending[id] = fut
        val w = writer ?: throw IllegalStateException("MCP not started")
        synchronized(this) {
            w.write(payload)
            w.flush()
        }
        return fut.get(timeoutMs, java.util.concurrent.TimeUnit.MILLISECONDS)
    }

    private fun escape(s: String): String = s.replace("\\", "\\\\").replace("\"", "\\\"")

    private fun extractId(line: String): Int? {
        val re = "\\\"id\\\"\\s*:\\s*(\\d+)".toRegex()
        val m = re.find(line) ?: return null
        return try { m.groupValues[1].toInt() } catch (_: Exception) { null }
    }
}
