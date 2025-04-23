
import json
import subprocess
from collections import defaultdict
import pandas as pd
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from datetime import datetime
import typer
import os
from collections import Counter
import math

app = typer.Typer()
version = "1.2.1"

# ------------------------- PDF Class ------------------------- #
class ProbeReport(FPDF):
    def write_line(self, text):
        self.set_font("Dejavu", '', 12)
        self.multi_cell(0, 8, text)

    def header(self):
        if self.page_no() == 1:
            self.ln(15)
            self.set_font("Dejavu", 'B', 35)
            self.cell(0, 15, "KubeCase Probe Report", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
            self.ln(30)
        else:
            self.set_font("Dejavu", 'B', 18)
            self.cell(0, 10, "KubeCase Probe Report", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
            self.ln(5)
            
    def section_title(self, title):
        self.set_font("Dejavu", 'B', 16)
        self.cell(0, 15, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def pod_title(self, pod_name):
        self.set_font("Dejavu", 'B', 12)
        self.cell(0, 5, f"Pod: {pod_name}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(1)

    def write_table(self, headers, rows):
        col_widths = [35, 25, 20, 20, 20, 40, 40, 80]
        #col_widths = [self.w * width / sum(col_widths) for width in col_widths]
        self.set_font("Dejavu", 'B', 10)

        for i, header in enumerate(headers):
            self.cell(col_widths[i], 8, header, border=1)
        self.ln()

        self.set_font("Dejavu", '', 9)
        for row in rows:
            restart_count_raw = row[4].split()[0]
            restart_count = int(restart_count_raw) if restart_count_raw.isdigit() else 0

            # Determine fill color
            if restart_count > 0:
                self.set_fill_color(255, 255, 153)  # yellow
            else:
                self.set_fill_color(255, 255, 255)  # white

            # IF POD IS NOT READY
            # self.set_fill_color(255, 102, 102)  # red

            for i, item in enumerate(row):
                self.cell(col_widths[i], 8, str(item), border=1, fill=True)
            self.ln()
        self.ln(3)

    def write_paragraph(self, text, font_style='', font_size=12, spacing=5):
        self.set_font("Dejavu", font_style, font_size)
        self.write(spacing, text)
        self.ln()

    def write_code_block(self, code_text):
        self.ln(2)
        self.set_font("Courier", '', 10)
        self.set_fill_color(240, 240, 240)
        self.cell(0, 10, code_text, fill=True, border=1)
        self.ln(12)

    def add_section_divider(self, title, restarts_summary=None):
        self.add_page(orientation="L")
        
        # Title
        self.set_font("DejaVu", 'B', 26)
        self.set_text_color(220, 50, 32)  # Red tone
        self.cell(0, 40, title, align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        self.set_text_color(0, 0, 0)  # Reset to black
        self.set_font("DejaVu", '', 16)

        # Creating Table
        self.set_fill_color(244, 246, 250)  # Light gray background

        # Set column width and center table
        label_width = 100
        value_width = self.w - 2 * self.l_margin - label_width

        for label, value in restarts_summary:
            self.set_font("Dejavu", 'B', 16)
            self.cell(label_width, 10, label, border=1, fill=True)
            self.set_font("Dejavu", '', 16)
            self.cell(value_width, 10, value, border=1)
            self.ln()

           
# ---------------------- Helper Functions ---------------------- #
def parse_cpu(cpu_str):
    if not cpu_str:
        return 0.0, None

    try:
        if cpu_str.endswith("m"):
            value = round(float(cpu_str[:-1]) / 1000.0, 2)
            return value, None
        elif cpu_str.replace('.', '', 1).isdigit():
            return round(float(cpu_str), 2), None
        else:
            return 0.0, f"Invalid CPU value '{cpu_str}'"
    except ValueError:
        return 0.0, f"Unable to parse CPU value '{cpu_str}'"

def parse_mem(mem_str):
    if not mem_str:
        return 0.0, None

    try:
        if mem_str.endswith('Ki'):
            return round(int(mem_str[:-2]) / 1024, 2), None
        elif mem_str.endswith('Mi'):
            return round(float(mem_str[:-2]), 2), None
        elif mem_str.endswith('Gi'):
            return round(float(mem_str[:-2]) * 1024, 2), None
        elif mem_str.endswith('Ti'):
            return round(float(mem_str[:-2]) * 1024 * 1024, 2), None
        elif mem_str.endswith('K'):
            return round(float(mem_str[:-1]) / 1024, 2), None
        elif mem_str.endswith('M'):
            return round(float(mem_str[:-1]), 2), None
        elif mem_str.endswith('G'):
            return round(float(mem_str[:-1]) * 1024, 2), None
        elif mem_str.endswith('T'):
            return round(float(mem_str[:-1]) * 1024 * 1024, 2), None
        elif mem_str.endswith('m'):
            return round(float(mem_str[:-1]) * (0.001 / 1048576), 2), "Non-standard memory unit 'm' used"
        else:
            return round(float(mem_str) / (1024 * 1024), 2), None
    except ValueError:
        print(f"⚠️ Warning: Unable to parse memory value '{mem_str}'. Interpreted as 0.")
        return 0.0, f"Unable to parse memory value '{mem_str}'"

def parse_quota_value(resource_key, raw_value):
    try:
        if any(kw in resource_key for kw in ["cpu"]):
            value, flag = parse_cpu(raw_value)
            return value, flag
        elif any(kw in resource_key for kw in ["memory", "storage", "ephemeral-storage"]):
            value, flag = parse_mem(raw_value)
            return value, flag
        elif resource_key.startswith("count/") or resource_key in ["pods", "secrets", "configmaps", "persistentvolumeclaims"]:
            return int(raw_value), None
        else:
            return float(raw_value), "units", None
    except Exception as e:
        return 0.0, f"Parse error for '{resource_key}': {str(e)}"
    
def extract_controller_name(pod):
    owner_refs = pod['metadata'].get('ownerReferences', [])
    if owner_refs:
        owner = owner_refs[0]
        return f"{owner['kind'].lower()}/{owner['name']}"
    return "standalone/" + pod['metadata']['name']

def get_pods(namespace):
    result = subprocess.run(["kubectl", "get", "pods", "-n", namespace, "-o", "json"],
                            stdout=subprocess.PIPE, text=True)
    return json.loads(result.stdout)

def get_resourcequota(namespace):
    result = subprocess.run(["kubectl", "get", "resourcequota", "-n", namespace, "-o", "json"],
                            stdout=subprocess.PIPE, text=True)
    return json.loads(result.stdout)

def aggregate_resources_by_controller(pods_json):
    grouped_data = defaultdict(lambda: {
        "pod_count": 0,
        "cpu_req": 0.0, "cpu_lim": 0.0,
        "mem_req": 0.0, "mem_lim": 0.0,
        "es_req": 0.0, "es_lim": 0.0,
        "flags": Counter()
    })
    

    for pod in pods_json["items"]:
        controller = extract_controller_name(pod)
        if controller.startswith("standalone/"):
          grouped_data[controller]["flags"]["Standalone pod without controller"] += 1
        grouped_data[controller]["pod_count"] += 1

        for container in pod["spec"]["containers"]:
            resources = container.get("resources", {})
            req = resources.get("requests", {})
            lim = resources.get("limits", {})

            # CPU
            cpu_req, cpu_req_flag = parse_cpu(req.get("cpu"))
            cpu_lim, cpu_lim_flag = parse_cpu(lim.get("cpu"))
            grouped_data[controller]["cpu_req"] += cpu_req
            grouped_data[controller]["cpu_lim"] += cpu_lim

            # Memory
            mem_req, mem_req_flag = parse_mem(req.get("memory"))
            mem_lim, mem_lim_flag = parse_mem(lim.get("memory"))
            grouped_data[controller]["mem_req"] += mem_req
            grouped_data[controller]["mem_lim"] += mem_lim

            # Ephemeral Storage
            es_req, es_req_flag = parse_mem(req.get("ephemeral-storage"))
            es_lim, es_lim_flag = parse_mem(lim.get("ephemeral-storage"))
            grouped_data[controller]["es_req"] += es_req
            grouped_data[controller]["es_lim"] += es_lim

            # Collect any parsing flags
            for flag in [cpu_req_flag, cpu_lim_flag, mem_req_flag, mem_lim_flag, es_req_flag, es_lim_flag]:
                if flag:
                    grouped_data[controller]["flags"][flag] += 1        

    # Build the DataFrame
    df = pd.DataFrame.from_dict(grouped_data, orient="index").reset_index().rename(columns={"index": "Controller"})
    df["Flags"] = df["flags"].apply(format_flag_counts)
    df.drop(columns=["flags"], inplace=True)

    # Round numeric fields
    for col in ["cpu_req", "cpu_lim", "mem_req", "mem_lim", "es_req", "es_lim"]:
        df[col] = df[col].round(2)

    return df

def format_flag_counts(counter):
    if not counter:
        return "OK"
    return "; ".join(
        f"{flag} ({count}x)" if count > 1 else flag
        for flag, count in sorted(counter.items())
    )

def parse_quota(quota_json):
    quota_data = []
    for item in quota_json["items"]:
        used = item["status"].get("used", {})
        hard = item["status"].get("hard", {})
        for resource in hard:
            used_val = used.get(resource, "0")
            hard_val = hard.get(resource, "0")

            used_num, used_flag = parse_quota_value(resource, used_val)
            hard_num, hard_flag = parse_quota_value(resource, hard_val)

            usage_percent = round((used_num / hard_num) * 100, 1) if hard_num > 0 else 0.0
            flags = "; ".join(filter(None, [used_flag, hard_flag]))

            quota_data.append({
                "Resource": resource,
                "Used": used_val,
                "Hard Limit": hard_val,
                "Usage (%)": usage_percent,
                "Flags": flags or "OK"
            })
    return pd.DataFrame(quota_data)

def get_total_pods(pods_json):
    return len(pods_json.get("items", []))

def get_total_containers(pods_json):
    return sum(len(pod["spec"].get("containers", [])) for pod in pods_json.get("items", []))

def get_total_owners(pods_json):
    owners = set()
    for pod in pods_json.get("items", []):
        owner_refs = pod["metadata"].get("ownerReferences", [])
        if owner_refs:
            owner_name = owner_refs[0]['name']
            owner_group = "-".join(owner_name.split("-")[:-1]) or owner_name
        else:
            owner_group = "standalone/" + pod["metadata"]["name"]
        owners.add(owner_group)
    return len(owners)

def get_container_details(pods_json):
    grouped_details = {}

    for pod in pods_json["items"]:
        pod_name = pod["metadata"]["name"]
        qos = pod["status"].get("qosClass", "Unknown")
        pod_containers = []

        for container in pod["spec"]["containers"]:
            name = container["name"]
            resources = container.get("resources", {})
            req = resources.get("requests", {})
            lim = resources.get("limits", {})

            cpu_req = req.get("cpu", "-")
            cpu_lim = lim.get("cpu", "-")
            mem_req = req.get("memory", "-")
            mem_lim = lim.get("memory", "-")
            es_req = req.get("ephemeral-storage", "-")
            es_lim = lim.get("ephemeral-storage", "-")


            has_req = any([cpu_req != "-", mem_req != "-", es_req != "-"])
            has_lim = any([cpu_lim != "-", mem_lim != "-", es_lim != "-"])

            # Flags
            flags = []
            if not has_req and not has_lim:
                flags.append("Missing resources")
            if cpu_req == "-" and mem_req == "-" and es_req == "-":
                flags.append("No requests")
            if cpu_lim == "-" and mem_lim == "-" and es_lim == "-":
                flags.append("No limits")
            if cpu_req != "-" and cpu_lim != "-" and cpu_req > cpu_lim:
                flags.append("CPU req > lim")

            pod_containers.append({
                "Container": name,
                "CPU (Req)": cpu_req,
                "CPU (Lim)": cpu_lim,
                "Mem (Req)": mem_req,
                "Mem (Lim)": mem_lim,
                "ES (Req)": es_req,
                "ES (Lim)": es_lim,
                "QoS": qos,
                "Flags": ", ".join(flags) if flags else "OK"
            })

        grouped_details[pod_name] = pd.DataFrame(pod_containers)

    return grouped_details

# ------------------------- PDF Class ------------------------- #
class PDFReport(FPDF):
    def header(self):
        if self.page_no() == 1:
            self.ln(15)
            self.set_font("Dejavu", 'B', 35)
            self.cell(0, 15, "KubeCase Resource Report", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
            self.ln(30)
        else:
            self.set_font("Dejavu", 'B', 18)
            self.cell(0, 10, "KubeCase Resource Report", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
            self.ln(5)

    def add_metadata_table(self, cluster, namespace, owners, pods, containers, timestamp):
        self.set_font("Dejavu", '', 16)
        self.set_fill_color(244, 246, 250)  # Light gray background

        # Define table rows
        data = [
            ("Cluster", cluster),
            ("Namespace", namespace),
            ("Total Owners", str(owners)),
            ("Total Pods", str(pods)),
            ("Total Containers", str(containers)),
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
        if col_widths is None:
            col_widths = [40] * len(dataframe.columns)

        # Draw header row
        for i, col in enumerate(dataframe.columns):
            self.set_fill_color(244, 246, 250)  # Light gray background
            self.cell(col_widths[i], 10, col, border=1, fill=True, align='C')
        self.ln()

        self.set_font("Dejavu", "", 10)

        # Draw each row
        for _, row in dataframe.iterrows():
            y_start = self.get_y()
            max_y = y_start

            # TODO 
            usage = float(row.get("Usage (%)", 0))
            if usage >= 90:
                self.set_fill_color(255, 0, 0)
                text_color = (255, 255, 255)
            elif usage >= 70:
                self.set_fill_color(255, 255, 153)  # yellow
                text_color = (0, 0, 0)
            else:
                self.set_fill_color(255, 255, 255)
                text_color = (0, 0, 0)

            self.set_text_color(*text_color)

            # Draw each cell in the row
            for i, col in enumerate(dataframe.columns):
              value = str(row[col])
              cell_width = col_widths[i]

              # Use multi_cell for wrapping (only on the "Flags" column)
              if col.lower() == "flags":
                  x_before = self.get_x()
                  y_before = self.get_y()
                  self.multi_cell(cell_width, 10, value, border=1)
                  max_y = max(max_y, self.get_y())
                  self.set_xy(x_before + cell_width, y_before)
              else:
                  self.cell(cell_width, 10, value, border=1, align='C')
        
            self.ln(max_y - y_start if max_y > y_start else 10)

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
        if title:
            self.set_font("Dejavu", "B", 12)
            self.cell(0, 10, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            self.ln(2)

        self.set_font("Dejavu", "B", 10)
        if col_widths is None:
            col_widths = [40] * len(dataframe.columns)

        # Draw header (excluding Flags)
        data_cols = [col for col in dataframe.columns if col != "Flags"]
        col_widths = col_widths or [40] * len(data_cols)
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
            else:
                self.set_fill_color(255, 255, 255)  # white
                text_color = (0, 0, 0)

            self.set_text_color(*text_color)

          # STEP 1: Determine row height if wrapping controller
          row_height = 10  # default
          line_height = 6

          if "Controller" in data_cols:
              controller_value = str(row["Controller"])
              controller_width = col_widths[data_cols.index("Controller")] - 3
              max_text_width = self.get_string_width(controller_value)
              estimated_lines = math.ceil(max_text_width / controller_width)
              row_height = estimated_lines * line_height

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

              if col.lower() == "controller":
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
            self.set_font("Dejavu", "B", 9)
            self.set_fill_color(220, 220, 255)  # Pale lavender for Flags row
            flags_text = "Flags: " + str(row["Flags"])
            self.cell(sum(col_widths), 10, flags_text, border=1, fill=True)
            self.ln()

# ---------------------- Main Command ---------------------- #
@app.command()
def resource(
    namespace: str = typer.Option(..., "-n", "--namespace", help="Target namespace to analyze")
):
    typer.echo(f"🔍 Generating KubeCase Resource Report for namespace: {namespace}")

    try:
        cluster_name = subprocess.check_output(["kubectl", "config", "current-context"], text=True).strip()
    except subprocess.CalledProcessError:
        cluster_name = "Unknown"


    pods_json = get_pods(namespace)
    quota_json = get_resourcequota(namespace)

    df_controller = aggregate_resources_by_controller(pods_json)
    df_controller = df_controller.round(2)
    df_quota = parse_quota(quota_json)

    # PDF Generation
    pdf = PDFReport()
    pdf.add_font("Dejavu", "", "fonts/DejaVuSansCondensed.ttf")
    pdf.add_font("Dejavu", "B", "fonts/DejaVuSansCondensed-Bold.ttf")

    # Front Page
    pdf.add_page()
    pdf.add_metadata_table(
        cluster=cluster_name,
        namespace=namespace,
        owners=get_total_owners(pods_json),
        pods=get_total_pods(pods_json),
        containers=get_total_containers(pods_json),
        timestamp=datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')
    )
    # Add image
    pdf.image("mascot.png", x=(pdf.w - 100)/2, y=150, w=100)  
    pdf.ln(115)
    pdf.set_font("Dejavu", 'B', 16)
    pdf.cell(0, 20, "\"Sniffing configs, one line at a time\"", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
    pdf.set_font("Dejavu", '', 16)
    pdf.cell(0, 10, f"KubeCase · https://github.com/kubecase/kubecase · v{version}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')

    # Section 1 - ResourceQuota Summary
    pdf.add_page(orientation='L')
    pdf.section_title("Section 1: ResourceQuota Summary")
    legend_items_section1 = [
    ((255, 255, 255), "Usage < 70% (Normal)"),
    ((255, 255, 153), "Usage ≥ 70% (Caution)"),
    ((255, 0, 0),   "Usage ≥ 90% (Critical)"),
    ((220, 220, 255), "Warning: If flags were set"),  # Pale lavender for Flags row
    ((255, 255, 255), "resourcequotas (Expected 1/1 count)")
    ]
    pdf.add_color_legend("Legend", legend_items_section1)
    pdf.add_table_with_flag_rows(df_quota, col_widths=[70, 40, 40, 40], highlight_usage=True)

    # Section 2 - Controller-Level Resource Usage
    pdf.add_page(orientation='L')
    pdf.section_title("Section 2: Controller-Level Resource Usage")
    legend_lines = [
    "Req = Request",
    "Lim = Limit",
    "ES = Ephemeral Storage"
    ]
    legend_items_section_abbr = [
    ((255, 255, 255), "Req = Requested value"),
    ((255, 255, 255), "Lim = Limit value"),
    ((255, 255, 255), "ES = Ephemeral Storage"),
    ((220, 220, 255), "Warning: If flags were set")  # Pale lavender for Flags row
    ]
    pdf.add_color_legend("Legend", legend_items_section_abbr)

    df_controller.columns = [
    "Controller", "Pods", 
    "CPU (Req)", "CPU (Lim)", 
    "Mem (Req)", "Mem (Lim)", 
    "ES (Req)", "ES (Lim)", "Flags"
    ]
    pdf.add_table_with_flag_rows(df_controller, col_widths=[120, 15, 22, 22, 25, 25, 25, 25])

    # Section 3 - Pod-Level Resource Usage
    #pdf.add_page(orientation='L')
    #pdf.section_title("Section 3: Pod Level Resource Usage")
    #pdf.add_legend(legend_lines, title="Legend")
    #container_data = get_container_details(pods_json)

    #for pod_name, df in container_data.items():
    #  pdf.add_table_with_flag_rows(
    #   df,
    #    col_widths=[80, 25, 25, 25, 25, 25, 25, 25],  # Adjust based on your columns
    #    title=f"{pod_name}"
    #  )
    #  pdf.add_page(orientation='L')  

    # Create reports folder if it doesn't exist
    os.makedirs("reports", exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out_path = f"reports/resource_report_{namespace}_{timestamp}.pdf"

    try:
        pdf.output(out_path)
        typer.echo(f"✅ KubeCase Resource Report saved to {out_path}")
    except Exception as e:
        typer.echo(f"❌ Error saving PDF: {e}")


if __name__ == "__main__":
    app()
