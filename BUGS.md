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
- **Status:** Not a bug - OptionAlpha API data limitation
- **Rationale:** OptionAlpha API doesn't have historical data for dates before 2026-06-28. Testing confirmed 2026-06-28 returns None from API, while 2026-06-30 returns data successfully.
- **Action:** No fix needed - this is a data availability limitation from OptionAlpha
- **Retest:** N/A (external API limitation)

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
