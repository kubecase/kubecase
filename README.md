# 🕵️‍♂️ KubeCase

**Sniffing configs, one line at a time**  

![KubeCase Mascot](mascot.png)

---

## 📌 What is KubeCase?

**KubeCase** is your Kubernetes detective assistant. It is built to sniff out misconfigurations, report on health, and make troubleshooting faster and smarter. It delivers actionable insights into workload health through clean, readable reports with the flair of a golden doodle detective on the case. 🐶

---

## ✨ Features (v2.0)

### 🔍 Probe Report (PDF)
- Analyzes **startup**, **liveness**, and **readiness** probes
- Breaks down timing logic: initial delay and runtime sensitivity
- Highlights missing probes and aggressive configurations
- Includes cluster name, namespace, and summary
- Beautiful PDF layout with mascot, tables, and analysis

### 📊 Resource Requests & Limits Report (NEW!)
- **Namespace-wide quota summary**: shows total CPU, memory, and ephemeral storage allocations vs usage
- **Controller-level breakdown**: aggregates usage by owner (e.g., Deployment, StatefulSet)
- **Container-level insight**: detailed view of requests/limits per container with flags for missing or invalid configs
- **QoS Class analysis**:
  - Pie chart distribution (Guaranteed, Burstable, BestEffort)
  - Executive-friendly explanation of why QoS matters
- **Misconfiguration detection**:
  - CPU request > limit
  - Missing limits/requests
  - Memory request using incorrect `m` suffix (flagged)
- **Color-coded usage highlights** (Yellow ≥ 80%, Red ≥ 90%)
- **Multi-line wrapping support** for long Controller and Container names
- **Smart page breaks** with persistent headers
- **Early exit handling** if namespace has no pods (avoids generating empty reports)

**Coming Soon:**
- 🛡️ Pod Disruption Budget (PDB) Analyzer
- 🔐 RBAC Relationship Viewer
- 🌐 Network Policy Inspector

---

## 📸 Example Output

<p align="center">
  <img src="docs/images/example_probe_cover.png" width="600" alt="Probe Report Sample"/>
</p>
<p align="center">
  <img src="docs/images/example_probe_deployment.png?" width="600" alt="Probe Report Sample"/>
</p>

---

## 🚀 Getting Started

```bash
# Clone the repo
git clone https://github.com/kubecase/kubecase.git
cd kubecase

# Set up environment
python3 -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt

# Run a probe report
python generate_probe_report.py -n my-namespace

# Run a resource report
python generate_resource_report.py -n my-namespace
```

## 🧩 Requirements

    Python 3.8+
    kubectl or oc CLI with access to a Kubernetes cluster
    Permissions to query pod data in the target namespace

## 💡 Vision

KubeCase aims to become the go-to Kubernetes diagnostics toolkit. It combines human-readable reports with deep insights to help:

  - Platform teams keep clusters healthy
  - App teams troubleshoot faster
  - Everyone understand their workloads better

## 👥 Contributing

We welcome contributions, ideas, and collaboration!
Have a feature request or bug report? Open an issue or pull request.

## 📄 License
MIT License © 2025 Rey Linares
