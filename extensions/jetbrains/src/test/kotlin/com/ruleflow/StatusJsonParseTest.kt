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
        val txt = f.readText()
        // lightweight key presence checks
        assertTrue("expect key 'weak'", txt.contains("\"weak\""))
        assertTrue("expect key 'near'", txt.contains("\"near\""))
        assertTrue("expect key 'groups'", txt.contains("\"groups\""))
    }
}

