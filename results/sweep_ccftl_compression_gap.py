import csv
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
MQSIM_DIR = ROOT / "MQSim"
RESULTS_DIR = ROOT / "results"

WORKING_SET_VALUES = [20, 40, 60, 80, 100]
HOT_REGION_VALUES = [1, 5, 10, 20, 40]
QUEUE_DEPTH_VALUES = [8, 16, 32, 64]

REQ_COUNT = 30000
GAP_THRESHOLD_US = 1


def write_workload(path: Path, working_set: int, hot_region: int, queue_depth: int) -> None:
    content = f"""<?xml version=\"1.0\" encoding=\"us-ascii\"?>
<MQSim_IO_Scenarios>
    <IO_Scenario>
        <IO_Flow_Parameter_Set_Synthetic>
            <Priority_Class>HIGH</Priority_Class>
            <Device_Level_Data_Caching_Mode>WRITE_CACHE</Device_Level_Data_Caching_Mode>
            <Channel_IDs>0,1,2,3,4,5,6,7</Channel_IDs>
            <Chip_IDs>0,1,2,3</Chip_IDs>
            <Die_IDs>0,1</Die_IDs>
            <Plane_IDs>0,1</Plane_IDs>
            <Initial_Occupancy_Percentage>70</Initial_Occupancy_Percentage>
            <Working_Set_Percentage>{working_set}</Working_Set_Percentage>
            <Synthetic_Generator_Type>QUEUE_DEPTH</Synthetic_Generator_Type>
            <Read_Percentage>0</Read_Percentage>
            <Address_Distribution>RANDOM_HOTCOLD</Address_Distribution>
            <Percentage_of_Hot_Region>{hot_region}</Percentage_of_Hot_Region>
            <Generated_Aligned_Addresses>true</Generated_Aligned_Addresses>
            <Address_Alignment_Unit>16</Address_Alignment_Unit>
            <Request_Size_Distribution>FIXED</Request_Size_Distribution>
            <Average_Request_Size>8</Average_Request_Size>
            <Variance_Request_Size>0</Variance_Request_Size>
            <Seed>901</Seed>
            <Average_No_of_Reqs_in_Queue>{queue_depth}</Average_No_of_Reqs_in_Queue>
            <Intensity>32768</Intensity>
            <Stop_Time>0</Stop_Time>
            <Total_Requests_To_Generate>{REQ_COUNT}</Total_Requests_To_Generate>
        </IO_Flow_Parameter_Set_Synthetic>
    </IO_Scenario>
</MQSim_IO_Scenarios>
"""
    path.write_text(content, encoding="ascii")


def run_one(config_file: str, workload_file: str) -> dict:
    exe_path = str((MQSIM_DIR / "MQSim.exe").resolve())
    subprocess.run(
        [exe_path, "-i", config_file, "-w", workload_file],
        cwd=str(MQSIM_DIR),
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )
    result_xml = MQSIM_DIR / f"{Path(workload_file).stem}_scenario_1.xml"
    root = ET.parse(result_xml).getroot()
    flow = root.find("Host").find("Host.IO_Flow")
    return {
        "request_count": int(flow.findtext("Request_Count")),
        "device_response_time_us": int(flow.findtext("Device_Response_Time")),
        "iops": float(flow.findtext("IOPS")),
        "bandwidth_Bps": float(flow.findtext("Bandwidth")),
    }


def main() -> None:
    rows = []
    cc_workload = "workload-gap-ccftl.xml"
    cp_workload = "workload-gap-compression.xml"

    for ws in WORKING_SET_VALUES:
        for hr in HOT_REGION_VALUES:
            for qd in QUEUE_DEPTH_VALUES:
                write_workload(MQSIM_DIR / cc_workload, ws, hr, qd)
                write_workload(MQSIM_DIR / cp_workload, ws, hr, qd)

                cc = run_one("ssdconfig-ccftl.xml", cc_workload)
                cp = run_one("ssdconfig-compression.xml", cp_workload)

                resp_delta = cp["device_response_time_us"] - cc["device_response_time_us"]
                iops_delta = cp["iops"] - cc["iops"]
                iops_pct_delta = (iops_delta / cc["iops"] * 100.0) if cc["iops"] else 0.0

                rows.append(
                    {
                        "working_set_pct": ws,
                        "hot_region_pct": hr,
                        "queue_depth": qd,
                        "ccftl_response_us": cc["device_response_time_us"],
                        "compression_response_us": cp["device_response_time_us"],
                        "resp_delta_us": resp_delta,
                        "ccftl_iops": cc["iops"],
                        "compression_iops": cp["iops"],
                        "iops_delta": iops_delta,
                        "iops_pct_delta": iops_pct_delta,
                        "ccftl_bw_Bps": cc["bandwidth_Bps"],
                        "compression_bw_Bps": cp["bandwidth_Bps"],
                    }
                )

    sweep_csv = RESULTS_DIR / "ccftl_vs_compression_sweep.csv"
    with sweep_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    gap_rows = [r for r in rows if abs(r["resp_delta_us"]) >= GAP_THRESHOLD_US]
    gap_csv = RESULTS_DIR / "ccftl_vs_compression_gap_regions.csv"
    with gap_csv.open("w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "working_set_pct",
            "hot_region_pct",
            "queue_depth",
            "ccftl_response_us",
            "compression_response_us",
            "resp_delta_us",
            "ccftl_iops",
            "compression_iops",
            "iops_pct_delta",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in gap_rows:
            writer.writerow({k: row[k] for k in fieldnames})

    df = pd.DataFrame(rows)
    agg = (
        df.groupby(["working_set_pct", "hot_region_pct"], as_index=False)
        .agg(resp_delta_us=("resp_delta_us", "mean"), iops_pct_delta=("iops_pct_delta", "mean"))
    )
    pivot_resp = agg.pivot(index="working_set_pct", columns="hot_region_pct", values="resp_delta_us")
    pivot_iops = agg.pivot(index="working_set_pct", columns="hot_region_pct", values="iops_pct_delta")

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8))
    im1 = axes[0].imshow(pivot_resp.values, aspect="auto", cmap="coolwarm")
    axes[0].set_title("Resp Delta (COMPRESSION-CCFTL, us)")
    axes[0].set_xticks(range(len(pivot_resp.columns)))
    axes[0].set_xticklabels([str(v) for v in pivot_resp.columns])
    axes[0].set_yticks(range(len(pivot_resp.index)))
    axes[0].set_yticklabels([str(v) for v in pivot_resp.index])
    axes[0].set_xlabel("Hot Region %")
    axes[0].set_ylabel("Working Set %")
    fig.colorbar(im1, ax=axes[0], fraction=0.046, pad=0.04)

    im2 = axes[1].imshow(pivot_iops.values, aspect="auto", cmap="coolwarm")
    axes[1].set_title("IOPS Delta % (COMPRESSION-CCFTL)")
    axes[1].set_xticks(range(len(pivot_iops.columns)))
    axes[1].set_xticklabels([str(v) for v in pivot_iops.columns])
    axes[1].set_yticks(range(len(pivot_iops.index)))
    axes[1].set_yticklabels([str(v) for v in pivot_iops.index])
    axes[1].set_xlabel("Hot Region %")
    axes[1].set_ylabel("Working Set %")
    fig.colorbar(im2, ax=axes[1], fraction=0.046, pad=0.04)

    fig.tight_layout()
    fig.savefig(RESULTS_DIR / "ccftl_vs_compression_gap_heatmap.png", dpi=180)


if __name__ == "__main__":
    main()
