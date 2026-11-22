#!/bin/bash
# Install the locally downloaded, ad-hoc-signed Daedalus preview without
# changing system-wide Gatekeeper settings or opening Privacy & Security.
#
# Run from the extracted Daedalus-macos-preview.zip:
#   bash "Install Daedalus.command"
# Finder may also open this file in Terminal, depending on macOS policy.
set -euo pipefail

fail() {
  printf 'Daedalus installation failed: %s\n' "$*" >&2
  exit 1
}

if [[ "${1:-}" == "--help" ]]; then
  printf 'Usage: bash "Install Daedalus.command"\n'
  printf 'Installs into ~/Applications. No sudo or Security settings changes.\n'
  exit 0
fi
[[ $# -eq 0 ]] || fail "No arguments expected (use --help)."
[[ "$(uname -s)" == "Darwin" ]] || fail "This installer must run on macOS."

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
source_app="$script_dir/Daedalus.app"
[[ -d "$source_app" ]] || fail "Daedalus.app is missing beside this installer. Extract the inner preview ZIP first."
[[ -f "$source_app/Contents/MacOS/Daedalus" ]] || fail "Incomplete app bundle."

expected_id="io.github.itshak.daedalus"
read_bundle_id() {
  /usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$1/Contents/Info.plist" 2>/dev/null || true
}

[[ "$(read_bundle_id "$source_app")" == "$expected_id" ]] || fail "The app bundle identity is not Daedalus."
/usr/bin/codesign --verify --deep --strict "$source_app" \
  || fail "The downloaded app failed its code-signature integrity check. Do not install it."

# Install only for this user: no admin password or system security changes.
install_root="${DAEDALUS_INSTALL_ROOT:-$HOME/Applications}"
[[ "$install_root" == /* ]] || fail "Installation directory must be an absolute path."
mkdir -p -- "$install_root"
destination="$install_root/Daedalus.app"
[[ ! -L "$destination" ]] || fail "Refusing to replace a symlink at $destination."
if [[ -e "$destination" ]]; then
  [[ -d "$destination" && "$(read_bundle_id "$destination")" == "$expected_id" ]] \
    || fail "Refusing to replace an unrelated app at $destination."
fi

staging="$(mktemp -d "$install_root/.daedalus-install.XXXXXXXX")" \
  || fail "Cannot create a staging directory."
cleanup() {
  # Restore a previous copy if any install step failed after moving it aside.
  if [[ ! -e "$destination" && -d "$staging/previous.app" ]]; then
    mv -- "$staging/previous.app" "$destination" || true
  fi
  rm -rf -- "$staging"
}
trap cleanup EXIT

staged_app="$staging/Daedalus.app"
/usr/bin/ditto "$source_app" "$staged_app"

# macOS adds quarantine when an app is downloaded/extracted on the user's Mac.
# Removing it on the CI runner does not help. Remove ONLY the quarantine flag
# from this checked bundle on the target Mac (not from the Applications folder).
/usr/bin/xattr -dr com.apple.quarantine "$staged_app" 2>/dev/null || true
/usr/bin/xattr -lr "$staged_app" > "$staging/remaining-attributes.txt" \
  || fail "Unable to inspect extended attributes."
if /usr/bin/grep -q 'com.apple.quarantine:' "$staging/remaining-attributes.txt"; then
  fail "Quarantine is still present; check app permissions. No Gatekeeper setting was changed."
fi
/usr/bin/codesign --verify --deep --strict "$staged_app" \
  || fail "The installed copy failed its code-signature integrity check."

if [[ -d "$destination" ]]; then
  mv -- "$destination" "$staging/previous.app"
fi
if ! mv -- "$staged_app" "$destination"; then
  fail "Could not move Daedalus into $install_root."
fi

printf '\nInstalled Daedalus at: %s\n' "$destination"
printf 'Open Daedalus from Applications (or run: open "%s").\n' "$destination"
printf 'Note: this is an unsigned-by-Apple preview, not a notarized public release.\n'
