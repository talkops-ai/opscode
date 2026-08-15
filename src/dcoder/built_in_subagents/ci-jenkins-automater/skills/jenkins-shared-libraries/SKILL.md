---
name: jenkins-shared-libraries
description: >
  Production-grade Jenkins Shared Library engineering covering strict directory
  structure segregation (vars/, src/, resources/), global variable authoring with
  def call() patterns, CPS transformation constraints and java.io.NotSerializableException
  avoidance, @NonCPS annotation rules (FATAL: never call pipeline steps from @NonCPS),
  Serializable implementation requirements, and libraryResource asset loading. Use when:
  (1) scaffolding shared library directory structures, (2) writing global pipeline steps
  in vars/ with def call(Map config) or def call(Closure body), (3) authoring OOP
  utility classes in src/ with package structures, (4) navigating CPS serialization
  boundaries (avoiding java.io.File, Matcher, closures with non-serializable state),
  (5) encapsulating non-serializable logic in @NonCPS methods, or (6) loading static
  resources via libraryResource. Do NOT use for pipeline generation (use
  jenkins-pipeline-generation), unit testing (use jenkins-pipeline-testing), or
  Job DSL (use jenkins-job-dsl-jcasc).
license: MIT
compatibility: designed for deepagents-code
---

# Jenkins Shared Library Engineering

Scaffold, author, and structure production-grade Jenkins Shared Libraries with strict CPS compliance, directory segregation, and Serializable safety.

---

## Core Principles

1. **DRY**: Centralise pipeline logic — never duplicate across repositories.
2. **Segregate Concerns**: `vars/` for pipeline steps, `src/` for OOP logic, `resources/` for static assets.
3. **CPS Compliance**: Every line of shared library code must survive Jenkins' CPS serialization.
4. **@NonCPS Boundary**: Complex data processing in `@NonCPS` methods — but **NEVER** call pipeline steps from them.

---

## Directory Structure

```
shared-library/
├── vars/                        # Global variables and custom pipeline steps
│   ├── standardPipeline.groovy  # Invoked as standardPipeline() in Jenkinsfiles
│   ├── buildDocker.groovy       # Invoked as buildDocker()
│   └── standardPipeline.txt     # Optional: help text displayed in Jenkins UI
├── src/                         # Standard Java/Groovy OOP classes
│   └── org/
│       └── company/
│           ├── utils/
│           │   ├── GitUtils.groovy
│           │   └── DockerUtils.groovy
│           └── models/
│               └── BuildConfig.groovy
├── resources/                   # Static assets loaded via libraryResource
│   ├── templates/
│   │   └── k8s-deployment.yaml
│   └── configs/
│       └── default-settings.json
└── test/                        # Unit tests (see jenkins-pipeline-testing)
    └── groovy/
        └── org/company/
```

---

## vars/ — Global Variables and Pipeline Steps

Files in `vars/` become globally available pipeline steps. The filename becomes the step name.

### Basic Pattern: `def call()`

```groovy
// vars/standardPipeline.groovy
def call(Map config = [:]) {
    pipeline {
        agent none
        options {
            disableConcurrentBuilds(abortPrevious: true)
            timeout(time: config.get('timeout', 30), unit: 'MINUTES')
        }
        stages {
            stage('Build') {
                agent { docker { image config.get('buildImage', 'maven:3.9') } }
                steps {
                    sh config.get('buildCommand', 'mvn clean package')
                }
            }
            stage('Test') {
                agent { docker { image config.get('buildImage', 'maven:3.9') } }
                steps {
                    sh config.get('testCommand', 'mvn test')
                }
            }
        }
    }
}
```

**Usage in a consuming Jenkinsfile:**

```groovy
@Library('my-shared-lib') _
standardPipeline(
    buildImage: 'maven:3.9-eclipse-temurin-21',
    buildCommand: 'mvn clean package -DskipTests',
    testCommand: 'mvn verify',
    timeout: 45
)
```

### Closure Pattern: `def call(Closure body)`

```groovy
// vars/withNotification.groovy
def call(Closure body) {
    try {
        body()
    } catch (Exception e) {
        slackSend channel: '#builds', message: "Build failed: ${e.message}"
        throw e
    }
}
```

