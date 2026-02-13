# Compression-based FTL Design Specification

## 1. Overview
This document specifies the design for three Flash Translation Layers (FTLs) to be implemented in MQSim:
1.  **GFTL (Group-level FTL)**: Baseline using coarse-grained mapping.
2.  **CCFTL (Continuity Compressed FTL)**: Baseline using run-length encoding.
3.  **Compression FTL**: A novel hybrid FTL using delta encoding and group mapping.

All FTLs inherit from `Address_Mapping_Unit_Base` (or `Address_Mapping_Unit_Page_Level` for code reuse).

## 2. GFTL (Group-level FTL)

### 2.1 Concept
Maps contiguous logical pages (Groups) to contiguous physical pages. Reduces mapping table size by a factor of `GROUP_SIZE` (e.g., 4, 8, 16).

### 2.2 Class Structure
- **Class**: `Address_Mapping_Unit_GFTL`
- **Inherits**: `Address_Mapping_Unit_Base`

### 2.3 Data Structures
```cpp
// In Address_Mapping_Unit_GFTL.h

struct GTD_Entry_GFTL { // Global Translation Directory
    MPPN_type MPPN; // Physical address of the translation page holding this group's mapping
    unsigned int TimeStamp;
};

struct Group_Mapping_Entry {
    PPA_type Start_PPA; // Physical Page Address of the FIRST page in the group
    bool Written;       // Whether the group is written
};
```

### 2.4 Address Translation
- **Read**:
  1. `Group_ID = LPN / GROUP_SIZE`
  2. `Offset = LPN % GROUP_SIZE`
  3. Lookup `Group_Mapping_Table[Group_ID]` -> `Start_PPA`
  4. `Target_PPA = Start_PPA + Offset`
- **Write**:
  1. New writes must be aligned to group boundaries or require Read-Modify-Write (RMW) of the whole group.
  2. Implementation Simplification: Assume writes are buffered until a full group is ready, or perform RMW.

## 3. CCFTL (Continuity Compressed FTL)

### 3.1 Concept
Compresses sequential mappings into a single entry: `{Start_LPN, Start_PPN, Count}`.
Ideally suited for sequential workloads.

### 3.2 Class Structure
- **Class**: `Address_Mapping_Unit_CCFTL`
- **Inherits**: `Address_Mapping_Unit_Page_Level`

### 3.3 Data Structures
```cpp
struct Compressed_Mapping_Entry {
    LPA_type Start_LPN;
    PPA_type Start_PPA;
    uint32_t Length; // Number of sequential pages
};

// In-Memory Structure
std::vector<Compressed_Mapping_Entry> CMT; // Sorted by Start_LPN for binary search
```

### 3.4 Address Translation
- **Read**:
  1. Binary search `CMT` for `Start_LPN <= LPN`.
  2. Check if `LPN < Start_LPN + Length`.
  3. If found: `Target_PPA = Start_PPA + (LPN - Start_LPN)`.
  4. If not found: Page not mapped.

## 4. Compression FTL (Novel Design)

### 4.1 Concept
Uses **Delta Encoding** within fixed-size groups to handle semi-sequential patterns (e.g., small gaps or strides) that break CCFTL's strict continuity.

### 4.2 Class Structure
- **Class**: `Address_Mapping_Unit_Compression`
- **Inherits**: `Address_Mapping_Unit_Page_Level`

### 4.3 Data Structures
```cpp
struct Delta_Compressed_Group {
    PPA_type Base_PPA;
    int16_t Deltas[GROUP_SIZE]; // Delta from Base_PPA. 0 means PPA = Base_PPA.
    // If Delta is too large for int16, fallback to full mapping or exception list.
};
```

### 4.4 Address Translation
- **Read**:
  1. `Group_ID = LPN / GROUP_SIZE`
  2. `Offset = LPN % GROUP_SIZE`
  3. Fetch `Delta_Compressed_Group`.
  4. `Target_PPA = Base_PPA + Deltas[Offset]`
- **Write**:
  1. Calculate `New_PPA`.
  2. `Delta = New_PPA - Base_PPA`.
  3. If `Delta` fits in `int16`: Update `Deltas[Offset]`.
  4. If not: Trigger re-base or split group (fallback).

## 5. Implementation Plan
1.  Modify `SSD_Defs.h` to add `FTL_Implementation_Type` enums.
2.  Modify `SSD_Device.cpp` to switch between FTLs based on `ssdconfig.xml`.
3.  Implement `Address_Mapping_Unit_GFTL` first (simplest).
4.  Implement `Address_Mapping_Unit_CCFTL` next.
5.  Implement `Address_Mapping_Unit_Compression` last.
