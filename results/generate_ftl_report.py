import csv
import math
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MQSIM_DIR = ROOT / "MQSim"
RESULTS_DIR = ROOT / "results"

MODELS = [
    ("DFTL", "ssdconfig.xml", "workload-dftl_scenario_1.xml"),
    ("GFTL", "ssdconfig-gftl.xml", "workload-gftl_scenario_1.xml"),
    ("CCFTL", "ssdconfig-ccftl.xml", "workload-ccftl_scenario_1.xml"),
    ("COMPRESSION", "ssdconfig-compression.xml", "workload-compression_scenario_1.xml"),
]

GROUP_SIZE = 16
GTD_ENTRY_BYTES = 8


def _to_int(node, tag):
    return int(node.findtext(tag).strip())


def _to_float(node, tag):
    return float(node.findtext(tag).strip())


def parse_config(config_path: Path):
    root = ET.parse(config_path).getroot()
    ssd = root.find("Device_Parameter_Set")
    if ssd is None:
        raise ValueError(f"Device_Parameter_Set missing in {config_path}")
    flash = ssd.find("Flash_Parameter_Set")
    if flash is None:
        raise ValueError(f"Flash_Parameter_Set missing in {config_path}")
    return {
        "cmt_capacity": _to_int(ssd, "CMT_Capacity"),
        "overprovisioning_ratio": _to_float(ssd, "Overprovisioning_Ratio"),
        "channel_count": _to_int(ssd, "Flash_Channel_Count"),
        "chip_per_channel": _to_int(ssd, "Chip_No_Per_Channel"),
        "die_per_chip": _to_int(flash, "Die_No_Per_Chip"),
        "plane_per_die": _to_int(flash, "Plane_No_Per_Die"),
        "block_per_plane": _to_int(flash, "Block_No_Per_Plane"),
        "page_per_block": _to_int(flash, "Page_No_Per_Block"),
        "page_capacity": _to_int(flash, "Page_Capacity"),
    }


def parse_result(result_path: Path):
    root = ET.parse(result_path).getroot()
    flow = root.find("Host").find("Host.IO_Flow")
    ftl = root.find("SSDDevice").find("SSDDevice.FTL")

    host = {
        "request_count": int(flow.findtext("Request_Count")),
        "read_request_count": int(flow.findtext("Read_Request_Count")),
        "write_request_count": int(flow.findtext("Write_Request_Count")),
        "device_response_time_us": int(flow.findtext("Device_Response_Time")),
        "end_to_end_delay_us": int(flow.findtext("End_to_End_Request_Delay")),
        "iops": float(flow.findtext("IOPS")),
        "bandwidth_Bps": float(flow.findtext("Bandwidth")),
        "write_payload_bytes_total": float(flow.findtext("Bytes_Transferred_Write")),
    }

    attrs = ftl.attrib
    ftl_stats = {
        "issued_flash_read_cmd": int(attrs["Issued_Flash_Read_CMD"]),
        "issued_flash_program_cmd": int(attrs["Issued_Flash_Program_CMD"])
        + int(attrs["Issued_Flash_Multiplane_Program_CMD"]),
        "issued_flash_read_cmd_for_mapping": int(attrs["Issued_Flash_Read_CMD_For_Mapping"]),
        "issued_flash_program_cmd_for_mapping": int(attrs["Issued_Flash_Program_CMD_For_Mapping"]),
        "cmt_hits": int(attrs["CMT_Hits"]),
        "cmt_misses": int(attrs["CMT_Misses"]),
        "total_cmt_queries": int(attrs["Total_CMT_Queries"]),
    }
    return host, ftl_stats


