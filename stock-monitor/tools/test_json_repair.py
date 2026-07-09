# test_json_repair.py
# Quick sanity check that json-repair handles the QQQ bear failure mode.
# The specific failure: model omits opening quote on a string field value.
# Run from C:\Users\Mack\ai-projects\stock-monitor
# Expected output: parsed dict with primary_argument populated.

from json_repair import repair_json

malformed = """{
  "persona": "bear",
  "ticker": "QQQ",
  "direction": "REDUCE",
  "confidence": 4,
  "primary_argument": QQQ's core thesis of software and platform AI monetization outpacing hardware is already fracturing.
  "supporting_evidence": ["evidence one", "evidence two"],
  "watch_items": ["watch one", "watch two"]
}"""

result = repair_json(malformed, return_objects=True)
print("Type:", type(result))
print("ticker:", result.get("ticker"))
print("primary_argument:", result.get("primary_argument", "")[:80])
print("supporting_evidence:", result.get("supporting_evidence"))
print()
print("PASS" if result.get("ticker") == "QQQ" and result.get("primary_argument") else "FAIL")
