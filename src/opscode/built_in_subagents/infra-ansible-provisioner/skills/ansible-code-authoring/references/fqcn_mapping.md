# Ansible FQCN (Fully Qualified Collection Name) Mapping Reference

This document maps legacy short module names to their canonical Fully Qualified Collection Names (FQCN) per Ansible best practices.

## Table of Contents

- [Built-in Core Modules (`ansible.builtin`)](#built-in-core-modules-ansiblebuiltin)
- [POSIX System Modules (`ansible.posix`)](#posix-system-modules-ansibleposix)
- [Community General Modules (`community.general`)](#community-general-modules-communitygeneral)
- [Cloud Collections](#cloud-collections)

---

## Built-in Core Modules (`ansible.builtin`)

Always use `ansible.builtin.<module>` for standard system operations:

| Short Name | FQCN | Common Use Case |
|------------|------|-----------------|
| `command` | `ansible.builtin.command` | Run commands without shell environment |
| `shell` | `ansible.builtin.shell` | Run shell pipelines or subshells |
| `script` | `ansible.builtin.script` | Copy and execute local script on remote host |
| `raw` | `ansible.builtin.raw` | Low-level command execution without Python |
| `copy` | `ansible.builtin.copy` | Copy local file/content to remote host |
| `template` | `ansible.builtin.template` | Process Jinja2 template and deploy to remote |
| `file` | `ansible.builtin.file` | Manage file/directory permissions, ownership, symlinks |
| `fetch` | `ansible.builtin.fetch` | Fetch remote file to controller |
| `lineinfile` | `ansible.builtin.lineinfile` | Ensure single line exists or is replaced in a file |
| `replace` | `ansible.builtin.replace` | Replace all occurrences of regex pattern in file |
| `blockinfile` | `ansible.builtin.blockinfile` | Insert/update/remove a block of multi-line text |
| `package` | `ansible.builtin.package` | Generic OS package manager abstraction |
| `apt` | `ansible.builtin.apt` | Debian/Ubuntu APT package management |
| `yum` | `ansible.builtin.yum` | RHEL/CentOS YUM package management |
| `dnf` | `ansible.builtin.dnf` | RHEL/Fedora DNF package management |
| `service` | `ansible.builtin.service` | Generic OS service manager |
| `systemd` | `ansible.builtin.systemd` | Systemd service and unit management |
| `user` | `ansible.builtin.user` | Manage user accounts and SSH keys |
| `group` | `ansible.builtin.group` | Manage user groups |
| `git` | `ansible.builtin.git` | Clone or update git repositories |
| `stat` | `ansible.builtin.stat` | Retrieve file or file system status |
| `set_fact` | `ansible.builtin.set_fact` | Set custom host facts dynamically |
| `include_tasks` | `ansible.builtin.include_tasks` | Dynamic task file inclusion |
| `import_tasks` | `ansible.builtin.import_tasks` | Static task file import |
| `include_role` | `ansible.builtin.include_role` | Dynamic role inclusion |
| `import_role` | `ansible.builtin.import_role` | Static role import |
| `fail` | `ansible.builtin.fail` | Fail execution with custom message |
| `assert` | `ansible.builtin.assert` | Assert conditions and fail if false |
| `debug` | `ansible.builtin.debug` | Print variables or messages |
| `uri` | `ansible.builtin.uri` | Interact with HTTP/HTTPS REST APIs |
| `get_url` | `ansible.builtin.get_url` | Download files from HTTP/HTTPS/FTP |
| `unarchive` | `ansible.builtin.unarchive` | Unpack archives (.tar.gz, .zip) on remote |

---

## POSIX System Modules (`ansible.posix`)

| Short Name | FQCN | Common Use Case |
|------------|------|-----------------|
| `sysctl` | `ansible.posix.sysctl` | Manage kernel parameters |
| `firewalld` | `ansible.posix.firewalld` | Manage firewalld rules and zones |
| `mount` | `ansible.posix.mount` | Control active and configured mount points in fstab |
| `synchronize` | `ansible.posix.synchronize` | Wrapper around rsync for efficient file transfers |
| `authorized_key` | `ansible.posix.authorized_key` | Add or remove SSH authorized keys |
| `acl` | `ansible.posix.acl` | Set POSIX ACLs on files/directories |

---

## Community General Modules (`community.general`)

| Short Name | FQCN | Common Use Case |
|------------|------|-----------------|
| `ini_file` | `community.general.ini_file` | Manage settings in INI files |
| `htpasswd` | `community.general.htpasswd` | Manage htpasswd files for HTTP auth |
| `ufw` | `community.general.ufw` | Manage Uncomplicated Firewall (UFW) |
| `make` | `community.general.make` | Run targets in a Makefile |
| `modprobe` | `community.general.modprobe` | Load or unload kernel modules |
| `archive` | `community.general.archive` | Create compressed archives on remote host |

---

## Cloud Collections

| Provider | FQCN Prefix | Common Modules |
|----------|-------------|----------------|
| AWS | `amazon.aws.<module>` | `amazon.aws.ec2_instance`, `amazon.aws.s3_object`, `amazon.aws.aws_s3` |
| Azure | `azure.azcollection.<module>` | `azure.azcollection.azure_rm_virtualmachine` |
| GCP | `google.cloud.<module>` | `google.cloud.gcp_compute_instance` |
