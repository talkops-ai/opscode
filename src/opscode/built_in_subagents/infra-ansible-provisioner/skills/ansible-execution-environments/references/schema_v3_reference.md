# Ansible Builder Version 3 Schema Reference

Complete specification for `execution-environment.yml` definition files complying with Ansible Builder v3.

## Schema Overview

Ansible Builder v3 structures the build process into multi-stage container builds.

```yaml
version: 3

images:
  base_image:
    name: quay.io/ansible/ansible-runner:latest
  builder_image:
    name: quay.io/ansible/ansible-builder:latest

build_arg_defaults:
  ANSIBLE_GALAXY_CLI_COLLECTION_OPTS: '--pre'
  EE_BASE_IMAGE: quay.io/ansible/ansible-runner:latest
  EE_BUILDER_IMAGE: quay.io/ansible/ansible-builder:latest

dependencies:
  galaxy: requirements.yml
  python: requirements.txt
  system: bindep.txt

options:
  package_manager_path: /usr/bin/microdnf

additional_build_steps:
  prepend_base:
    - RUN echo "Starting base prep"
  append_base:
    - COPY certs/corp-ca.crt /etc/pki/ca-trust/source/anchors/
    - RUN update-ca-trust
  prepend_galaxy:
    - ENV GALAXY_SERVER=https://galaxy.ansible.com
  append_galaxy: []
  prepend_builder: []
  append_builder: []
  prepend_final: []
  append_final:
    - RUN useradd -u 1000 -g 0 runner
    - USER 1000
```

---

## Field Specifications

### `version` (required)
- Must be integer `3` or string `'3'`.

### `images` (optional)
Specifies base images for final and build stages.

- `base_image.name`: Container base image for runtime execution (e.g., `quay.io/ansible/ansible-runner:latest`, `registry.redhat.io/ansible-automation-platform-24/ee-minimal-rhel8`).
- `builder_image.name`: Container image used during dependency compilation and collection assembly.

### `dependencies` (required / recommended)
Reference external dependency files or supply inline declarations:

```yaml
# File-based syntax
dependencies:
  galaxy: requirements.yml
  python: requirements.txt
  system: bindep.txt
```

```yaml
# Inline syntax
dependencies:
  galaxy:
    collections:
      - name: community.general
        version: ">=8.0.0"
  python:
    - boto3>=1.28.0
    - netaddr
  system:
    - python3-devel [compile]
    - libffi-devel [compile]
```

### `additional_build_steps` (optional)
Inject custom instructions into specific lifecycle hooks during Containerfile/Dockerfile generation:

| Hook Name | Lifecycle Point | Common Usage |
|-----------|-----------------|--------------|
| `prepend_base` | Beginning of base image setup | Proxy settings, global ENV variables |
| `append_base` | End of base image setup | Custom CA certificates, repo configurations |
| `prepend_galaxy` | Before Galaxy installation | Galaxy CLI flags, custom server URLs |
| `append_galaxy` | After Galaxy installation | Cleanup of collection cache/downloads |
| `prepend_builder` | Before Python/System builds | Compiler environment flags (`CFLAGS`, `LDFLAGS`) |
| `append_builder` | After Python/System builds | Builder stage artifact cleanup |
| `prepend_final` | Beginning of final stage | Base layer adjustments in final image |
| `append_final` | End of final stage | User management (`useradd`), file permission fixes |

### `options` (optional)
- `package_manager_path`: Executable path for package manager (`/usr/bin/dnf`, `/usr/bin/microdnf`, `/usr/bin/apt-get`).
- `container_init`: Container init settings.
