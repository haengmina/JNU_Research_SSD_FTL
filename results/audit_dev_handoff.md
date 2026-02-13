# Audit Review and Dev Handoff

## Audit Scope
- Reviewed ftl_summary_results.csv consistency with model logic (DFTL/GFTL/CCFTL/COMPRESSION).
- Cross-checked with implemented behaviors in Address_Mapping_Unit_GFTL.cpp, Address_Mapping_Unit_CCFTL.cpp, Address_Mapping_Unit_Compression.cpp.

## Findings (After Dev Update)
1. **Translation-read fairness restored (fixed)**
   - DFTL: Issued_Flash_Read_CMD_For_Mapping=6882
   - GFTL: Issued_Flash_Read_CMD_For_Mapping=6633
   - CCFTL: Issued_Flash_Read_CMD_For_Mapping=6882
   - COMPRESSION: Issued_Flash_Read_CMD_For_Mapping=6882
   - Non-DFTL models now use the translation-page fetch path instead of bypassing it.

2. **DRAM accounting is now model-specific (fixed)**
   - CSV now reports per-model DRAM estimates using model-dependent assumptions:
     - GFTL group mapping/GTD scale-down
     - CCFTL run-length CMT estimate
     - COMPRESSION delta-group metadata estimate
   - `dram_total_bytes_est` is no longer identical across all rows.

3. **CCFTL vs COMPRESSION runtime separation remains limited (open)**
   - Main latency/throughput metrics are still close under current trace/config.
   - COMPRESSION now differs in cache behavior (`CMT_Misses` divergence), but stronger runtime gap may require heavier write-locality-sensitive workloads.

## Defect Severity
- D1: Non-equivalent mapping-read path across models (**Resolved**)
- D2: DRAM metric misrepresents model-specific memory usage (**Resolved**)
- D3: CCFTL vs COMPRESSION indistinguishable in outcome (**Partially Open, Medium**)

## Dev Team Action Items
1. **Re-enable fair translation path**
   - Ensure non-DFTL models also pay translation-page read/write costs when mapping entry is absent (or explicitly model equivalent metadata access cost).
2. **Model-specific DRAM accounting**
   - Report per-model DRAM footprint from actual structures:
     - GFTL group table + index
     - CCFTL run-length map
     - COMPRESSION delta groups + exception handling
3. **Differentiate COMPRESSION from CCFTL behavior**
   - Enforce delta-group update semantics and exception path impact in runtime stats.
4. **Regenerate CSV/graphs after fixes**
   - Re-run all 4 models and export updated ftl_summary_results.csv and graphs.

## Current Verdict
- CSV is now **valid for fair mapping-overhead/DRAM comparison claims** (D1/D2 fixed).
- Additional scenario tuning is recommended if stronger CCFTL vs COMPRESSION runtime separation is required.

## Secondary Comparison (Hot-Write Synthetic)
- Executed a write-locality-sensitive synthetic scenario for CCFTL and COMPRESSION:
  - `MQSim/workload-hotwrite-ccftl.xml`
  - `MQSim/workload-hotwrite-compression.xml`
- Output summary: `results/ccftl_vs_compression_hotwrite.csv`
- Observed result: end-to-end runtime metrics remained identical in this setup, while cache-accounting counters still diverge (`CMT_Misses` handling difference).
