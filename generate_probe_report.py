#!/usr/bin/env python3

from datetime import datetime
from dateutil import parser
from collections import defaultdict
from fpdf import FPDF
from fpdf.enums import XPos, YPos
import subprocess
import json
import typer

app = typer.Typer()
version = "1.2.0"

# ------------------------- PDF Class ------------------------- #
class ProbePDF(FPDF):
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
            
    def section_title(self, title):
        self.set_font("Dejavu", 'B', 16)
        self.cell(0, 15, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def pod_title(self, pod_name):
        self.set_font("Dejavu", 'B', 12)
        self.cell(0, 5, f"Pod: {pod_name}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(1)

    def write_table(self, headers, rows):
        col_widths = [40, 30, 30, 30, 25, 40]
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

# ---------------------- Helper Functions ---------------------- #
def get_probe_seconds(probe, probe_type):
    if not probe:
        return None
    delay = probe.get("initialDelaySeconds", 0)
    period = probe.get("periodSeconds", 10)
    successThreshold = probe.get("successThreshold", 1)
    failureThreshold = probe.get("failureThreshold", 3)
    #timeoutSeconds = probe.get("timeoutSeconds", 1)

    # Calculate total runtime for the probe
    startUp_max = delay + period * failureThreshold
    initial_total = delay + period * (successThreshold - 1)
    runtime_total = period * failureThreshold

    if probe_type == "startupProbe":
        return f"{delay}s + {period}s, {startUp_max}s"
    else:
        return f"{initial_total}s, {runtime_total}s"

def get_pod_bootup_duration(pod):
    container_statuses = pod.get("status", {}).get("containerStatuses", [])
    restarts_exist = any(cs.get("restartCount", 0) > 0 for cs in container_statuses)

    if not restarts_exist:
        # Use conditions if no container has restarted
        def extract_time(condition_type):
            for cond in pod.get("status", {}).get("conditions", []):
                if cond["type"] == condition_type and cond["status"] == "True":
                    return cond["lastTransitionTime"]
            return None

        scheduled = extract_time("PodScheduled")
        ready = extract_time("ContainersReady") or extract_time("Ready")

        if scheduled and ready:
            try:
                start = parser.parse(scheduled)
                end = parser.parse(ready)
                return int((end - start).total_seconds())
            except Exception:
                pass
    else:
        # Use runtime timestamps for containers that restarted
        try:
            times = []
            for cs in container_statuses:
                state = cs.get("state", {})
                if "running" in state and "startedAt" in state["running"]:
                    started_at = parser.parse(state["running"]["startedAt"])
                    finished_at = None
                    if "lastState" in cs and "terminated" in cs["lastState"]:
                        finished_at = parser.parse(cs["lastState"]["terminated"]["finishedAt"])
                    if finished_at:
                        duration = (started_at - finished_at).total_seconds()
                        times.append(duration)
            if times:
                return int(max(times))  # Longest recovery time
        except Exception:
            pass

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
            restart_count = 0
            reason = "N/A"
            exit_code = "N/A"

            # Get restart count and last termination reason
            for status in pod.get("status", {}).get("containerStatuses", []):
                if status["name"] == container_name:
                    restart_count = status.get("restartCount", 0)
                    last = status.get("lastState", {})
                    if "terminated" in last:
                        reason = last["terminated"].get("reason", "Terminated")
                        exit_code = last["terminated"].get("exitCode", "N/A")
                    break

            # Add warning icon
            if restart_count > 0:
                restart_display = f"{restart_count} ⚠"
            else:
                restart_display = f"{restart_count}"

            # Format reason with exit code
            if exit_code != "N/A":
                reason_display = f"{reason} (code {exit_code})"
            else:
                reason_display = f"{reason}"

            # Get pod bootup duration and probe durations
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

            owners[owner][pod_name].append([container_name, startup, liveness, readiness, restart_display, reason_display])

    # PDF Generation
    pdf = ProbePDF()
    pdf.add_font("Dejavu", "", "fonts/DejaVuSansCondensed.ttf")
    pdf.add_font("Dejavu", "B", "fonts/DejaVuSansCondensed-Bold.ttf")

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
    pdf.set_font("Dejavu", 'B', 16)
    pdf.cell(0, 20, "\"Sniffing configs, one line at a time\"", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
    pdf.set_font("Dejavu", '', 16)
    pdf.cell(0, 10, f"KubeCase · https://github.com/kubecase/kubecase · v{version}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')


    # Explanation Page
    pdf.add_page()
    pdf.section_title("Purpose")
    pdf.set_font("Dejavu", '', 12)
    pdf.write_paragraph("The purpose of this report is to gather all the probes configured across all containers in your namespace "
        "so you can easily see how long each probe waits before taking action. In this report you will also see restart count "
        " and the reason. Understanding these durations and reasons is critical for troubleshooting delays, crashes, and deployment issues.")
    pdf.section_title("3 Types of Probes")
    pdf.write_paragraph("Startup Probe", font_style='B')
    pdf.write_paragraph("Determines when a container is ready to start receiving traffic.\n"
        "If it fails, the container is restarted and the probe is retried. Readiness and Liveness "
        "probes are disabled until the Startup probe succeeds.\n")
    pdf.write_paragraph("Liveness Probe", font_style='B')
    pdf.write_paragraph("Determines when a container is healthy and should continue running.\n"
        "If it fails, the container is restarted and the probe is retried.\n")
    pdf.write_paragraph("Readiness Probe", font_style='B')
    pdf.write_paragraph("Determines when a container is ready to start serving traffic.\n"
        "If it fails, the container is removed from the service's load balancer.")
    
    pdf.section_title("Probe Timing")
    pdf.write_paragraph("The report is organized by workload owner, then lists each pod and its containers.\n")
    pdf.write_paragraph("Startup Probe:", font_style='B')
    pdf.write_code_block("initialDelay + period, initialDelay + period × failureThreshold")
    pdf.write_paragraph("Liveness and Readiness Probes:", font_style='B')
    pdf.write_code_block("initialDelay + period × (successThreshold - 1), period × failureThreshold")
    pdf.write_paragraph("Probes not configured are shown as '--'. This layout helps identify which probes "
                 "exist, how aggressive they are, and where gaps exist.")
    
    pdf.section_title("Bootup Time")
    pdf.write_paragraph("The time it takes for a pod to start up is shown in 'Bootup Time'. "
                        "This is the time from when the pod is created to when the pod is Ready. If a container "
                         "has restarted, the bootup time is the time from the last restart to when the pod is Ready.\n")
    
    pdf.section_title("Restart Count and Reason")
    pdf.write_paragraph("If a container has restarted, it is marked with a warning icon, and the row is highlighted "
                        "in yellow. The reason is also shown with the exit code.\n")

    # Data Pages
    for owner, pods in owners.items():
        pdf.add_page()
        pdf.section_title(f"Owner: {owner}")
        for pod_name, containers in pods.items():
            # Get pod object to extract conditions
            pod_obj = next((p for p in pod_data["items"] if p["metadata"]["name"] == pod_name), None)
            if pod_obj:
                bootup_time = get_pod_bootup_duration(pod_obj)
                bootup_str = f"{bootup_time}s" if bootup_time is not None else "Pending or Unknown"
            else:
                bootup_str = "Unavailable"

            pdf.pod_title(pod_name)
            pdf.set_font("Dejavu", '', 12)
            pdf.cell(0, 5, f"Bootup Time: {bootup_str}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(1)

            # Table
            pdf.write_table(["Container", "Startup", "Liveness", "Readiness", "Restarts", "Reason"], containers)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out_path = f"probe_report_{namespace}_{timestamp}.pdf"
    pdf.output(out_path)
    typer.echo(f"✅ KubeCase Probe Report saved to {out_path}")

if __name__ == "__main__":
    app()
