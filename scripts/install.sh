#!/usr/bin/env bash
# Install OpsCode — AI DevOps & Coding Agent.
#
# Usage:
#   curl -LsSf https://raw.githubusercontent.com/talkops-ai/opscode/main/scripts/install.sh | bash
#   curl -LsSf https://raw.githubusercontent.com/talkops-ai/opscode/main/scripts/install.sh | bash -s -- VERSION
#
# Install an exact pre-release version:
#   curl -LsSf https://raw.githubusercontent.com/talkops-ai/opscode/main/scripts/install.sh | OPSCODE_VERSION="0.1.0" bash
#   curl -LsSf https://raw.githubusercontent.com/talkops-ai/opscode/main/scripts/install.sh | bash -s -- 0.1.0
#
# Override uv's pre-release strategy when resolving the latest version:
#   curl -LsSf https://raw.githubusercontent.com/talkops-ai/opscode/main/scripts/install.sh | OPSCODE_PRERELEASE="allow" bash
#
# Options:
#   --help, -h     Show this help message and exit
#   --version, -v  Print installer version and exit
#
# By default, the installer uses uv's `allow` pre-release strategy so stable
# opscode releases that pin a pre-release dependency can resolve.
# OPSCODE_VERSION and an explicit OPSCODE_PRERELEASE are mutually
# exclusive: an exact pin already selects a single version, so setting both is an
# error.
#
# Already installed?
#   Safe to re-run. If a newer version exists, it asks before upgrading — or
#   upgrades on its own when run unattended (cron/CI/Docker). If you're already
#   on the latest, it does nothing. To skip the prompt:
#     - OPSCODE_YES=1                     accept the upgrade
#     - OPSCODE_VERSION / _PRERELEASE     install that exact selection
#     - OPSCODE_EXTRAS / _PYTHON          rebuild with those options
#
# Uninstall:
#   This script installs opscode as a uv tool. To remove it:
#     uv tool uninstall opscode
#   That removes the opscode and ops binaries and their isolated venv.
#   User config and data live separately in ~/.opscode (config.toml,
#   hooks.json, a global .env, and a .state/ dir holding sessions and saved
#   credentials) and are NOT removed by the uninstall above. To also wipe them:
#     rm -rf ~/.opscode
#   Optionally clear uv's shared tool cache (~/.cache/uv on Linux,
#   ~/Library/Caches/uv on macOS) — only if no other uv tools rely on it.
#
# Environment variables:
#   OPSCODE_EXTRAS — comma-separated pip extras, e.g. "ui",
#     "dev", or custom extra sets.
#   OPSCODE_VERSION — exact version to install, e.g. "0.1.0"
#     (mutually exclusive with OPSCODE_PRERELEASE)
#   OPSCODE_PRERELEASE — uv pre-release strategy applied when
#     resolving the latest version: disallow, allow, if-necessary, explicit,
#     or if-necessary-or-explicit (default: allow; explicitly setting it is
#     mutually exclusive with OPSCODE_VERSION)
#   OPSCODE_PYTHON — Python version to use (default: 3.12)
#   OPSCODE_YES — set to 1 to accept an available update without
#     prompting (assume "yes"). Exists so automated runs that still attach a
#     terminal (CI, wrapper scripts) update instead of stalling at the y/n
#     prompt.
#   OPSCODE_SKIP_OPTIONAL — set to 1 to skip optional tool checks
#   OPSCODE_RIPGREP_INSTALLER — how to provision ripgrep:
#     "managed" (default) or "system" package-manager install.
#     Set OPSCODE_OFFLINE=1 to skip managed downloads entirely.
#   OPSCODE_SKIP_XCODE_CHECK — set to 1 to bypass macOS Xcode Command Line Tools check
#   OPSCODE_NO_MODIFY_PATH — set to 1 to skip PATH setup entirely
#     (no profile edits, no symlinks).
#   OPSCODE_VERBOSE — set to 1 to show verbose logging and timing lines.
#   UV_BIN — path to uv binary (auto-detected if unset)

set -euo pipefail

INSTALLER_VERSION="0.1.0"
PACKAGE_NAME="talkops-opscode"
PRIMARY_BIN="opscode"
ALIAS_BIN="ops"

