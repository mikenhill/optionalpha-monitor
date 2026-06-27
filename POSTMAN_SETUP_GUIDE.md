# Postman Setup Guide for MVC Refactoring

This guide walks you through setting up Postman to test the new MVC controller implementations against the original Flask endpoints.

## Prerequisites

1. **Postman Desktop App** - Download from https://www.postman.com/downloads/
2. **Flask App Running** - The gex_viewer.py app must be running on port 5050

## Step 1: Start the Flask App

Open a terminal in the project directory and run:

```bash
python gex_viewer.py --port 5050
```

You should see output indicating the server is running on port 5050. Keep this terminal open.

## Step 2: Import the Postman Collection

1. Open Postman Desktop App
2. Click **Import** in the top-left corner
3. Navigate to: `g:\My Drive\Colab Notebooks\optionalpha-monitor\postman\`
4. Select `mvc-refactoring.postman_collection.json`
5. Click **Import**

You should now see a collection called "MVC Refactoring - Phase 2" in your Collections sidebar.

## Step 3: Configure the Collection

1. Click on "MVC Refactoring - Phase 2" in the sidebar
2. Click the **Variables** tab
3. Verify the base URL is set to `http://localhost:5050`

## Step 4: Run the Collection Tests

### Option A: Run All Tests

1. Click on "MVC Refactoring - Phase 2" collection
2. Click the **Run** button (arrow icon) or right-click → "Run collection"
3. A runner window will open showing all requests
4. Click **Run "MVC Refactoring - Phase 2"**
5. Review the test results - green checks indicate passing tests

### Option B: Run Individual Requests

1. Expand the collection to see folders: "Dates API" and "Snapshot API"
2. Click on any request (e.g., "Get All Dates (MVC)")
3. Click **Send**
4. View the response in the bottom panel
5. Check the **Test Results** tab to see automated assertions

## Step 5: Compare MVC vs Original

The collection includes paired requests for comparison:

### Dates API
- **Get All Dates (MVC)** - `/mvc/api/dates?test_mode=1`
- **Get All Dates (Original)** - `/api/dates`

Run both and compare:
- MVC returns: `{"success": true, "data": [...], "test_metadata": {...}}`
- Original returns: `[...]` (array directly)

The data array should be identical between both.

### Snapshot API
- **Get Snapshots (Times for Date) - MVC** - `/mvc/api/snapshots?date=2026-06-23&test_mode=1`
- **Get Snapshots (Times for Date) - Original** - `/api/snapshots?date=2026-06-23`

Run both and compare the `times` arrays.

- **Get Single Snapshot - MVC** - `/mvc/api/snapshot?date=2026-06-23&time=935&test_mode=1`
- **Get Snapshots Summary - MVC** - `/mvc/api/snapshots/summary?date=2026-06-23&test_mode=1`
- **Get Snapshots Summary - Original** - `/api/snapshots/summary?date=2026-06-23`

## Step 6: Understanding Test Mode

Add `?test_mode=1` to any MVC endpoint to see metadata:

```json
{
  "success": true,
  "data": [...],
  "test_metadata": {
    "timestamp": "2026-06-27T10:30:00.123456Z",
    "test_mode": true,
    "dao_used": "DatesController",
    "query_time_ms": 12.34,
    "row_count": 45
  }
}
```

**Test Metadata Fields:**
- `timestamp` - When the request was processed
- `test_mode` - Always true when test_mode=1 is set
- `dao_used` - Which controller/DAO handled the request
- `query_time_ms` - Query execution time in milliseconds
- `row_count` - Number of rows returned

## Step 7: Troubleshooting

### Connection Refused
- Ensure Flask app is running: `python gex_viewer.py --port 5050`
- Check that port 5050 is not in use by another process

### 404 Errors
- Verify the URL path is correct (should start with `/mvc/api/`)
- Check that the Flask app loaded the controller imports successfully

### Test Failures
- Check the **Test Results** tab for specific assertion failures
- Verify the database has data for the test date (2026-06-23)
- Try a different date if data is missing

### Import Errors
- Ensure you're importing the `.json` file, not the `.md` guide
- Verify the file path is correct

## Step 8: Customizing Tests

To test with different dates or parameters:

1. Click on a request
2. In the **Params** tab, change the `date` value
3. Click **Send** to test with new parameters
4. For dates with more data, try recent dates from the `/api/dates` response

## Step 9: Saving Results

To save test results for documentation:

1. After running the collection, click **Export Results** in the runner
2. Save as JSON for later review
3. Or take screenshots of individual request/response pairs

## Next Steps

Once Postman testing confirms MVC implementations match the original:

1. Update TODO list items for verification completion
2. Proceed to Phase 2 Step 4: Migrate remaining SnapshotDAO-dependent APIs
3. Eventually replace original routes with MVC versions after verification
