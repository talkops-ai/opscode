---
name: jenkins-pipeline-generation
description: >
  Advanced Declarative Pipeline generation for Jenkins covering pipeline {} block
  architecture, containerised agent allocation (Docker, Kubernetes pod templates),
  matrix builds with axes/excludes, parallel stages with executor starvation
  prevention, pipeline options (disableConcurrentBuilds, parallelsAlwaysFailFast,
  timeout), post-execution conditions, and autonomous syntax validation via the
  Jenkins REST API pipeline-model-converter/validate endpoint with CSRF crumb
  tokens. Use when: (1) generating Jenkinsfile configurations with Declarative
  syntax, (2) allocating Docker or Kubernetes pod template agents, (3) implementing
  matrix builds with excludes for invalid combinations, (4) creating parallel
  stages while preventing executor starvation via agent none, (5) injecting
  pipeline options for concurrency control and fail-fast, or (6) validating
  Jenkinsfile syntax against a Jenkins server. Do NOT use for shared library
  authoring (use jenkins-shared-libraries), unit testing (use
  jenkins-pipeline-testing), or Job DSL (use jenkins-job-dsl-jcasc).
license: MIT
compatibility: designed for opscode
---

# Jenkins Declarative Pipeline Generation

Author production-grade Declarative Pipelines with containerised agents, matrix/parallel optimisation, executor starvation prevention, and autonomous syntax validation.

---

## Core Principles

1. **Declarative by Default**: Always use Declarative Pipeline syntax (`pipeline { }`) unless Scripted is explicitly requested.
2. **No `script {}` Crutch**: Leverage built-in Declarative directives — do not use `script { }` to compensate for poor pipeline design.
3. **Agent None at Top Level**: Prevent executor starvation by declaring `agent none` at the pipeline level and assigning agents per-stage.
4. **Validate Before Deliver**: Always validate generated Jenkinsfiles against the Jenkins REST API before returning to the user.

---

## Declarative Pipeline Architecture

### Structural Hierarchy

Every valid Declarative Pipeline must follow this strict block hierarchy:

```groovy
pipeline {
    agent none                    // Top-level agent declaration
    options { ... }               // Pipeline-wide options
    environment { ... }           // Global environment variables
    stages {
        stage('Build') {
            agent { ... }         // Stage-level agent
            steps { ... }
        }
        stage('Test') {
            parallel {            // Parallel sub-stages
                stage('Unit') { ... }
                stage('Integration') { ... }
            }
        }
    }
    post {                        // Post-execution conditions
        always { ... }
        success { ... }
        failure { ... }
    }
}
```

**Rules:**
- All code enclosed within `pipeline { }` — no code outside this block
- Statements on separate lines — **no semicolons**
- `stages` must contain at least one `stage`

---

## Agent Allocation

### Docker Agent

```groovy
stage('Build') {
    agent {
        docker {
            image 'maven:3.9-eclipse-temurin-21'
            args '-v $HOME/.m2:/root/.m2'
            registryUrl 'https://registry.example.com'
            registryCredentialsId 'docker-registry-creds'
        }
    }
    steps {
        sh 'mvn clean package'
    }
}
```

### Kubernetes Pod Template

```groovy
stage('Build & Test') {
    agent {
        kubernetes {
            yaml '''
apiVersion: v1
kind: Pod
spec:
  containers:
  - name: maven
    image: maven:3.9-eclipse-temurin-21
    command: ['sleep']
    args: ['infinity']
  - name: node
    image: node:20-alpine
    command: ['sleep']
    args: ['infinity']
'''
        }
    }
    steps {
        container('maven') {
            sh 'mvn clean package'
        }
        container('node') {
            sh 'npm test'
        }
    }
}
```

### Agent None (Top-Level)

```groovy
pipeline {
    agent none    // No executor provisioned on controller — stages define their own
    stages {
        stage('Build') {
            agent { docker { image 'maven:3.9' } }
            steps { sh 'mvn package' }
        }
    }
}
```