print_help() {
  cat <<'EOF'
Install OpsCode — AI DevOps & Coding Agent.

Usage:
  curl -LsSf https://raw.githubusercontent.com/talkops-ai/opscode/main/scripts/install.sh | bash
  curl -LsSf https://raw.githubusercontent.com/talkops-ai/opscode/main/scripts/install.sh | bash -s -- [options]
  curl -LsSf https://raw.githubusercontent.com/talkops-ai/opscode/main/scripts/install.sh | bash -s -- VERSION

Options:
  --help, -h       Show this help message and exit
  --version, -v    Print installer version and exit

Environment variables:
  OPSCODE_EXTRAS — comma-separated pip extras
  OPSCODE_VERSION — exact version to install, e.g. "0.1.0"
    (mutually exclusive with OPSCODE_PRERELEASE)
  OPSCODE_PRERELEASE — uv pre-release strategy applied when
    resolving latest version: disallow, allow, if-necessary, explicit,
    or if-necessary-or-explicit (default: allow)
  OPSCODE_PYTHON — Python version to use (default: 3.12)
  OPSCODE_YES — set to 1 to accept an available update without prompting
  OPSCODE_SKIP_OPTIONAL — set to 1 to skip optional tool checks
  OPSCODE_RIPGREP_INSTALLER — "managed" (default) or "system"
  OPSCODE_OFFLINE — set to 1 to skip external downloads
  OPSCODE_SKIP_XCODE_CHECK — set to 1 to bypass macOS Xcode check
  OPSCODE_NO_MODIFY_PATH — set to 1 to skip PATH setup entirely
  OPSCODE_VERBOSE — set to 1 to show verbose logs
  UV_BIN — path to uv binary (auto-detected if unset)

Documentation:
  https://github.com/talkops-ai/opscode
EOF
}

# ── Colors & Logging ─────────────────────────────────────────

if [ -t 1 ] && [ -z "${NO_COLOR:-}" ] && [ "${TERM:-dumb}" != "dumb" ]; then
  BOLD=$'\033[1m'
  DIM=$'\033[2m'
  RED=$'\033[0;31m'
  GREEN=$'\033[0;32m'
  YELLOW=$'\033[0;33m'
  BLUE=$'\033[0;34m'
  CYAN=$'\033[0;36m'
  NC=$'\033[0m'
else
  BOLD=""
  DIM=""
  RED=""
  GREEN=""
  YELLOW=""
  BLUE=""
  CYAN=""
  NC=""
fi

log_info() { printf "%s\n" "$*"; }
log_step() { printf "${BLUE}==>${NC} ${BOLD}%s${NC}\n" "$*"; }
log_success() { printf "${GREEN}✔${NC} %s\n" "$*"; }
log_warn() { printf "${YELLOW}Warning:${NC} %s\n" "$*" >&2; }
log_error() { printf "${RED}Error:${NC} %s\n" "$*" >&2; }

# ── Argument Handling ────────────────────────────────────────

POSITIONAL_VERSION=""

while [ $# -gt 0 ]; do
  case "$1" in
    --help|-h)
      print_help
      exit 0
      ;;
    --version|-v)
      printf "opscode-installer %s\n" "$INSTALLER_VERSION"
      exit 0
      ;;
    -*)
      log_error "Unknown option: $1"
      print_help >&2
      exit 1
      ;;
    *)
      if [ -z "$POSITIONAL_VERSION" ]; then
        POSITIONAL_VERSION="$1"
      else
        log_error "Unexpected extra argument: $1"
        print_help >&2
        exit 1
      fi
      ;;
  esac
  shift
done

# ── Temp File & Directory Tracking ───────────────────────────

TEMP_FILES=()
TEMP_DIRS=()

register_temp() { TEMP_FILES+=("$1"); }
register_temp_dir() { TEMP_DIRS+=("$1"); }

cleanup_temp_files() {
  for f in "${TEMP_FILES[@]:-}"; do
    [ -n "$f" ] && [ -f "$f" ] && rm -f "$f" 2>/dev/null || true
  done
}

cleanup_temp_dirs() {
  for d in "${TEMP_DIRS[@]:-}"; do
    [ -n "$d" ] && [ -d "$d" ] && rm -rf "$d" 2>/dev/null || true
  done
}

# ── Lock Management ──────────────────────────────────────────

LOCK_DIR=""

release_install_lock() {
  if [ -n "$LOCK_DIR" ] && [ -d "$LOCK_DIR" ]; then
    rm -rf "$LOCK_DIR" 2>/dev/null || true
    LOCK_DIR=""
  fi
}

cleanup_on_exit() {
  cleanup_temp_files
  cleanup_temp_dirs
  release_install_lock
}

trap cleanup_on_exit EXIT
trap 'cleanup_on_exit; exit 130' INT TERM

