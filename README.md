# JNU Research SSD FTL

## Overview
This project focuses on the research and implementation of advanced Flash Translation Layers (FTLs) within the MQSim SSD simulator. The goal is to optimize SSD performance and endurance through novel mapping strategies.

## Key FTL Designs
The repository includes the design and implementation of the following FTL schemes:

1.  **GFTL (Group-level FTL)**: 
    - A baseline FTL using coarse-grained mapping.
    - Maps contiguous logical pages (Groups) to contiguous physical pages to reduce mapping table size.

2.  **CCFTL (Continuity Compressed FTL)**:
    - A baseline FTL utilizing run-length encoding.
    - Compresses sequential mappings into single entries, making it highly efficient for sequential workloads.

3.  **Compression FTL**:
    - A novel hybrid FTL design.
    - Uses **Delta Encoding** within fixed-size groups to efficiently handle semi-sequential patterns (e.g., small gaps or strides).

## Project Metadata
- **Code Editor**: ai-enterprise
- **Manager**: Lee Hyung-min