**Rules for `vars/`:**
- Filename = step name (e.g., `vars/buildDocker.groovy` → `buildDocker()`)
- Must implement `def call(...)` method
- Keep logic **minimal** — delegate complexity to `src/` classes
- Optional `.txt` file provides help text in Jenkins UI

---

## src/ — Object-Oriented Groovy Classes

Standard Java-style OOP with strict package structures:

```groovy
// src/org/company/utils/GitUtils.groovy
package org.company.utils

import java.io.Serializable

class GitUtils implements Serializable {
    private static final long serialVersionUID = 1L

    private def script    // Reference to the pipeline script

    GitUtils(def script) {
        this.script = script
    }

    String getCommitSha() {
        return script.sh(
            script: 'git rev-parse HEAD',
            returnStdout: true
        ).trim()
    }

    String getBranchName() {
        return script.env.BRANCH_NAME ?: script.sh(
            script: 'git rev-parse --abbrev-ref HEAD',
            returnStdout: true
        ).trim()
    }
}
```

**Rules for `src/`:**
- Follow strict package structures (`src/org/company/module/`)
- Implement `java.io.Serializable` where required by Jenkins
- Pass `this` (the pipeline script) to constructors for step access
- Complex data parsing classes go here, not in `vars/`

---

## resources/ — Static Assets

```groovy
// Loading a resource from within a pipeline step
def k8sManifest = libraryResource('templates/k8s-deployment.yaml')
writeFile file: 'deployment.yaml', text: k8sManifest
```

---

## CPS Constraints — The Critical Knowledge

Jenkins rewrites Groovy at compile-time into **Continuation-Passing Style (CPS)** to enable pipeline serialization (pause → save to disk → resume). This imposes severe restrictions.

### What CPS Allows (Standard Pipeline Code)

- Calling Jenkins steps: `sh`, `git`, `echo`, `checkout`, `build`
- Pausing execution (input steps, approval gates)
- Declarative directive blocks

### What CPS Prohibits ⚠️

| Prohibited Pattern | Why It Breaks | Fix |
|---|---|---|
| `java.io.File` | Not serializable | Use `readFile`/`writeFile` steps |
| `java.util.regex.Matcher` | Not serializable | Extract to `@NonCPS` method |
| `.each { }`, `.collect { }`, `.map { }` on closures with non-serializable state | Closure state not serializable | Use traditional `for` loops |
| Network sockets, HTTP clients | Not serializable | Use `sh 'curl ...'` or `@NonCPS` |
| `JsonSlurper` in CPS context | Not serializable | Use `@NonCPS` or `sh 'jq ...'` |

### @NonCPS — The Escape Hatch

For complex data processing that requires non-serializable objects:

```groovy
@NonCPS
List<String> parseChangedFiles(String jsonPayload) {
    def slurper = new groovy.json.JsonSlurper()
    def data = slurper.parseText(jsonPayload)
    return data.files.collect { it.filename }
    // Returns a serializable List<String> back to the CPS script
}
```

### 🚫 FATAL RULE

> **A method annotated with `@NonCPS` can NEVER call Jenkins pipeline steps (`sh`, `echo`, `git`, `build`, `writeFile`, etc.)**
>
> If a `@NonCPS` method calls a pipeline step, the Jenkins interpreter will fail silently or produce anomalous behaviour.

```groovy
// ❌ FATAL — calling 'sh' from @NonCPS
@NonCPS
def processData() {
    def result = parseComplexJson(data)
    sh "echo ${result}"    // THIS WILL BREAK JENKINS
    return result
}

// ✅ CORRECT — @NonCPS only processes data, returns to CPS
@NonCPS
def processData(String data) {
    def slurper = new groovy.json.JsonSlurper()
    return slurper.parseText(data)    // Returns serializable data
}

// CPS pipeline code calls the step
def parsed = processData(rawJson)
sh "echo Processing ${parsed.size()} items"
```

### Memory Management

Prefer agent-side execution over controller-memory parsing:

```groovy
// ❌ BAD — loads entire file into controller memory
def content = readFile('large-report.json')
def parsed = new groovy.json.JsonSlurper().parseText(content)

// ✅ GOOD — processes on the agent node via jq
def result = sh(script: "jq '.items | length' large-report.json", returnStdout: true).trim()
```