# ── OS & Platform Detection ──────────────────────────────────

OS="unknown"
ARCH="unknown"

detect_platform() {
  case "$(uname -s)" in
    Darwin*)
      OS="macos"
      ;;
    Linux*)
      OS="linux"
      ;;
    CYGWIN*|MINGW*|MSYS*)
      OS="windows"
      ;;
    *)
      OS="unknown"
      ;;
  esac

  case "$(uname -m)" in
    x86_64|amd64)
      ARCH="x86_64"
      ;;
    aarch64|arm64)
      ARCH="aarch64"
      ;;
    armv7l|armv6l)
      ARCH="arm"
      ;;
    *)
      ARCH="$(uname -m)"
      ;;
  esac
}

detect_platform

if [ "$OS" = "windows" ]; then
  log_warn "OpsCode is designed for Linux and macOS."
  log_warn "On Windows, running inside WSL (Windows Subsystem for Linux) is strongly recommended."
fi

# ── Xcode CLI tools check on macOS ───────────────────────────

if [ "$OS" = "macos" ] && [ "${OPSCODE_SKIP_XCODE_CHECK:-0}" != "1" ]; then
  if ! xcode-select -p >/dev/null 2>&1; then
    log_warn "macOS Command Line Tools not found."
    log_info "To install them, run: xcode-select --install"
    log_info "To bypass this check, set: OPSCODE_SKIP_XCODE_CHECK=1"
  fi
fi

# ── Configuration & Environment Setup ────────────────────────

EXTRAS="${OPSCODE_EXTRAS:-}"
VERSION="${OPSCODE_VERSION:-$POSITIONAL_VERSION}"
PRERELEASE_REQUESTED="${OPSCODE_PRERELEASE:-}"
PYTHON_VERSION="${OPSCODE_PYTHON:-3.12}"
SKIP_OPTIONAL="${OPSCODE_SKIP_OPTIONAL:-0}"
VERBOSE="${OPSCODE_VERBOSE:-0}"
ASSUME_YES="${OPSCODE_YES:-0}"
RIPGREP_INSTALLER="${OPSCODE_RIPGREP_INSTALLER:-managed}"

if [ -n "$POSITIONAL_VERSION" ] && [ -n "${OPSCODE_VERSION:-}" ]; then
  log_error "Do not combine a positional version with OPSCODE_VERSION."
  exit 1
fi

if [ -n "$VERSION" ] && [ -n "$PRERELEASE_REQUESTED" ]; then
  log_error "OPSCODE_VERSION and OPSCODE_PRERELEASE are mutually exclusive."
  exit 1
fi

# ── Acquire Install Lock ─────────────────────────────────────

acquire_install_lock() {
  local user_id
  user_id="$(id -u 2>/dev/null || echo 0)"
  LOCK_DIR="/tmp/opscode-install-${user_id}.lock"

  local attempts=0
  while ! mkdir "$LOCK_DIR" 2>/dev/null; do
    attempts=$((attempts + 1))
    if [ "$attempts" -ge 10 ]; then
      log_warn "Existing install lock detected at $LOCK_DIR. Breaking stale lock..."
      rm -rf "$LOCK_DIR" 2>/dev/null || true
      mkdir "$LOCK_DIR" 2>/dev/null || true
      break
    fi
    sleep 1
  done
}

acquire_install_lock

# ── Download Helpers ─────────────────────────────────────────

download_to_stdout() {
  local url="$1"
  if command -v curl >/dev/null 2>&1; then
    curl -LsSf "$url"
  elif command -v wget >/dev/null 2>&1; then
    wget -qO- "$url"
  else
    log_error "Neither curl nor wget is installed."
    exit 1
  fi
}

# ── UV Bootstrap & Resolution ────────────────────────────────

UV_BIN="${UV_BIN:-}"

resolve_uv_bin() {
  if [ -n "$UV_BIN" ] && [ -x "$UV_BIN" ]; then
    return 0
  fi

  if command -v uv >/dev/null 2>&1; then
    UV_BIN="$(command -v uv)"
    return 0
  fi

  local candidate_paths=(
    "${HOME}/.cargo/bin/uv"
    "${HOME}/.local/bin/uv"
    "/usr/local/bin/uv"
    "/opt/homebrew/bin/uv"
  )

  for p in "${candidate_paths[@]}"; do
    if [ -x "$p" ]; then
      UV_BIN="$p"
      return 0
    fi
  done

  return 1
}

