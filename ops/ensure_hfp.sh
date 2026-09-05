#!/usr/bin/env bash
# Switches the bonded CX 6.00BT headset off its power-on default (A2DP,
# sink-only) onto the headset-head-unit profile (HFP, codec mSBC).
#
# C1 capture and C4 playback are simultaneous (DR-017 Bar A item 1), and
# A2DP does not carry a live capture direction -- so this is not optional.
# Found and done by hand in thread 1.0.8; folded into an ops script here
# (thread 1.0.9, DR-024 addendum) so no session repeats it manually.
#
# Confirms via pw-dump that the resulting active node reports
# api.bluez5.codec == "msbc" before returning success. Exits non-zero and
# prints diagnostics on any failure -- callers (ops/run_d0.sh) should not
# proceed to a live run without this succeeding.
set -euo pipefail

DEVICE_NAME="CX 6.00BT"

device_id="$(wpctl status | grep -F "${DEVICE_NAME}" | grep -F "[bluez5]" | grep -oE '[0-9]+\.' | head -1 | tr -d '.')"

if [[ -z "${device_id}" ]]; then
    echo "ensure_hfp: ${DEVICE_NAME} not found in \`wpctl status\` (bluez5 device) -- is it connected?" >&2
    exit 1
fi

profile_index="$(pw-cli enum-params "${device_id}" 8 2>/dev/null | python3 -c '
import sys, re
text = sys.stdin.read()
blocks = text.split("  Object: size")
for block in blocks:
    if re.search(r"String \"headset-head-unit\"\n", block):
        m = re.search(r"Profile:index \(1\), flags \S+\n\s+Int (\d+)", block)
        if m:
            print(m.group(1))
            break
')"

if [[ -z "${profile_index}" ]]; then
    echo "ensure_hfp: no headset-head-unit profile advertised for device ${device_id} -- headset may not support HFP, or is not actually connected." >&2
    exit 1
fi

wpctl set-profile "${device_id}" "${profile_index}"

# wpctl set-profile is fire-and-forget; give WirePlumber a moment to apply
# it and spawn the new node before checking.
for _ in $(seq 1 10); do
    codec="$(pw-dump 2>/dev/null | python3 -c '
import json, sys
d = json.load(sys.stdin)
for o in d:
    props = o.get("info", {}).get("props", {})
    if props.get("api.bluez5.profile") == "headset-head-unit":
        print(props.get("api.bluez5.codec", ""))
        break
')"
    if [[ "${codec}" == "msbc" ]]; then
        echo "ensure_hfp: ${DEVICE_NAME} on headset-head-unit, codec=msbc confirmed." >&2
        exit 0
    fi
    sleep 0.5
done

echo "ensure_hfp: set-profile to headset-head-unit did not converge to codec=msbc (last seen: '${codec}')." >&2
exit 1
