package com.ruleflow

import org.junit.Test
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue

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
