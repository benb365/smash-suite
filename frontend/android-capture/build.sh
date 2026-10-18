#!/usr/bin/env bash
set -euo pipefail
task_root="$(cd "$(dirname "$0")" && pwd)"
variant="${1:-release}"
case "$variant" in
  release) task=assembleRelease ;;
  debug) task=assembleDebug ;;
  *) echo 'Usage: ./build.sh [release|debug]' >&2; exit 2 ;;
esac
if [[ -z "${JAVA_HOME:-}" && -d '/Applications/Android Studio.app/Contents/jbr/Contents/Home' ]]; then
  export JAVA_HOME='/Applications/Android Studio.app/Contents/jbr/Contents/Home'
fi
if [[ -z "${ANDROID_HOME:-}" && -d "$HOME/Library/Android/sdk" ]]; then
  export ANDROID_HOME="$HOME/Library/Android/sdk"
fi
export GRADLE_USER_HOME="$task_root/android/.gradle-home"
export ANDROID_USER_HOME="$task_root/android/.android-home"
(
  cd "$task_root/ui"
  npm ci --legacy-peer-deps --cache="$task_root/.runtime/npm-cache" --no-audit --no-fund
  npm run typecheck
)
(
  cd "$task_root/android"
  ./gradlew "$task" --no-daemon
)
mkdir -p "$task_root/dist"
cp "$task_root/android/app/build/outputs/apk/$variant/app-$variant.apk" \
  "$task_root/dist/smash-capture-0.1.0-arm64-$variant.apk"
echo "APK: $task_root/dist/smash-capture-0.1.0-arm64-$variant.apk"
