#!/usr/bin/env bash
# Builds ios/build/Cicada.app for the iOS simulator: the shared Mac sources (ios/shared-sources.txt)
# and ios/Sources in one module, bundled by hand like the Mac's scripts/build.sh (no .xcodeproj).
# Without RELEASE=1 it is a dev build: "Cicada Dev", bundle id com.wquguru.cicada.dev, cicada-dev:// commands.
set -euo pipefail
cd "$(dirname "$0")/../.."

SDK=iphonesimulator
TARGET=arm64-apple-ios26.0-simulator
APP=ios/build/Cicada.app
rm -rf "$APP"
mkdir -p "$APP"

files=()
while IFS= read -r line; do [[ -z $line || $line == \#* ]] || files+=("$line"); done < ios/shared-sources.txt
while IFS= read -r f; do files+=("$f"); done < <(find ios/Sources -name '*.swift' | sort)

SDKPATH=$(xcrun --show-sdk-path --sdk "$SDK")
# App Intents (Intents.swift) need the metadata Xcode extracts from the compiler's constant values:
# without Metadata.appintents in the bundle, Siri, Shortcuts, Control Center and the Live
# Activity's buttons don't know the intents. Each module is compiled whole (-wmo) to one
# .swiftconstvalues file, then appintentsmetadataprocessor writes the metadata into its bundle.
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
printf '%s' '["AppIntent","AppEntity","TransientAppEntity","AppEnum","EntityQuery","AppShortcutsProvider","AppShortcutProviding","DynamicOptionsProvider","LiveActivityIntent","ControlConfigurationIntent","WidgetConfigurationIntent","_IntentValueRepresentable","AppIntentsPackage"]' > "$WORK/protocols.json"
CONST=(-wmo -Xfrontend -const-gather-protocols-file -Xfrontend "$WORK/protocols.json")
intents_metadata() {   # <module> <bundle dir> <binary> <sources...>
  local module=$1 out=$2 binary=$3; shift 3
  printf '%s\n' "$@" > "$WORK/$module.sources"
  printf '%s\n' "$WORK/$module.swiftconstvalues" > "$WORK/$module.constvals"
  xcrun appintentsmetadataprocessor --toolchain-dir "$(dirname "$(dirname "$(dirname "$(xcrun -f swiftc)")")")" \
    --module-name "$module" --sdk-root "$SDKPATH" --xcode-version "$(xcodebuild -version | awk '/Build version/{print $3}')" \
    --platform-family iOS --deployment-target 26.0 --target-triple "$TARGET" --output "$out" \
    --source-file-list "$WORK/$module.sources" --swift-const-vals-list "$WORK/$module.constvals" \
    --binary-file "$binary" --deployment-aware-processing --no-app-shortcuts-localization --force --quiet-warnings >/dev/null 2>&1
  [[ -d "$out/Metadata.appintents" ]] || { echo "no App Intents metadata for $module"; exit 1; }
}

# STRINGS_OUT=<dir>: also write the UI text keys there (scripts/strings.py).
extra=()
[[ -n "${STRINGS_OUT:-}" ]] && extra=(-emit-localized-strings -emit-localized-strings-path "$STRINGS_OUT")
xcrun --sdk "$SDK" swiftc -O -swift-version 5 -parse-as-library -module-name Cicada \
  -target "$TARGET" -sdk "$SDKPATH" -D CICADA_IOS "${CONST[@]}" -emit-const-values-path "$WORK/Cicada.swiftconstvalues" \
  "${extra[@]+"${extra[@]}"}" "${files[@]}" -o "$APP/Cicada"
intents_metadata Cicada "$APP" "$APP/Cicada" "${files[@]}"

cp ios/Resources/Info.plist "$APP/Info.plist"
# UI text is the Mac's: the Chinese source is the key, the other languages translate it.
for d in Resources/*.lproj; do
  mkdir -p "$APP/$(basename "$d")"
  cp "$d/Localizable.strings" "$APP/$(basename "$d")/" 2>/dev/null || true
done
cp -R "$APP/zh-Hans.lproj" "$APP/zh-Hant.lproj"
cp Resources/sample/sample.m4a "$APP/"
# 说话人识别's voiceprint model, compiled on first use as on the Mac (SpeakerID.swift).
cp -R Resources/models/SpeakerEmbedding.mlpackage "$APP/"
# The logo on the 听会议室 card: the Mac's own icon renderer (Sources/CicadaIcon), not a fourth
# copy of the geometry. It is a host tool, built once.
ICON_TOOL=.build/release/CicadaIcon
[[ -x $ICON_TOOL ]] || swift build -c release --product CicadaIcon >/dev/null
ICONS=$(mktemp -d)
"$ICON_TOOL" "$ICONS/logo.iconset" >/dev/null
cp "$ICONS/logo.iconset/icon_128x128@2x.png" "$APP/logo.png"
rm -rf "$ICONS"

# The Live Activity (lock screen, Dynamic Island): a WidgetKit extension in PlugIns. The attributes
# type is compiled into both, so the app and the extension agree on it. Linked like Xcode links an
# app extension: entered through _NSExtensionMain, which runs the @main WidgetBundle on the main
# queue (the plain Swift entry point dies in libdispatch before the bundle loads).
APPEX="$APP/PlugIns/CicadaLive.appex"
mkdir -p "$APPEX"
LIVE=(ios/LiveActivity/*.swift ios/Sources/Cicada/ListenActivity.swift ios/Sources/Cicada/Intents.swift)
xcrun --sdk "$SDK" swiftc -O -swift-version 5 -parse-as-library -application-extension -module-name CicadaLive \
  -target "$TARGET" -sdk "$SDKPATH" -D CICADA_LIVE "${CONST[@]}" -emit-const-values-path "$WORK/CicadaLive.swiftconstvalues" \
  -Xlinker -e -Xlinker _NSExtensionMain \
  "${LIVE[@]}" -o "$APPEX/CicadaLive"
intents_metadata CicadaLive "$APPEX" "$APPEX/CicadaLive" "${LIVE[@]}"
cp ios/LiveActivity/Info.plist "$APPEX/Info.plist"
cp "$APP/logo.png" "$APPEX/"
for d in "$APP"/*.lproj; do cp -R "$d" "$APPEX/"; done

PLIST="$APP/Info.plist"
/usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString $(tr -d '[:space:]' < VERSION)" "$PLIST"
if [[ "${RELEASE:-}" != 1 ]]; then
  STAMP="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo local) @ $(git rev-parse --short HEAD 2>/dev/null || echo none)"
  /usr/libexec/PlistBuddy -c "Set :CFBundleIdentifier com.wquguru.cicada.dev" \
    -c "Set :CFBundleName Cicada Dev" -c "Set :CFBundleDisplayName Cicada Dev" \
    -c "Add :LiveSubsDev string $STAMP" \
    -c "Set :BGTaskSchedulerPermittedIdentifiers:0 com.wquguru.cicada.dev.import" \
    -c "Add :CFBundleURLTypes array" -c "Add :CFBundleURLTypes:0 dict" \
    -c "Add :CFBundleURLTypes:0:CFBundleURLSchemes array" -c "Add :CFBundleURLTypes:0:CFBundleURLSchemes:0 string cicada-dev" \
    "$PLIST"
  /usr/libexec/PlistBuddy -c "Set :CFBundleIdentifier com.wquguru.cicada.dev.live" "$APPEX/Info.plist"
fi
/usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString $(tr -d '[:space:]' < VERSION)" "$APPEX/Info.plist"
codesign --force --sign - "$APPEX" 2>/dev/null
codesign --force --sign - "$APP" 2>/dev/null
echo "Built $APP ($(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$PLIST"))"
