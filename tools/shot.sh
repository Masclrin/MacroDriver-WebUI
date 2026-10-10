#!/usr/bin/env bash
# 无头 Chrome 截图助手 —— 用于自检 WebUI 改动（不需要 pywebview / 不需要用户手动核对）
#
# 用法:
#   tools/shot.sh <url> <out.png> [width] [height] [virtual_time_budget_ms]
#
# 例:
#   tools/shot.sh "http://127.0.0.1:8793/index.html?p_tab=editor&p_panes=3" "E:/proj/artifacts/preview/editor.png"
#
# 说明:
#   - out 请用 Windows 风格路径（如 E:/... 或 C:/...），Chrome 才能正确写入。
#   - 静态预览支持 URL 预设参数：p_tab / p_panes / p_sidebar / p_topbar
#     （静态预览不调用后端，仅渲染 UI，便于稳定截图。）
set -euo pipefail

CHROME="${CHROME_BIN:-/c/Program Files/Google/Chrome/Application/chrome.exe}"
URL="${1:?用法: tools/shot.sh <url> <out.png> [w] [h] [budget_ms]}"
OUT="${2:?缺少输出路径}"
W="${3:-1500}"
H="${4:-950}"
BUDGET="${5:-4500}"
# 每次用**全新 profile**：否则 Chrome 会缓存 ES 模块，截到旧代码（很难发现）
BASE_PROFILE="${SHOT_PROFILE_BASE:-C:\\Users\\Administrator\\.workbuddy\\tmp}"
PROFILE="${SHOT_PROFILE:-${BASE_PROFILE}\\chrome-shot-$$}"

if [ ! -x "$CHROME" ]; then
  echo "找不到 Chrome: $CHROME（可用 CHROME_BIN 指定）" >&2
  exit 1
fi

mkdir -p "$(dirname "$OUT")"

"$CHROME" --headless=new --disable-gpu --no-first-run --no-default-browser-check \
  --user-data-dir="$PROFILE" \
  --window-size="${W},${H}" \
  --virtual-time-budget="${BUDGET}" \
  --screenshot="$OUT" "$URL" >/dev/null 2>&1

rm -rf "$(cygpath -u "$PROFILE" 2>/dev/null || echo "$PROFILE")" 2>/dev/null || true

echo "saved: $OUT"
