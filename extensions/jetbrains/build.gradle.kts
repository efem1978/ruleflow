plugins {
    kotlin("jvm") version "1.9.10"
    id("org.jetbrains.intellij") version "1.16.0"
}

group = "com.ruleflow"
version = "0.0.1"

repositories { mavenCentral() }

intellij {
    type.set("IC") // IntelliJ Community
    version.set("2023.1")
}

tasks {
    patchPluginXml {
        sinceBuild.set("231")
        untilBuild.set(null as String?)
    }
}