install_uv() {
  log_step "Installing uv (fast Python package manager)..."
  local installer_script
  installer_script="$(mktemp /tmp/uv-install-XXXXXX.sh)"
  register_temp "$installer_script"

  if download_to_stdout "https://astral.sh/uv/install.sh" > "$installer_script"; then
    sh "$installer_script" >/dev/null 2>&1 || sh "$installer_script"
    if resolve_uv_bin; then
      log_success "uv installed successfully at ${UV_BIN}"
      return 0
    fi
  fi

  log_error "Failed to automatically install uv. Please install uv manually from https://docs.astral.sh/uv/getting-started/installation/"
  exit 1
}

if ! resolve_uv_bin; then
  install_uv
fi

# ── Resolve uv tool binary directory ─────────────────────────

TOOL_BIN_DIR=""

resolve_tool_bin_dir() {
  if [ -n "${UV_TOOL_BIN_DIR:-}" ]; then
    TOOL_BIN_DIR="${UV_TOOL_BIN_DIR}"
  elif [ -d "${HOME}/.local/bin" ]; then
    TOOL_BIN_DIR="${HOME}/.local/bin"
  elif [ -d "${HOME}/.cargo/bin" ]; then
    TOOL_BIN_DIR="${HOME}/.cargo/bin"
  else
    TOOL_BIN_DIR="${HOME}/.local/bin"
    mkdir -p "$TOOL_BIN_DIR" 2>/dev/null || true
  fi
}

resolve_tool_bin_dir

# ── User Prompting ───────────────────────────────────────────

prompt_yn() {
  local prompt_text="$1"
  local default_ans="${2:-y}"

  if [ "$ASSUME_YES" = "1" ] || [ "$ASSUME_YES" = "true" ]; then
    return 0
  fi

  if [ ! -t 0 ]; then
    # Unattended execution without stdin -> default to yes
    return 0
  fi

  local choice
  if [ "$default_ans" = "y" ]; then
    printf "%s [Y/n]: " "$prompt_text"
  else
    printf "%s [y/N]: " "$prompt_text"
  fi

  read -r choice || return 1
  choice="$(printf '%s' "$choice" | tr '[:upper:]' '[:lower:]')"

  if [ -z "$choice" ]; then
    choice="$default_ans"
  fi

  case "$choice" in
    y|yes) return 0 ;;
    *) return 1 ;;
  esac
}

# ── Check Existing Installation ──────────────────────────────

CURRENT_VERSION=""
for bin_candidate in "$PRIMARY_BIN" "$ALIAS_BIN"; do
  if command -v "$bin_candidate" >/dev/null 2>&1; then
    CURRENT_VERSION="$("$bin_candidate" --version 2>/dev/null | awk '{print $NF}' || true)"
    if [ -n "$CURRENT_VERSION" ]; then
      break
    fi
  fi
done

if [ -n "$CURRENT_VERSION" ]; then
  log_info "OpsCode ${CURRENT_VERSION} found on system."
fi

# ── Tool Installation / Upgrade ──────────────────────────────

SPEC_STR="${PACKAGE_NAME}"
if [ -n "$EXTRAS" ]; then
  SPEC_STR="${PACKAGE_NAME}[${EXTRAS}]"
fi

if [ -n "$VERSION" ]; then
  SPEC_STR="${SPEC_STR}==${VERSION}"
fi

PRERELEASE_FLAG="--prerelease=allow"
if [ -n "$PRERELEASE_REQUESTED" ]; then
  PRERELEASE_FLAG="--prerelease=${PRERELEASE_REQUESTED}"
fi

log_step "Installing ${SPEC_STR} via uv tool..."

INSTALL_CMD=(
  "$UV_BIN" "tool" "install"
  "--python" "$PYTHON_VERSION"
  "$PRERELEASE_FLAG"
  "--force"
  "--upgrade"
)

# If directory contains pyproject.toml and src/opscode (local repository), allow installing from directory
if [ -f "pyproject.toml" ] && [ -d "src/opscode" ] && [ -z "$VERSION" ]; then
  log_info "Detected local OpsCode repository. Installing in editable mode..."
  INSTALL_CMD+=("--editable" ".")
else
  INSTALL_CMD+=("$SPEC_STR")
fi

if [ "$VERBOSE" = "1" ]; then
  "${INSTALL_CMD[@]}"
else
  "${INSTALL_CMD[@]}" >/dev/null 2>&1 || "${INSTALL_CMD[@]}"
fi

log_success "OpsCode package installed."

# ── Alias & Symlink Setup ────────────────────────────────────

