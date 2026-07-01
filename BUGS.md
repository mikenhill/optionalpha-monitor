# Bug List

## 2026-07-01

### Issue: Pre-market records don't have HMM labels
- **Description:** Live records added for pre-market times (ntime < 935) do not have Regime (hmm_label) set
- **Date:** 2026-07-01
- **Example:** 2026-07-01 @ 0751
- **Status:** Intentional behavior (by design)
- **Rationale:** HMM labels are only calculated for RTH snapshots (ntime >= 935). This matches the live capture function behavior.
- **Action:** No action required unless pre-market HMM labels are desired
- **Retest:** N/A (intentional behavior)

### Issue: Historical sync fails for older dates with "'str' object has no attribute 'get'"
- **Description:** Syncing historical records for dates before 2026-06-28 fails with error "'str' object has no attribute 'get'"
- **Date:** 2026-07-01
- **Examples:** 2026-06-28, 2026-06-19, 2026-06-14, 2026-06-13, 2026-06-07, 2026-06-06
- **Status:** Not a bug - Weekend dates have no trading data
- **Rationale:** Testing confirmed 2026-06-28 is a Sunday (weekend) with no trading data. OptionAlpha API returns responses without data field for weekend dates. Other dates work correctly (e.g., 2026-02-18@955 returns 225 data points, 2026-06-30@935 returns 644 data points). Not a CAPTCHA issue - CAPTCHA detection added and confirmed not triggering.
- **Action:** Removed 1 record for 2026-06-28 from snapshot table. Consider adding weekend date validation to sync function to prevent future attempts.
- **Retest:** N/A (weekend dates have no trading data)

### Issue: GEX Admin tab navigation loses ML tab state
- **Description:** When navigating to GEX Admin tab, the ML tab state is lost
- **Date:** 2026-07-01
- **Status:** Bug - needs investigation
- **Rationale:** Tab navigation state not preserved when switching between admin pages
- **Action:** Investigate tab navigation logic in gex_admin.html
- **Retest:** After fix

### Issue: PCA variance chart lacks explanation of PC1-PC27
- **Description:** The "Variance Explained by Principal Component" chart shows PC1 through PC27 without explanation
- **Date:** 2026-07-01
- **Status:** Feature request - needs enhancement
- **Rationale:** Users need to understand what PC1-PC27 represent (principal components from PCA)
- **Action:** Add tooltip or explanatory text to the PCA variance chart
- **Retest:** After enhancement