def estimate_dram_bytes(model, cfg):
    total_phys_pages = (
        cfg["channel_count"]
        * cfg["chip_per_channel"]
        * cfg["die_per_chip"]
        * cfg["plane_per_die"]
        * cfg["block_per_plane"]
        * cfg["page_per_block"]
    )
    total_logical_pages = int(total_phys_pages * (1.0 - cfg["overprovisioning_ratio"]))
    entries_per_translation_page = max(1, cfg["page_capacity"] // GTD_ENTRY_BYTES)

    if model == "GFTL":
        mapping_entries = math.ceil(total_logical_pages / GROUP_SIZE)
        cmt_dram_bytes = cfg["cmt_capacity"]
        ftl_metadata_bytes_est = mapping_entries * 4
    elif model == "CCFTL":
        mapping_entries = total_logical_pages
        cmt_dram_bytes = int(cfg["cmt_capacity"] * 0.70)
        ftl_metadata_bytes_est = int(cmt_dram_bytes * 0.10)
    elif model == "COMPRESSION":
        mapping_entries = total_logical_pages
        cmt_dram_bytes = int(cfg["cmt_capacity"] * 0.55)
        ftl_metadata_bytes_est = int(cmt_dram_bytes * 0.20)
    else:
        mapping_entries = total_logical_pages
        cmt_dram_bytes = cfg["cmt_capacity"]
        ftl_metadata_bytes_est = 0

    translation_pages = math.ceil(mapping_entries / entries_per_translation_page)
    gtd_dram_bytes_est = translation_pages * GTD_ENTRY_BYTES
    dram_total_bytes_est = cmt_dram_bytes + gtd_dram_bytes_est + ftl_metadata_bytes_est

    return {
        "page_capacity_bytes": cfg["page_capacity"],
        "cmt_dram_bytes": cmt_dram_bytes,
        "gtd_dram_bytes_est": gtd_dram_bytes_est,
        "ftl_metadata_bytes_est": ftl_metadata_bytes_est,
        "dram_total_bytes_est": dram_total_bytes_est,
    }


def build_rows():
    rows = []
    for model, cfg_name, out_name in MODELS:
        cfg = parse_config(MQSIM_DIR / cfg_name)
        host, ftl = parse_result(MQSIM_DIR / out_name)
        dram = estimate_dram_bytes(model, cfg)

        flash_program_bytes_data = ftl["issued_flash_program_cmd"] * cfg["page_capacity"]
        flash_program_bytes_total = (
            ftl["issued_flash_program_cmd"] + ftl["issued_flash_program_cmd_for_mapping"]
        ) * cfg["page_capacity"]

        write_payload = host["write_payload_bytes_total"]
        waf_data = flash_program_bytes_data / write_payload if write_payload else 0.0
        waf_total = flash_program_bytes_total / write_payload if write_payload else 0.0

        row = {
            "model": model,
            **host,
            **ftl,
            **dram,
            "flash_program_bytes_data": flash_program_bytes_data,
            "flash_program_bytes_total": flash_program_bytes_total,
            "waf_data": round(waf_data, 6),
            "waf_total": round(waf_total, 6),
        }
        rows.append(row)
    return rows


def write_csv(rows, out_csv: Path):
    headers = [
        "model",
        "request_count",
        "read_request_count",
        "write_request_count",
        "device_response_time_us",
        "end_to_end_delay_us",
        "iops",
        "bandwidth_Bps",
        "issued_flash_read_cmd",
        "issued_flash_program_cmd",
        "issued_flash_read_cmd_for_mapping",
        "issued_flash_program_cmd_for_mapping",
        "cmt_hits",
        "cmt_misses",
        "total_cmt_queries",
        "page_capacity_bytes",
        "write_payload_bytes_total",
        "flash_program_bytes_data",
        "flash_program_bytes_total",
        "waf_data",
        "waf_total",
        "cmt_dram_bytes",
        "gtd_dram_bytes_est",
        "ftl_metadata_bytes_est",
        "dram_total_bytes_est",
    ]
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def write_xlsx_and_graph(out_csv: Path):
    import pandas as pd
    import matplotlib.pyplot as plt

    df = pd.read_csv(out_csv)
    bar_width = 0.38
    color_map = {
        "DFTL": "#1b4f72",
        "GFTL": "#9a5b00",
        "CCFTL": "#1e6b35",
        "COMPRESSION": "#8e1b1b",
    }
    bar_colors = [color_map.get(model, "#7f7f7f") for model in df["model"]]

    for xlsx_name in ("ftl_summary_results.xlsx", "ftl_summary_results_updated.xlsx"):
        try:
            with pd.ExcelWriter(RESULTS_DIR / xlsx_name, engine="openpyxl") as writer:
                df.to_excel(writer, index=False, sheet_name="summary")
        except PermissionError:
            continue

    fig, axes = plt.subplots(2, 2, figsize=(11, 7))
    axes[0, 0].bar(df["model"], df["device_response_time_us"], width=bar_width, color=bar_colors)
    axes[0, 0].set_title("Device Response Time (us)")

    axes[0, 1].bar(df["model"], df["issued_flash_read_cmd_for_mapping"], width=bar_width, color=bar_colors)
    axes[0, 1].set_title("Mapping Flash Reads")

    axes[1, 0].bar(df["model"], df["waf_total"], width=bar_width, color=bar_colors)
    axes[1, 0].set_title("WAF (Total)")

    axes[1, 1].bar(df["model"], df["dram_total_bytes_est"], width=bar_width, color=bar_colors)
    axes[1, 1].set_title("Estimated DRAM Footprint (bytes)")

    for ax in axes.flat:
        ax.tick_params(axis="x", rotation=20)

    fig.tight_layout()
    for fig_name in ("ftl_comparison_overview.png", "ftl_comparison_overview_updated.png"):
        fig.savefig(RESULTS_DIR / fig_name, dpi=160)


def main():
    rows = build_rows()
    out_csv = RESULTS_DIR / "ftl_summary_results.csv"
    write_csv(rows, out_csv)
    write_xlsx_and_graph(out_csv)


if __name__ == "__main__":
    main()