ensure_alias_symlink() {
  local source_bin="${TOOL_BIN_DIR}/${PRIMARY_BIN}"
  local target_alias="${TOOL_BIN_DIR}/${ALIAS_BIN}"

  if [ -x "$source_bin" ] && [ ! -e "$target_alias" ]; then
    ln -sf "$source_bin" "$target_alias" 2>/dev/null || true
  fi
}

ensure_alias_symlink

# ── PATH Configuration ───────────────────────────────────────

setup_shell_path() {
  if [ "${OPSCODE_NO_MODIFY_PATH:-0}" = "1" ]; then
    return 0
  fi

  # Check if TOOL_BIN_DIR is already in PATH
  case ":${PATH}:" in
    *:"${TOOL_BIN_DIR}":*)
      return 0
      ;;
  esac

  local user_shell
  user_shell="$(basename "${SHELL:-bash}")"
  local profile_file=""

  case "$user_shell" in
    zsh)
      profile_file="${ZDOTDIR:-$HOME}/.zshrc"
      ;;
    bash)
      if [ "$OS" = "macos" ]; then
        profile_file="${HOME}/.bash_profile"
        [ ! -f "$profile_file" ] && profile_file="${HOME}/.profile"
      else
        profile_file="${HOME}/.bashrc"
        [ ! -f "$profile_file" ] && profile_file="${HOME}/.profile"
      fi
      ;;
    fish)
      local fish_conf_dir="${HOME}/.config/fish/conf.d"
      mkdir -p "$fish_conf_dir" 2>/dev/null || true
      local fish_conf="${fish_conf_dir}/opscode.env.fish"
      if [ ! -f "$fish_conf" ]; then
        echo "fish_add_path -m ${TOOL_BIN_DIR}" > "$fish_conf"
      fi
      return 0
      ;;
    *)
      profile_file="${HOME}/.profile"
      ;;
  esac

  if [ -n "$profile_file" ] && [ -w "$(dirname "$profile_file")" ]; then
    local path_line="export PATH=\"${TOOL_BIN_DIR}:\$PATH\""
    if [ -f "$profile_file" ]; then
      if ! grep -Fq "${TOOL_BIN_DIR}" "$profile_file" 2>/dev/null; then
        printf "\n# Added by OpsCode installer\n%s\n" "$path_line" >> "$profile_file"
      fi
    else
      printf "# Added by OpsCode installer\n%s\n" "$path_line" > "$profile_file"
    fi
  fi
}

setup_shell_path

# ── Verification ─────────────────────────────────────────────

INSTALLED_PRIMARY=""
INSTALLED_ALIAS=""

for dir in "$TOOL_BIN_DIR" $(echo "$PATH" | tr ':' ' '); do
  if [ -x "${dir}/${PRIMARY_BIN}" ] && [ -z "$INSTALLED_PRIMARY" ]; then
    INSTALLED_PRIMARY="${dir}/${PRIMARY_BIN}"
  fi
  if [ -x "${dir}/${ALIAS_BIN}" ] && [ -z "$INSTALLED_ALIAS" ]; then
    INSTALLED_ALIAS="${dir}/${ALIAS_BIN}"
  fi
done

INSTALLED_VERSION=""
if [ -n "$INSTALLED_PRIMARY" ]; then
  INSTALLED_VERSION="$("$INSTALLED_PRIMARY" --version 2>/dev/null || echo "0.1.0")"
fi

# ── Summary & Next Steps ─────────────────────────────────────

printf "\n"
printf "${GREEN}✔${NC} ${BOLD}OpsCode ${INSTALLED_VERSION} installed successfully!${NC}\n\n"

case ":${PATH}:" in
  *:"${TOOL_BIN_DIR}":*)
    printf "Run ${BOLD}opscode${NC} (or alias ${BOLD}ops${NC}) to start an interactive session.\n"
    ;;
  *)
    printf "${YELLOW}Note:${NC} ${TOOL_BIN_DIR} is not in your current shell's PATH.\n"
    printf "To use OpsCode immediately in this terminal, run:\n"
    printf "  ${BOLD}export PATH=\"%s:\$PATH\"${NC}\n\n" "$TOOL_BIN_DIR"
    printf "Or restart your terminal session.\n"
    ;;
esac

printf "\nQuick Commands:\n"
printf "  ${CYAN}ops /auth${NC}        Configure model credentials\n"
printf "  ${CYAN}ops --help${NC}       Show all CLI flags and subcommands\n"
printf "  ${CYAN}ops -r${NC}           Resume your last conversation\n\n"
