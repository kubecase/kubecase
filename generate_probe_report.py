#!/usr/bin/env python3

from datetime import datetime
from collections import defaultdict
from fpdf import FPDF
import subprocess
import json
import os
import typer

app = typer.Typer()
version = "1.0.0"

# ------------------------- PDF Class ------------------------- #
class ProbePDF(FPDF):
    def write_line(self, text):
        self.set_font("Arial", '', 11)
        self.multi_cell(0, 8, text)

    def header(self):
        if self.page_no() == 1:
            self.ln(15)
            self.set_font("Arial", 'B', 35)
            self.cell(0, 15, "KubeCase Probe Report", ln=True, align='C')
            self.ln(30)
        else:
            self.set_font("Arial", 'B', 14)
            title = "Kubernetes Probe Report (Owner > Pod > Container)"
            self.cell(0, 10, title, ln=True, align='C')
            self.set_font("Arial", '', 11)
            self.cell(0, 10, f"Generated: {datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}", ln=True)
            self.ln(5)

    def add_metadata_table(self, cluster, namespace, owners, pods, containers, timestamp):
        self.set_font("Arial", '', 16)
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
            self.set_font("Arial", 'B', 16)
            self.cell(label_width, 10, label, border=1, fill=True)
            self.set_font("Arial", '', 16)
            self.cell(value_width, 10, value, border=1)
            self.ln()
            
    def section_title(self, title):
        self.set_font("Arial", 'B', 12)
        self.cell(0, 10, title, ln=True)
        self.ln(1)

    def pod_title(self, pod_name):
        self.set_font("Arial", 'B', 11)
        self.cell(0, 8, f"Pod: {pod_name}", ln=True)
        self.ln(1)

    def write_table(self, headers, rows):
        col_widths = [70, 30, 30, 30]
        self.set_font("Arial", 'B', 10)
        for i, header in enumerate(headers):
            self.cell(col_widths[i], 8, header, border=1)
        self.ln()
        self.set_font("Arial", '', 9)
        for row in rows:
            for i, item in enumerate(row):
                self.cell(col_widths[i], 8, str(item), border=1)
            self.ln()
        self.ln(3)

# ---------------------- Helper Functions ---------------------- #
def get_probe_seconds(probe, probe_type):
    if not probe:
        return None
    delay = probe.get("initialDelaySeconds", 0)
    period = probe.get("periodSeconds", 10)
    threshold = probe.get("failureThreshold", 3)
    runtime_total = period * threshold
    initial_total = delay + runtime_total
    return f"{initial_total}s" if probe_type == "startupProbe" else f"{initial_total}s, {runtime_total}s"

# ---------------------- Main Command ---------------------- #
@app.command()
def probe(namespace: str):
    """Generate a probe report for a specific namespace."""
    try:
        cluster_name = subprocess.check_output(["kubectl", "config", "current-context"], text=True).strip()
    except subprocess.CalledProcessError:
        cluster_name = "Unknown"

    try:
        raw = subprocess.check_output(["kubectl", "get", "pods", "-n", namespace, "-o", "json"], text=True)
        pod_data = json.loads(raw)
    except subprocess.CalledProcessError as e:
        typer.echo(f"Failed to fetch pod data: {e}")
        raise typer.Exit(code=1)

    owners = defaultdict(lambda: defaultdict(list))
    startup_missing = liveness_missing = readiness_missing = 0
    all_containers = 0
    seen_owners = set()

    for pod in pod_data.get("items", []):
        metadata = pod["metadata"]
        ref = metadata.get("ownerReferences", [{}])[0]
        owner = f"{ref.get('kind', 'Pod')}/{ref.get('name', metadata['name'])}"
        seen_owners.add(owner)
        pod_name = metadata["name"]

        for container in pod["spec"].get("containers", []):
            all_containers += 1
            container_name = container["name"]
            startup = liveness = readiness = "--"

            for probe_type in ["startupProbe", "livenessProbe", "readinessProbe"]:
                probe = container.get(probe_type)
                total = get_probe_seconds(probe, probe_type)
                if total is not None:
                    if probe_type == "startupProbe": startup = total
                    elif probe_type == "livenessProbe": liveness = total
                    elif probe_type == "readinessProbe": readiness = total
                else:
                    if probe_type == "startupProbe": startup_missing += 1
                    elif probe_type == "livenessProbe": liveness_missing += 1
                    elif probe_type == "readinessProbe": readiness_missing += 1

            owners[owner][pod_name].append([container_name, startup, liveness, readiness])

    # PDF Generation
    pdf = ProbePDF()

    # Front Page
    pdf.add_page()
    pdf.add_metadata_table(
        cluster=cluster_name,
        namespace=namespace,
        owners=len(seen_owners),
        pods=len(pod_data.get('items', [])),
        containers=all_containers,
        timestamp=datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')
    )

    # Add image
    pdf.image("mascot.png", x=(pdf.w - 100)/2, y=150, w=100)  
    pdf.ln(115)
    pdf.set_font("Arial", 'BI', 16)
    pdf.cell(0, 20, "\"Sniffing configs, one line at a time\"", ln=True, align='C')
    pdf.set_font("Arial", '', 16)
    pdf.cell(0, 10, f"KubeCase · https://github.com/kubecase/kubecase · v{version}", ln=True, align='C')


    # Explanation Page
    pdf.add_page()
    pdf.section_title("Explanation")
    pdf.write_line(
        "This report organizes probes by workload owner, then lists each pod and its containers. "
        "For each container, the time before a probe takes action is calculated as:\n"
        "initialDelaySeconds + (periodSeconds × failureThreshold) \n"
        "Probes not configured are shown as '--'. This layout helps identify which probes exist, how aggressive they are, and where gaps exist.\n\n"
        "Probe Timing Format:\n"
        "initial_time, runtime_time\n"
        "Example: 12s, 6s\nMeans: First failure may take up to 12s (cold start), while any future failures will be detected within 6s"
    )

    for owner, pods in owners.items():
        pdf.add_page()
        pdf.section_title(f"Owner: {owner}")
        for pod_name, containers in pods.items():
            pdf.pod_title(pod_name)
            pdf.write_table(["Container", "Startup", "Liveness", "Readiness"], containers)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out_path = f"probe_report_{namespace}_{timestamp}.pdf"
    pdf.output(out_path)
    typer.echo(f"✅ KubeCase Probe Report saved to {out_path}")

if __name__ == "__main__":
    app()
