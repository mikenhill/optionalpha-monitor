import json

# Read the test payload
with open('test_payload_20260623.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Convert to compact JSON (no extra whitespace)
compact_json = json.dumps(data, separators=(',', ':'))

# Escape for Postman format: " -> \" and add \n for readability
# Postman stores the body as a string with \n for newlines
postman_escaped = compact_json.replace('\n', '\\n').replace('"', '\\"')

# Save to file for reference
with open('postman_body_escaped.txt', 'w', encoding='utf-8') as f:
    f.write(postman_escaped)

print(f"Original length: {len(compact_json)}")
print(f"Escaped length: {len(postman_escaped)}")
print(f"First 300 chars: {postman_escaped[:300]}")
print("Saved to postman_body_escaped.txt")
