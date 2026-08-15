---
name: jenkins-pipeline-testing
description: >
  Unit testing for Jenkins Shared Libraries using JenkinsPipelineUnit framework
  with Spock and JUnit. Covers test class construction extending BasePipelineTest
  and JenkinsPipelineSpecification, mocking Jenkins pipeline steps via
  helper.registerAllowedMethod() and helper.addShMock(), file system mocking via
  helper.addFileExistsMock() and helper.addReadFileMock(), pipeline status assertion
  (currentBuild.result), global variable testing via loadScript(), call stack
  verification via printCallStack(), and TDD workflow with Gradle/Maven test
  execution. Use when: (1) writing unit tests for vars/ global pipeline steps,
  (2) mocking sh, git, checkout, or fileExists steps, (3) testing pipeline outcome
  (FAILURE, UNSTABLE, SUCCESS) transitions, (4) loading and invoking vars/ scripts
  via loadScript/loadPipelineScriptForTest, (5) verifying call stacks with
  printCallStack(), or (6) running Gradle/Maven test suites to validate shared
  library code. Do NOT use for pipeline generation (use jenkins-pipeline-generation),
  shared library structure (use jenkins-shared-libraries), or Job DSL (use
  jenkins-job-dsl-jcasc).
license: MIT
compatibility: designed for opscode
---

# Jenkins Pipeline Unit Testing

Test every Shared Library component using JenkinsPipelineUnit + Spock before delivery. Code without tests is unacceptable.

---

## Core Principles

1. **Test-Driven Development**: Write the Spock specification first, then implement the shared library component.
2. **Mock Everything**: Jenkins steps don't exist outside the controller — every step must be explicitly mocked.
3. **Validate Outcomes**: Assert `currentBuild.result` transitions to verify error handling.
4. **Verify Call Stacks**: Use `printCallStack()` to confirm the exact sequence of Jenkins steps executed.

---

## Test Class Structure

### Spock Specification (Recommended)

```groovy
// test/groovy/StandardPipelineSpec.groovy
import com.lesfurets.jenkins.unit.declarative.DeclarativePipelineTest
import org.junit.Before
import org.junit.Test

class StandardPipelineSpec extends DeclarativePipelineTest {

    @Override
    @Before
    void setUp() throws Exception {
        super.setUp()
        // Register mocks for all Jenkins steps used by the pipeline
        helper.registerAllowedMethod('docker', [Map.class, Closure.class], null)
    }

    @Test
    void 'should run build stage successfully'() {
        // Load and execute the pipeline
        runScript('Jenkinsfile')

        // Verify success
        assertJobStatusSuccess()

        // Print the full call stack for debugging
        printCallStack()
    }
}
```

### JenkinsPipelineSpecification (Spock-native)

```groovy
// test/groovy/org/company/BuildDockerSpec.groovy
import com.lesfurets.jenkins.unit.global.lib.LibraryConfiguration
import com.lesfurets.jenkins.unit.BasePipelineTest
import spock.lang.Specification

class BuildDockerSpec extends Specification {

    def pipelineTest = new BasePipelineTest()

    def setup() {
        pipelineTest.setUp()
        // Mock the 'sh' step to return predefined output
        pipelineTest.helper.registerAllowedMethod(
            'sh', [Map.class], { Map params ->
                if (params.script.contains('docker build')) {
                    return 'Successfully built abc123'
                }
                return ''
            }
        )
    }

    def 'should build docker image with correct tag'() {
        when:
        def script = pipelineTest.loadScript('vars/buildDocker.groovy')
        script.call(image: 'myapp', tag: '1.0.0')

        then:
        pipelineTest.helper.callStack.find {
            it.toString().contains('docker build -t myapp:1.0.0')
        }
    }
}
```

---

## Mocking Jenkins Steps

### Shell Execution (`sh`)

```groovy
// Mock sh step — return stdout
helper.registerAllowedMethod('sh', [Map.class], { Map params ->
    if (params.returnStdout) {
        if (params.script.contains('git rev-parse')) {
            return 'abc123def456\n'
        }
    }
    if (params.returnStatus) {
        return 0    // Exit code
    }
    return null
})

// Shorthand: addShMock
helper.addShMock('git rev-parse HEAD', 'abc123def456', 0)
helper.addShMock('mvn test', '', 0)  // Exit code 0, no stdout
helper.addShMock('failing-command', 'error output', 1)  // Non-zero exit
```

