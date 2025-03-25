#!/usr/bin/env python3

from datetime import datetime
from collections import defaultdict
from fpdf import FPDF
import subprocess
import json
import sys
import os
import matplotlib.pyplot as plt

class ProbePDF(FPDF):
    def write_line(self, text):
        self.set_font("Arial", '', 11)
        self.multi_cell(0,8, text)

    def header(self):
        if self.page_no() == 1:
            self.set_font("Arial", 'B', 14)
            self.cell(0, 10, "Kubernetes Probe Report Summary", ln=True, align='C')
            self.set_font("Arial", '', 11)
            self.cell(0, 10, f"Generated: {datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}", ln=True)
            self.ln(5)
        else:
            self.set_font("Arial", 'B', 14)
            self.cell(0, 10, "Kubernetes Probe Report (Owner > Pod > Container)", ln=True, align='C')
            self.set_font("Arial", '', 11)
            self.cell(0, 10, f"Generated: {datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}", ln=True)
            self.ln(5)

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

def get_probe_seconds(probe):
    if not probe:
        return None
    delay = probe.get("initialDelaySeconds", 0)
    period = probe.get("periodSeconds", 10)
    threshold = probe.get("failureThreshold", 3)

    runtime_total = period * threshold
    initial_total = delay + runtime_total
    
    if probe_type == "startupProbe":
        return f"{initial_total}s"
    else:
        return f"{initial_total}s, {runtime_total}s"

if len(sys.argv) != 2:
    print("Usage: python3 generate_probe_report.py <namespace>")
    sys.exit(1)

namespace = sys.argv[1]

try:
    cluster_name = subprocess.check_output(["kubectl", "config", "current-context"], text=True).strip()
except subprocess.CalledProcessError:
    cluster_name = "Unknown"

try:
    raw = subprocess.check_output(["kubectl", "get", "pods", "-n", namespace, "-o", "json"], text=True)
    pod_data = json.loads(raw)
except subprocess.CalledProcessError as e:
    print("Failed to fetch pod data:", e)
    sys.exit(1)

owners = defaultdict(lambda: defaultdict(list))
missing_summary = []
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
        missing = []

        for probe_type in ["startupProbe", "livenessProbe", "readinessProbe"]:
            probe = container.get(probe_type)
            total = get_probe_seconds(probe)
            if total is not None:
                if probe_type == "startupProbe":
                    startup = total
                elif probe_type == "livenessProbe":
                    liveness = total
                elif probe_type == "readinessProbe":
                    readiness = total
            else:
                missing.append(probe_type.replace("Probe", "").capitalize())
                if probe_type == "startupProbe":
                    startup_missing += 1
                elif probe_type == "livenessProbe":
                    liveness_missing += 1
                elif probe_type == "readinessProbe":
                    readiness_missing += 1

        if missing:
            missing_summary.append(f"{owner} - {pod_name} - {container_name}: Missing {', '.join(missing)}")

        owners[owner][pod_name].append([container_name, startup, liveness, readiness])

# Create PDF
pdf = ProbePDF()
pdf.add_page()

pdf.section_title("Report Overview")
pdf.set_font("Arial", '', 11)
pdf.cell(0, 8, f"Cluster: {cluster_name}", ln=True)
pdf.cell(0, 8, f"Namespace: {namespace}", ln=True)
pdf.cell(0, 8, f"Total Owners: {len(seen_owners)}", ln=True)
pdf.cell(0, 8, f"Total Pods: {len(pod_data.get('items', []))}", ln=True)
pdf.cell(0, 8, f"Total Containers: {all_containers}", ln=True)
pdf.cell(0, 8, f"Report Timestamp: {datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}", ln=True)

# Explanation
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

# Owner-pod breakdown
for owner, pods in owners.items():
    pdf.add_page()
    pdf.section_title(f"Owner: {owner}")
    for pod_name, containers in pods.items():
        pdf.pod_title(pod_name)
        pdf.write_table(["Container", "Startup", "Liveness", "Readiness"], containers)

out_path = f"probe_report_{namespace}_summary.pdf"
pdf.output(out_path)
print(f"Report saved to {out_path}")