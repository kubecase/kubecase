
import json
import subprocess
from collections import defaultdict
import pandas as pd
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from datetime import datetime
import typer
import os

app = typer.Typer()
version = "1.0.0"

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
        return 0.0
    if cpu_str.endswith('m'):
        return round(float(cpu_str[:-1]) / 1000.0, 2)
    return round(float(cpu_str), 2)

def parse_mem(mem_str):
    if not mem_str:
        return 0
    if mem_str.endswith('Ki'):
        return round(int(mem_str[:-2]) / (1024 ** 2), 2)
    if mem_str.endswith('Mi'):
        return round(int(mem_str[:-2]) / 1024.0, 2)
    if mem_str.endswith('Gi'):
        return round(float(mem_str[:-2]), 2)
    return round(float(mem_str), 2)

def extract_controller_name(pod):
    owner_refs = pod['metadata'].get('ownerReferences', [])
    if owner_refs:
        name = owner_refs[0]['name']
        return "-".join(name.split("-")[:-1]) or name
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
        "pod_count": 0, "cpu_req": 0, "cpu_lim": 0,
        "mem_req": 0, "mem_lim": 0, "es_req": 0, "es_lim": 0,
    })

    for pod in pods_json["items"]:
        controller = extract_controller_name(pod)
        grouped_data[controller]["pod_count"] += 1

        for container in pod["spec"]["containers"]:
            resources = container.get("resources", {})
            req = resources.get("requests", {})
            lim = resources.get("limits", {})

            grouped_data[controller]["cpu_req"] += parse_cpu(req.get("cpu"))
            grouped_data[controller]["cpu_lim"] += parse_cpu(lim.get("cpu"))
            grouped_data[controller]["mem_req"] += parse_mem(req.get("memory"))
            grouped_data[controller]["mem_lim"] += parse_mem(lim.get("memory"))
            grouped_data[controller]["es_req"] += parse_mem(req.get("ephemeral-storage"))
            grouped_data[controller]["es_lim"] += parse_mem(lim.get("ephemeral-storage"))

    return pd.DataFrame.from_dict(grouped_data, orient="index").reset_index().rename(columns={"index": "Controller"})

def parse_quota(quota_json):
    quota_data = []
    for item in quota_json["items"]:
        used = item["status"].get("used", {})
        hard = item["status"].get("hard", {})
        for resource in hard:
            used_val = used.get(resource, "0")
            hard_val = hard.get(resource, "0")

            if "m" in used_val or "m" in hard_val:
                used_num = parse_cpu(used_val)
                hard_num = parse_cpu(hard_val)
            else:
                used_num = parse_mem(used_val)
                hard_num = parse_mem(hard_val)

            usage_percent = round((used_num / hard_num) * 100, 1) if hard_num > 0 else 0.0

            quota_data.append({
                "Resource": resource,
                "Used": used_val,
                "Hard Limit": hard_val,
                "Usage (%)": usage_percent
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

                # Use multi_cell for wrapping (only on the "Flags" column or long text)
              if col.lower() == "flags" or len(value) > 20:
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

    def section_title(self, title):
      self.set_font("Dejavu", 'B', 16)
      self.cell(0, 15, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

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
    pdf.add_page()
    pdf.section_title("Section 1: ResourceQuota Summary")
    pdf.add_table(df_quota, col_widths=[50, 30, 30, 30])
    pdf.ln(10)

    # Section 2 - Controller-Level Resource Usage
    pdf.add_page(orientation='L')
    pdf.section_title("Section 2: Controller-Level Resource Usage")
    legend_lines = [
    "Req = Request",
    "Lim = Limit",
    "ES = Ephemeral Storage"
    ]
    pdf.add_legend(legend_lines, title="Legend")
    df_controller.columns = [
    "Controller", "Pods", 
    "CPU (Req)", "CPU (Lim)", 
    "Mem (Req)", "Mem (Lim)", 
    "ES (Req)", "ES (Lim)"
    ]
    pdf.add_table(df_controller, col_widths=[60, 25, 25, 25, 25, 25, 25, 25])

    # Section 3 - Pod-Level Resource Usage
    pdf.add_page(orientation='L')
    pdf.section_title("Section 3: Pod Level Resource Usage")
    pdf.add_legend(legend_lines, title="Legend")
    container_data = get_container_details(pods_json)

    for pod_name, df in container_data.items():
      pdf.set_font("Dejavu", "B", 11)
      pdf.cell(0, 10, f"{pod_name}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

      # Only include data columns (excluding Flags)
      cols = [c for c in df.columns if c != "Flags"]
      col_widths = [60, 25, 25, 25, 25, 25, 25, 25]

      # Header row
      pdf.set_font("Dejavu", "B", 10)
      for i, col in enumerate(cols):
          pdf.cell(col_widths[i], 10, col, border=1, fill=True, align='C')
      pdf.ln()

      # Data rows
      pdf.set_font("Dejavu", "", 10)
      for _, row in df.iterrows():
          for i, col in enumerate(cols):
              value = row[col]
              if isinstance(value, float):
                  value = f"{value:.2f}"
              pdf.cell(col_widths[i], 10, str(value), border=1, align='C')
          pdf.ln()

          # Render flags on their own line
          pdf.set_font("Dejavu", "", 9)
          flags_text = "Flags: " + str(row["Flags"])
          pdf.set_fill_color(244, 246, 250)
          pdf.cell(sum(col_widths), 8, flags_text, border=1, fill=True)
          pdf.set_fill_color(255, 255, 255)
          pdf.ln()
      pdf.add_page(orientation='L')


      

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
