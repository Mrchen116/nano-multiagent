#!/bin/bash
set -euo pipefail
IOS_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export DEVELOPER_DIR="${DEVELOPER_DIR:-/Applications/Xcode.app/Contents/Developer}"
MODE="${1:-build}"
BUILD_ROOT="${NANO_IOS_BUILD_ROOT:-/tmp/nano-ios-build}"
case "$MODE" in
  build)
    xcodebuild -project "$IOS_ROOT/NanoIM.xcodeproj" -scheme NanoIM -destination 'generic/platform=iOS Simulator' -derivedDataPath "$BUILD_ROOT" build
    ;;
  test)
    DEVICE_ID="${NANO_IOS_SIMULATOR_ID:?Set NANO_IOS_SIMULATOR_ID to an available iPhone simulator UDID}"
    xcodebuild -project "$IOS_ROOT/NanoIM.xcodeproj" -scheme NanoIM -destination "platform=iOS Simulator,id=$DEVICE_ID" -derivedDataPath "$BUILD_ROOT" test
    ;;
  archive)
    xcodebuild -project "$IOS_ROOT/NanoIM.xcodeproj" -scheme NanoIM -destination 'generic/platform=iOS' -configuration Release -archivePath "$BUILD_ROOT/NanoIM.xcarchive" -derivedDataPath "$BUILD_ROOT" CODE_SIGNING_ALLOWED=NO archive
    STAGE="$(mktemp -d "$BUILD_ROOT/ipa.XXXXXX")"
    trap 'rm -rf "$STAGE"' EXIT
    mkdir -p "$STAGE/Payload"
    ditto "$BUILD_ROOT/NanoIM.xcarchive/Products/Applications/NanoIM.app" "$STAGE/Payload/NanoIM.app"
    ditto -c -k --keepParent "$STAGE/Payload" "$BUILD_ROOT/NanoIM-unsigned.ipa"
    /usr/bin/file "$STAGE/Payload/NanoIM.app/NanoIM"
    printf 'Unsigned IPA for AltStore re-signing: %s\n' "$BUILD_ROOT/NanoIM-unsigned.ipa"
    ;;
  *) printf 'Usage: %s [build|test|archive]\n' "$0" >&2; exit 2 ;;
esac