> **Critical**: `agent none` at the pipeline level prevents executor starvation in parallel/matrix builds. Always use this pattern when stages have different agent requirements.

---

## Matrix Builds

Run identical stages across a multi-dimensional configuration space:

```groovy
stage('Cross-Platform Tests') {
    matrix {
        axes {
            axis {
                name 'PLATFORM'
                values 'linux', 'windows', 'macos'
            }
            axis {
                name 'BROWSER'
                values 'chrome', 'firefox', 'safari'
            }
        }
        excludes {
            exclude {
                axis {
                    name 'PLATFORM'
                    values 'linux'
                }
                axis {
                    name 'BROWSER'
                    values 'safari'    // Safari doesn't run on Linux
                }
            }
        }
        agent {
            label "${PLATFORM}-agent"
        }
        stages {
            stage('Test') {
                steps {
                    sh "run-tests --browser=${BROWSER}"
                }
            }
        }
    }
}
```

### Matrix Components

| Component | Purpose |
|---|---|
| `axes` | Defines build dimensions (e.g., PLATFORM, BROWSER, JDK_VERSION) |
| `excludes` | Filters invalid/redundant combinations to save compute |
| Cell-level `agent` | Each matrix cell runs on a tailored agent |
| Cell-level `environment` | Per-cell environment variable injection |

---

## Parallel Stages & Executor Starvation Prevention

### The Problem

When a parent pipeline holds an executor while launching parallel child stages that also need executors, and the executor pool is limited — **permanent deadlock** occurs.

### The Solution

```groovy
pipeline {
    agent none    // ← Critical: do NOT hold an executor at the pipeline level
    options {
        parallelsAlwaysFailFast()    // Abort all branches if one fails
    }
    stages {
        stage('Parallel Tests') {
            parallel {
                stage('Unit Tests') {
                    agent { docker { image 'maven:3.9' } }
                    steps { sh 'mvn test' }
                }
                stage('Integration Tests') {
                    agent { docker { image 'maven:3.9' } }
                    steps { sh 'mvn verify -Pintegration' }
                }
            }
        }
    }
}
```

---

## Pipeline Options

Always inject these optimisation options:

```groovy
options {
    disableConcurrentBuilds(abortPrevious: true)  // Kill old builds on new push
    parallelsAlwaysFailFast()                      // Abort siblings on any failure
    timeout(time: 30, unit: 'MINUTES')             // Prevent hanging builds
    buildDiscarder(logRotator(numToKeepStr: '10')) // Retain only last 10 builds
}
```

| Option | Purpose |
|---|---|
| `disableConcurrentBuilds(abortPrevious: true)` | Terminates older builds when a new commit triggers — frees infrastructure |
| `parallelsAlwaysFailFast()` | Immediately aborts all parallel branches if one fails — reduces wasted compute |
| `timeout(time: N, unit: 'MINUTES')` | Hard limit on execution duration — prevents zombie builds |

---

## Autonomous Syntax Validation

Before delivering a Jenkinsfile, validate it against the Jenkins server's native parsing engine:

### Validation Flow

```bash
# Step 1: Fetch CSRF crumb token (if CSRF protection is enabled)
CRUMB=$(curl -s -u "$JENKINS_USER:$JENKINS_TOKEN" \
  "$JENKINS_URL/crumbIssuer/api/xml?xpath=concat(//crumbRequestField,\":\",//crumb)")

# Step 2: POST the Jenkinsfile for validation
curl -X POST \
  -H "$CRUMB" \
  -F "jenkinsfile=<Jenkinsfile" \
  "$JENKINS_URL/pipeline-model-converter/validate"
```

### Iterative Correction Loop

1. Generate the Jenkinsfile
2. POST to `pipeline-model-converter/validate`
3. If errors → parse line-level error messages → edit the file → re-validate
4. Repeat until the API returns `"Jenkinsfile successfully validated"`
5. Return the validated Jenkinsfile to the user