### File System Operations

```groovy
// Mock fileExists
helper.addFileExistsMock('path/to/Dockerfile', true)
helper.addFileExistsMock('missing/file.txt', false)

// Mock readFile
helper.addReadFileMock('config/settings.json', '{"env": "production"}')
helper.addReadFileMock('VERSION', '2.1.0')
```

### Credentials

```groovy
// Mock withCredentials
helper.registerAllowedMethod('withCredentials', [List.class, Closure.class], { args, body ->
    body()
})

// Mock usernamePassword binding
helper.registerAllowedMethod('usernamePassword', [Map.class], { Map params ->
    binding.setVariable(params.usernameVariable, 'mock-user')
    binding.setVariable(params.passwordVariable, 'mock-pass')
})
```

### Other Common Mocks

```groovy
// Mock echo (allow all calls)
helper.registerAllowedMethod('echo', [String.class], null)

// Mock writeFile
helper.registerAllowedMethod('writeFile', [Map.class], null)

// Mock archiveArtifacts
helper.registerAllowedMethod('archiveArtifacts', [Map.class], null)

// Mock slackSend
helper.registerAllowedMethod('slackSend', [Map.class], null)

// Mock checkout (SCM)
helper.registerAllowedMethod('checkout', [Object.class], null)
```

---

## Testing Global Variables (vars/)

```groovy
@Test
void 'should execute standardPipeline with custom config'() {
    // Load the global variable script
    def script = loadScript('vars/standardPipeline.groovy')

    // Invoke the step with parameters
    script.call(
        buildImage: 'maven:3.9',
        buildCommand: 'mvn package',
        timeout: 20
    )

    // Verify the call stack contains expected steps
    printCallStack()

    // Assert specific steps were called
    assert helper.callStack.find { it.toString().contains('mvn package') }
}
```

---

## Asserting Pipeline Outcomes

```groovy
// Verify success
assertJobStatusSuccess()

// Verify failure handling
@Test
void 'should set build to FAILURE when tests fail'() {
    // Mock sh to return non-zero exit for test command
    helper.addShMock('mvn test', 'Test failures detected', 1)

    runScript('Jenkinsfile')

    // Assert the pipeline correctly set the failure status
    assertJobStatusFailure()
    // Or check directly:
    assert binding.getVariable('currentBuild').result == 'FAILURE'
}

// Verify unstable
@Test
void 'should mark build UNSTABLE when quality gate fails'() {
    helper.addShMock('quality-check', 'Warnings found', 0)
    binding.getVariable('currentBuild').result = 'UNSTABLE'

    runScript('Jenkinsfile')

    assertJobStatusUnstable()
}
```

---

## Call Stack Verification

```groovy
@Test
void 'should execute steps in correct order'() {
    runScript('Jenkinsfile')

    // Print full call stack for debugging
    printCallStack()

    // Verify specific step ordering
    def callStack = helper.callStack.collect { it.toString() }

    assert callStack.indexOf { it.contains('mvn clean') } <
           callStack.indexOf { it.contains('mvn test') }
}
```

---

## Build Configuration (Gradle)

```groovy
// build.gradle
plugins {
    id 'groovy'
}

dependencies {
    testImplementation 'com.lesfurets:jenkins-pipeline-unit:1.19'
    testImplementation 'org.spockframework:spock-core:2.4-groovy-4.0'
    testImplementation 'junit:junit:4.13.2'
}

sourceSets {
    main {
        groovy {
            srcDirs = ['src', 'vars']
        }
    }
    test {
        groovy {
            srcDirs = ['test/groovy']
        }
    }
}
```

### Execution

```bash
# Run all tests
./gradlew clean test

# Run specific test class
./gradlew test --tests "StandardPipelineSpec"
```

---

## TDD Workflow

1. **Write test** → define Spock spec with mocked steps and expected assertions
2. **Implement** → write the `vars/` or `src/` code
3. **Execute** → `./gradlew clean test`
4. **If mock missing** → register the missing method signature → re-run
5. **If assertion fails** → fix the implementation → re-run
6. **Repeat** until all tests pass with full coverage
