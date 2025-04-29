# This script generates a PDF report for Kubernetes Pod Disruption Budgets (PDBs) in a specified namespace.

# ---------------------- Imports ---------------------- #
import pandas as pd
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from datetime import datetime
import typer
import os
import math

# Import custom modules
import kubecase.utils as utils

# ---------------------- Constants ---------------------- #
version = "1.0.0"
           
# ---------------------- Helper Functions ---------------------- # 
def get_total_owners(pods_list):
    owners = set()
    for pod in pods_list:
        owner_refs = pod["metadata"].get("ownerReferences", [])
        if owner_refs:
            owner_name = owner_refs[0]['name']
            owner_group = "-".join(owner_name.split("-")[:-1]) or owner_name
        else:
            owner_group = "standalone/" + pod["metadata"]["name"]
        owners.add(owner_group)
    return len(owners)

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
class PDFReport(FPDF):
    def __init__(self):
        super().__init__()
        font_path_regular = utils.get_font_path("DejaVuSansCondensed.ttf")
        font_path_bold = utils.get_font_path("DejaVuSansCondensed-Bold.ttf")
        self.add_font("Dejavu", "", font_path_regular)
        self.add_font("Dejavu", "B", font_path_bold)

    def homepage(self, cluster_name, namespace, pods, pdbs):
        self.add_page()
        self.start_section(name="Namespace Overview", level=0)
        self.add_metadata_table(
            cluster=cluster_name,
            namespace=namespace,
            owners=get_total_owners(pods),
            pods=len(pods),
            pdbs=len(pdbs),
            timestamp=datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')
        )
        # Add image
        mascot_path = utils.get_asset_path("mascot.png")
        self.image(mascot_path, x=(self.w - 100)/2, y=150, w=100)  
        self.ln(115)
        self.set_font("Dejavu", 'B', 16)
        self.cell(0, 20, "\"Sniffing configs, one line at a time\"", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
        self.set_font("Dejavu", '', 16)
        self.cell(0, 10, f"KubeCase · https://github.com/kubecase/kubecase · v{version}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')

    def intro_page(self):
        self.add_page()
        self.section_title("Purpose")
        self.set_font("Dejavu", '', 12)
        self.write_paragraph("This report provides a comprehensive snapshot of container resource usage and "
            "configuration within a Kubernetes namespace. Its purpose is to help platform engineers, developers, "
            "and leadership understand how workloads are defined, how they interact with the cluster’s scheduling "
            "and stability mechanisms, and whether they follow best practices.")
        
        self.section_title("What This Report Covers")
        self.write_paragraph("Section 1: ResourceQuota Summary", font_style='B')
        self.write_paragraph("Shows the total resource quotas assigned to the namespace and how much has been "
            "requested so far. Highlights potential overuse or inefficiencies.\n")
        
        self.write_paragraph("Section 2: Controller-Level Resource Usage", font_style='B')
        self.write_paragraph("Groups resource requests and limits by owner (Deployment, StatefulSet, etc.). "
            "This helps identify which workloads are well configured and which may be missing limits, causing "
            "cluster and app risk.\n")
        
        self.write_paragraph("Section 3: Pod-Level Resource Usage", font_style='B')
        self.write_paragraph("Displays CPU, memory, and ephemeral storage requests and limits for every container. "
            "Flags misconfigurations such as missing limits, missing requests, or containers that request more "
            "than they’re limited to.\n")
        
        self.write_paragraph("Section 4: QoS Class Distribution", font_style='B')
        self.write_paragraph("Visualizes how many pods are classified as Guaranteed, Burstable, or BestEffort. "
            "This directly affects eviction priority and reliability. Includes a detailed explanation of what "
            "each class means and why it matters.")

        self.section_title("Why This Matters")
        self.write_paragraph("Kubernetes is a powerful platform, but it requires careful configuration to ensure "
            "stability and performance. Setting resource requests and limits correctly is one of the simplest "
            "and most powerful ways to improve Kubernetes stability. This report surfaces the invisible "
            "misconfigurations that can lead to poor performance, uneven node pressure, or unexpected pod "
            "evictions. This report helps teams fix them before they become incidents.")

    def section1(self, pods, pdbs, namespace):
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
        
        # Calculate coverage
        coverage_data = get_namespace_coverage(pods, pdbs)

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

        self.add_table(df_table, col_widths=[70, 70, 70, 70])

    def header(self):
        if self.page_no() == 1:
            self.ln(15)
            self.set_font("Dejavu", 'B', 35)
            self.cell(0, 15, "KubeCase PDB Report", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
            self.ln(30)
        else:
            self.set_font("Dejavu", 'B', 18)
            self.cell(0, 10, "KubeCase PDB Report", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
            self.ln(5)

    def write_paragraph(self, text, font_style='', font_size=12, spacing=5):
        self.set_font("Dejavu", font_style, font_size)
        self.write(spacing, text)
        self.ln()

    def add_metadata_table(self, cluster, namespace, owners, pods, pdbs, timestamp):
        self.set_font("Dejavu", '', 16)
        self.set_fill_color(244, 246, 250)  # Light gray background

        # Define table rows
        data = [
            ("Cluster", cluster),
            ("Namespace", namespace),
            ("Total Owners", str(owners)),
            ("Total Pods", str(pods)),
            ("Total PDBs", str(pdbs)),
            ("Generated", timestamp)
        ]

        # Set column width and center table
        label_width = 60
        value_width = self.w - 2 * self.l_margin - label_width

        for label, value in data:
            self.set_font("Dejavu", 'B', 16)
            self.cell(label_width, 10, label, border=1, fill=True)
            self.set_font("Dejavu", '', 16)
            self.cell(value_width, 10, value, border=1)
            self.ln()

    def add_table(self, dataframe, col_widths=None, title=None):
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

    def add_legend(self, lines, title="Legend"):
      self.set_font("Dejavu", "B", 11)
      self.cell(0, 10, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
      self.set_font("Dejavu", "", 10)
      for line in lines:
          self.cell(0, 8, line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
      self.ln(5)

    def add_color_legend(self, title, items, col_widths=(20, 100)):
        """
        Draws a two-column legend box.
        :param title: Title of the legend section (e.g. "Legend:")
        :param items: List of tuples → (fill_color as (R,G,B), label text)
        :param col_widths: Tuple of (color box width, label width)
        """
        self.set_font("Dejavu", "B", 11)
        self.cell(0, 10, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_font("Dejavu", "", 10)

        color_w, label_w = col_widths
        for fill_color, label in items:
            self.set_fill_color(*fill_color)
            self.cell(color_w, 8, "", border=1, fill=True)
            self.set_fill_color(255, 255, 255)  # reset for next cell
            self.cell(label_w, 8, label, border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(3)

    def section_title(self, title):
      self.set_font("Dejavu", 'B', 16)
      self.cell(0, 15, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def add_table_with_flag_rows(self, dataframe, col_widths=None, title=None, highlight_usage=False):
        # Defaults
        line_height = 10
        self.set_font("Dejavu", "", 10)

        if title:
            self.set_font("Dejavu", "B", 12)
            self.cell(0, 10, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            self.ln(2)

        self.set_font("Dejavu", "B", 10)
        data_cols = [col for col in dataframe.columns if col != "Flags"]
        col_widths = col_widths or [40] * len(data_cols)

        # Draw header row
        for i, col in enumerate(data_cols):
            self.set_fill_color(244, 246, 250)  # Light gray background
            self.cell(col_widths[i], 10, col, border=1, fill=True, align='C')
        self.ln()

        for _, row in dataframe.iterrows():
          self.set_font("Dejavu", "", 10)
          self.set_fill_color(255, 255, 255)  # white
          text_color = (0, 0, 0)

          # --- Determine fill color based on Usage (%) ---
          resource_name = row.get("Resource", "")
          usage = float(row.get("Usage (%)", 0))
          if highlight_usage:
            if resource_name == "resourcequotas":
                # Special case for resourcequotas
                self.set_fill_color(255, 255, 255)  # default white
                text_color = (0, 0, 0)
            elif usage >= 90:
                self.set_fill_color(255, 0, 0)  # red
                text_color = (255, 255, 255)
            elif usage >= 80:
                self.set_fill_color(255, 255, 153)  # yellow
                text_color = (0, 0, 0)
            self.set_text_color(*text_color)

          # Estimate row height
          row_height = 10  # default
          for wrap_col in ["Controller", "Container"]:
            if wrap_col in data_cols:
                idx = data_cols.index(wrap_col)
                col_width = col_widths[idx] - 2  # reduce for padding
                text = str(row[wrap_col])
                
                # Estimate the rendered string width in mm
                string_width = self.get_string_width(text)
                estimated_lines = math.ceil(string_width / col_width)
                est_height = max(10, estimated_lines * line_height)
                
                row_height = max(row_height, est_height)

          # Check if row fits on current page
          if self.get_y() + row_height + 10 > self.page_break_trigger:
              self.add_page(orientation=self.cur_orientation)

              # Re-draw the table header
              self.set_font("Dejavu", "B", 10)
              for i, col in enumerate(data_cols):
                  self.set_fill_color(244, 246, 250)
                  self.cell(col_widths[i], 10, col, border=1, fill=True, align='C')
              self.ln()
              
              # Reset
              self.set_font("Dejavu", "", 10)
              self.set_fill_color(255, 255, 255) 

          # Store Y position to restore after drawing multi_cell
          y_start = self.get_y()

          # STEP 2: Draw the controller column as wrapped
          for i, col in enumerate(data_cols):
              value = f"{row[col]:.2f}" if isinstance(row[col], float) else str(row[col])
              col_width = col_widths[i]

              if col in ["Controller", "Container"]:
                  # Draw wrapped controller column
                  x_start = self.get_x()
                  self.multi_cell(col_width, line_height, value, border=1)
                  self.set_xy(x_start + col_width, y_start)  # return to top right of the wrapped cell
              else:
                  self.set_xy(self.get_x(), y_start)  # reset Y position before drawing each cell
                  self.cell(col_width, row_height, value, border=1, fill=True, align='C')

          # STEP 3: Move to next line based on tallest column
          self.ln(row_height)

          # --- Reset colors for Flags row ---
          self.set_text_color(0, 0, 0)
          self.set_fill_color(240, 240, 240)

          # Flags row
          if str(row["Flags"]) != "OK":
            self.set_font("Dejavu", "B", 10)
            self.set_fill_color(220, 220, 255)  # Pale lavender for Flags row
            flags_text = "Flags: " + str(row["Flags"])
            self.cell(sum(col_widths), 10, flags_text, border=1, fill=True)
            self.ln()
            self.set_font("Dejavu", "", 10)
    
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

    # PDF Generation
    pdf = PDFReport()

    # Homepage
    pdf.homepage(cluster_name, namespace, pods_json, pdbs_json)

    # Intro Page
    #pdf.intro_page()

    # Section 1 - ResourceQuota Summary
    pdf.section1(pods_json, pdbs_json, namespace)

    # Save the PDF
    os.makedirs("reports", exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out_path = f"reports/pdb_report_{namespace}_{timestamp}.pdf"
    
    try:
        pdf.output(out_path)
        typer.echo(f"✅ KubeCase Pod Disruption Budget Report saved to {out_path}")
    except Exception as e:
        typer.echo(f"❌ Error saving PDF: {e}")
