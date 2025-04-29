# This script generates a PDF report for Kubernetes Pod Disruption Budgets (PDBs) in a specified namespace.

# ---------------------- Imports ---------------------- #
import pandas as pd
from fpdf.enums import XPos, YPos
from datetime import datetime
import typer
import os

# Import custom modules
import kubecase.utils as utils
from kubecase.base_report import BaseReport

# ---------------------- Constants ---------------------- #
VERSION = "1.0.0"
           
# ---------------------- Helper Functions ---------------------- # 
def get_namespace_coverage(pods_list, pdbs_list):
    """Returns total pods, covered pods, uncovered pods."""
    covered_pods = []
    uncovered_pods = []

    # Build PDB selectors
    pdb_selectors = []
    for pdb in pdbs_list:
        selector = pdb.get("spec", {}).get("selector", {}).get("matchLabels", {})
        if selector:
            pdb_selectors.append(selector)

    # For each pod, check if it matches any PDB selector
    for pod in pods_list:
        pod_labels = pod["metadata"].get("labels", {})
        matched = False

        for selector in pdb_selectors:
            if all(pod_labels.get(k) == v for k, v in selector.items()):
                matched = True
                break
        
        if matched:
            covered_pods.append(pod)
        else:
            uncovered_pods.append(pod)

    total_pods = len(pods_list)
    covered_count = len(covered_pods)
    coverage_percentage = (covered_count / total_pods) * 100 if total_pods > 0 else 0

    return {
        "total_pods": total_pods,
        "covered_pods": covered_pods,
        "uncovered_pods": uncovered_pods,
        "coverage_percentage": round(coverage_percentage, 0)
    }

