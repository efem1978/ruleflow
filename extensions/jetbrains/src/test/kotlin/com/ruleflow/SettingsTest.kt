package com.ruleflow

import org.junit.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class SettingsTest {
    @Test
    fun defaults() {
        val s = RuleFlowSettingsState()
        assertEquals("", s.pythonBin)
        assertTrue(s.timeoutMs >= 1000)
        assertTrue(s.defaultRunChecks)
        assertTrue(s.defaultStrict)
        assertTrue(s.defaultDryRun)
    }
}

