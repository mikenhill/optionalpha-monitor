import json

# Read the historical payload (10:00 from 2026-06-23)
with open('test_payload_20260623_1000.json', 'r', encoding='utf-8') as f:
    historical_data = json.load(f)
    # Convert to formatted JSON for Postman (with newlines for readability)
    historical_payload = json.dumps(historical_data, indent=2)

# Read the test/gex.json for live payload
with open('test/gex.json', 'r', encoding='utf-8') as f:
    live_data = json.load(f)
    # Extract the actual data from the OptionAlpha response format
    live_payload = live_data[0]['data'] if isinstance(live_data, list) and len(live_data) > 0 else live_data
    # Convert to formatted JSON for Postman
    live_payload_str = json.dumps(live_payload, indent=2)

# Read the Postman collection
with open('postman/mvc-refactoring.postman_collection.json', 'r', encoding='utf-8') as f:
    collection = json.load(f)

# Find and update the requests
for item in collection['item']:
    if item['name'] == 'Local APIs':
        for sub_item in item['item']:
            if sub_item['name'] in ['Upsert Historical Snapshot', 'Upsert Historical Snapshot (Test Mode)']:
                sub_item['request']['body']['raw'] = historical_payload
                print(f"Updated: {sub_item['name']}")
            elif sub_item['name'] in ['Upsert Live Snapshot', 'Upsert Live Snapshot (Test Mode)']:
                sub_item['request']['body']['raw'] = live_payload_str
                # Add required date and time query parameters
                if 'query' not in sub_item['request']['url']:
                    sub_item['request']['url']['query'] = []
                # Check if date and time params exist, if not add them
                query_params = sub_item['request']['url']['query']
                has_date = any(p['key'] == 'date' for p in query_params)
                has_time = any(p['key'] == 'time' for p in query_params)
                if not has_date:
                    query_params.append({'key': 'date', 'value': '2026-06-23', 'description': 'Required: YYYY-MM-DD format'})
                if not has_time:
                    query_params.append({'key': 'time', 'value': '1000', 'description': 'Required: HHMM format'})
                # Update the raw URL to include the params
                sub_item['request']['url']['raw'] = f"http://localhost:5050/mvc/api/snapshot/live?date=2026-06-23&time=1000"
                if sub_item['name'] == 'Upsert Live Snapshot (Test Mode)':
                    sub_item['request']['url']['raw'] += "&test=1"
                print(f"Updated: {sub_item['name']} with date/time params")

# Save the updated collection
with open('postman/mvc-refactoring.postman_collection.json', 'w', encoding='utf-8') as f:
    json.dump(collection, f, indent=2)

print("Postman collection updated successfully with 10:00 payload from 2026-06-23")