# ------------------------- PDF Class ------------------------- #
class PDBReport(BaseReport):
    """
    PDB-specific extensions for the PDF report.
    """
    def add_section_1_table(self, dataframe, col_widths=None, title=None):
        if title:
            self.set_font("Dejavu", "B", 12)
            self.cell(0, 10, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            self.ln(2)

        self.set_font("Dejavu", "B", 10)

        # Setup default column widths if not provided
        if col_widths is None:
            col_widths = [40] * len(dataframe.columns)

        # Draw header row
        for i, col in enumerate(dataframe.columns):
            self.set_fill_color(244, 246, 250)  # Light gray background
            self.cell(col_widths[i], 10, col, border=1, fill=True, align='C')
        self.ln()
        self.set_font("Dejavu", "", 10)

        # Draw each data row
        for _, row in dataframe.iterrows():
            self.set_fill_color(255, 255, 255)  # Default white background
            text_color = (0, 0, 0)

            # --- Special Highlight Logic for Coverage (%) ---
            if "Coverage (%)" in dataframe.columns:
                try:
                    coverage = float(row["Coverage (%)"])
                    if coverage >= 90:
                        self.set_fill_color(255, 255, 255)  # Healthy
                        text_color = (0, 0, 0)
                    elif 80 <= coverage < 90:
                        self.set_fill_color(255, 255, 153)  # Caution Yellow
                        text_color = (0, 0, 0)
                    else:
                        self.set_fill_color(255, 0, 0)  # Critical Red
                        text_color = (255, 255, 255)
                except (ValueError, KeyError, TypeError):
                    pass  # If can't parse, keep default colors

            self.set_text_color(*text_color)

            # Draw each cell
            for i, col in enumerate(dataframe.columns):
                value = str(row[col])
                cell_width = col_widths[i]
                self.cell(cell_width, 10, value, border=1, align='C', fill=True)

            self.ln(10)

        # Reset text color and line after table
        self.ln(3)
        self.set_text_color(0, 0, 0)

    def intro_page(self):
        self.add_page()
        self.start_section(name="Purpose", level=0)
        self.section_title("Purpose")
        self.set_font("DejaVu", '', 12)
        self.write_paragraph(
            "This report provides a detailed analysis of Pod Disruption Budgets (PDBs) within a Kubernetes namespace. "
            "Its purpose is to help platform engineers, SREs, and application teams understand which workloads are protected "
            "from voluntary disruptions (like node drains or upgrades), and which may be vulnerable to unintended downtime."
        )

        self.section_title("What This Report Covers")
        self.write_paragraph("Section 1: Namespace PDB Coverage", font_style='B')
        self.write_paragraph(
            "Analyzes how many pods in the namespace are covered by a PDB. Shows the percentage of workloads protected, "
            "and lists any uncovered pods that may block rolling upgrades or cause app outages.\n"
        )

        self.write_paragraph("Section 2: PDB Breakdown by Controller", font_style='B')
        self.write_paragraph(
            "Groups PDBs by owner (Deployment, StatefulSet, etc.), showing minAvailable or maxUnavailable settings, "
            "affected pod counts, and any mismatch or misalignment with real workloads.\n"
        )

        self.write_paragraph("Section 3: PDB Details & Flags", font_style='B')
        self.write_paragraph(
            "WORK IN PROGRESS: Shows detailed PDB configuration including selector labels, disruption allowed, current healthy pods, "
            "expected counts, and flag rows for PDBs that are overly restrictive or ineffective.\n"
        )

        self.write_paragraph("Section 4: Eviction Simulation", font_style='B')
        self.write_paragraph(
            "WORK IN PROGRESS: Simulates draining 5, 10, 15, 20, and 25 nodes sequentially (with 15 minute reboot times) to estimate how long "
            "it would take to safely reboot all nodes in the cluster based on your current PDB constraints.\n"
        )

        self.section_title("Why This Matters")
        self.write_paragraph(
            "Pod Disruption Budgets are a critical tool for controlling voluntary disruptions in Kubernetes, such as node drains "
            "during upgrades or maintenance. Without PDBs, applications may be interrupted mid-deployment, causing downtime, "
            "data loss, or failed rollouts. This report helps teams identify gaps in disruption protection and take action "
            "before the next upgrade. When used correctly, PDBs protect availability and maintain application continuity even "
            "during high churn events like rolling updates or node reboots."
        )

    def section1(self, pdbs, coverage_data, namespace):
        self.add_page(orientation='L')
        self.start_section(name="Section 1: Namespace PDB Coverage", level=0)
        self.section_title("Section 1: Namespace PDB Coverage")

        self.write_paragraph("This section provides an overview of the Pod Disruption Budgets (PDBs) defined in the namespace "
            "and their coverage over the pods. PDBs are crucial for ensuring the availability of applications "
            "during voluntary disruptions, such as node maintenance or scaling operations.\n")

        if len(pdbs) == 0:
            self.set_font("Dejavu", 'B', 16)
            self.cell(0, 15, "No PDBs found in this namespace.", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            return
        
        # Build DataFrame (or table data) for output
        df_table = pd.DataFrame([{
            "Total Pods": int(coverage_data["total_pods"]),
            "Covered Pods": int(len(coverage_data["covered_pods"])),
            "Uncovered Pods": int(len(coverage_data["uncovered_pods"])),
            "Coverage (%)": int(round(coverage_data["coverage_percentage"]))
        }])

        # Add Legend
        legend_items_section1 = [
            ((255, 255, 255), "Coverage ≥ 90% (Healthy)"),
            ((255, 255, 153), "Coverage 80–89% (Caution)"),
            ((255, 0, 0),     "Coverage < 80% (Critical)"),
        ]
        self.add_color_legend("Legend", legend_items_section1)

        self.write_paragraph(f"\nNAMESPACE: {namespace}\n", font_style='B')

        self.add_section_1_table(df_table, col_widths=[70, 70, 70, 70])
        
# ---------------------- Main Command ---------------------- #
def run(namespace: str):
    """
    Generates the Pod Disruption Budget (PDB) report for the given namespace.
    """

    # Fetching data
    cluster_name = utils.get_current_context()
    pods_json = utils.get_pods(namespace)
    pdbs_json = utils.get_pdbs(namespace)

    # Check if pods_json is empty
    if len(pods_json) == 0:
        typer.echo("❌ No pods found in the specified namespace.")
        raise typer.Exit()
    
    # Get coverage data
    coverage_data = get_namespace_coverage(pods_json, pdbs_json)
    
    # Create the homepage dataframe
    homepage_df = pd.DataFrame([
        ("Cluster", cluster_name),
        ("Namespace", namespace),
        ("Total Owners", utils.get_total_owners(pods_json)),
        ("Total Pods", len(pods_json)),
        ("Total PDBs", len(pdbs_json)),
        ("Total PDB Coverage", f"{round(coverage_data['coverage_percentage'])}%"),
        ("Report version", VERSION),
        ("Generated", datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %Z'))
    ])

    # PDF Generation
    pdf = PDBReport()
    pdf.report_title = "KubeCase PDB Report"

    # Homepage
    pdf.homepage(metatable_df=homepage_df)

    # Intro Page
    pdf.intro_page()

    # Section 1: Namespace PDB Coverage
    pdf.section1(pdbs_json, coverage_data, namespace)

    # Save the PDF
    pdf.save_report(report_name="pdb_report", namespace=namespace)
