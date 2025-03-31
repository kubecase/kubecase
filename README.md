# 🕵️‍♂️ KubeCase

**Sniffing configs, one line at a time**  

![KubeCase Mascot](mascot.png)

---

## 📌 What is KubeCase?

**KubeCase** is your Kubernetes detective assistant — built to sniff out misconfigurations, report on health, and make troubleshooting faster and smarter. It delivers actionable insights into workload health through clean, readable reports — with the flair of a golden doodle detective on the case. 🐶

---

## ✨ Features (v1.0)

### 🔍 Probe Report (PDF)
- Analyzes **startup**, **liveness**, and **readiness** probes
- Breaks down timing logic: initial delay and runtime sensitivity
- Highlights missing probes and aggressive configurations
- Includes cluster name, namespace, and summary
- Beautiful PDF layout with mascot, tables, and analysis

**Coming Soon:**
- 🧠 Resource Requests & Limits Report
- 🛡️ Pod Disruption Budget (PDB) Analyzer
- 📊 Resource Quota Visualizer
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
python3 src/generate_probe_report.py -n my-namespace
```

## 🧩 Requirements

    Python 3.8+
    kubectl or oc CLI with access to a Kubernetes cluster
    Permissions to query pod data in the target namespace

## 💡 Vision

KubeCase aims to become the go-to Kubernetes diagnostics toolkit — combining human-readable reports with deep insights to help:

  - Platform teams keep clusters healthy
  - App teams troubleshoot faster
  - Everyone understand their workloads better

## 👥 Contributing

We welcome contributions, ideas, and collaboration!
Have a feature request or bug report? Open an issue or pull request.

## 📄 License
MIT License © 2025 Rey Linares