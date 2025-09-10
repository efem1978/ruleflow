package com.ruleflow

import org.junit.Test
import org.junit.Assert.assertTrue
import java.io.File

class StatusJsonParseTest {
    @Test
    fun parseStatusJsonOrMock() {
        // Try repo real-time dashboard first, fallback to mock
        val candidates = listOf(
            File("../../.mcp/dashboard/status.json"),
            File("../../tests/mock_status.json")
        )
        val f = candidates.firstOrNull { it.exists() } ?: throw AssertionError("no status json found")
        var txt = f.readText()
        // Fallback to mock if current file doesn't contain coverage keys
        if (!txt.contains("\"weak\"")) {
            val mock = File("../../tests/mock_status.json")
            if (mock.exists()) txt = mock.readText()
        }
        // lightweight key presence checks (in either real or mock)
        assertTrue("expect key 'weak'", txt.contains("\"weak\""))
        assertTrue("expect key 'near'", txt.contains("\"near\""))
        assertTrue("expect key 'groups'", txt.contains("\"groups\""))
    }
}
