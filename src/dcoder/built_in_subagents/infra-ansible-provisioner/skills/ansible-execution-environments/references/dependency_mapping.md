# Dependency Mapping Guide

Detailed guidance on mapping Ansible Galaxy collections, Python packages, and system dependencies into execution environments.

## 1. Galaxy Collections (`requirements.yml`)

Collections specify the Ansible content available inside the execution environment.

### Syntax Example

```yaml
---
collections:
  - name: ansible.posix
    version: ">=1.5.0"

  - name: community.general
    version: ">=8.0.0"

  - name: amazon.aws
    version: "7.1.0"

  - name: https://github.com/my-org/my_custom_collection.git
    type: git
    version: main
```

### Best Practices
- Always specify version constraints to ensure reproducible builds.
- Put collections in `requirements.yml` referenced under `dependencies.galaxy` in `execution-environment.yml`.

---

## 2. Python Dependencies (`requirements.txt`)

Python packages required by modules inside the installed collections or custom plugins.

### Syntax Example

```text
boto3>=1.28.0
botocore>=1.31.0
netaddr>=0.8.0
paramiko>=3.0.0
psutil
pewp
```

### Best Practices
- Pin major or minor versions to avoid breaking changes during rebuilds.
- Ansible Builder aggregates Python requirements from installed Galaxy collections automatically alongside `requirements.txt`.

---

## 3. System Packages (`bindep.txt`)

System binaries, C libraries, and header packages required at build-time or runtime across various OS distributions.

### Syntax Example

```text
# RPM/DEB system packages with bindep profiles
gcc [compile]
python3-devel [compile]
libffi-devel [compile]
openssl-devel [compile]
openldap-devel [compile]
krb5-devel [compile]

git [platform:rpm platform:dpkg]
rsync [platform:rpm platform:dpkg]
openssh-clients [platform:rpm]
openssh-client [platform:dpkg]
```

### Profile Indicators
- `[compile]`: Installed in the builder stage only (used for compiling wheels/binaries), omitted from final runtime image.
- `[platform:rpm]`: Targets RPM-based distributions (RHEL, Fedora, CentOS).
- `[platform:dpkg]`: Targets Debian/Ubuntu distributions.
