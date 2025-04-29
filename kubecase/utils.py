"""
utils.py

Common utility functions for KubeCase.

Author: Rey Linares
Created: 2023-10-01
"""

import subprocess
import json
import importlib.resources

def run_kubectl(cmd, timeout_seconds=10, parse_json=True):
    """
    Safely runs a kubectl command.

    Args:
        cmd (list): List of kubectl command arguments (e.g., ["kubectl", "get", "pods", ...]).
        timeout_seconds (int): Time limit for command execution.
        parse_json (bool): Whether to parse the output as JSON or return raw text.

    Returns:
        dict or str:
            - If parse_json=True: returns parsed JSON dictionary ({} if failed).
            - If parse_json=False: returns raw stdout string ("" if failed).

    Example:
        >>> run_kubectl(["kubectl", "get", "pods", "-n", "mynamespace", "-o", "json"])
        { "items": [...] }

        >>> run_kubectl(["kubectl", "config", "current-context"], parse_json=False)
        "my-cluster-context"
    """
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=timeout_seconds)
        output = result.stdout.strip()

        if parse_json:
            return json.loads(output)
        else:
            return output

    except subprocess.CalledProcessError as e:
        print(f"❌ Kubectl command failed: {e}")
    except subprocess.TimeoutExpired:
        print(f"❌ Kubectl command timed out after {timeout_seconds} seconds.")
    except json.JSONDecodeError:
        if parse_json:
            print(f"❌ Kubectl output was not valid JSON.")
    return {} if parse_json else ""

def get_current_context():
    """
    Get the current Kubernetes context.

    Returns:
        str: Current context name. Returns an empty string if an error occurs.
    """
    cmd = ["kubectl", "config", "current-context"]
    return run_kubectl(cmd, parse_json=False)

def get_pods(namespace):
    """
    Fetch all pods in the specified namespace.

    Args:
        namespace (str): Kubernetes namespace name.

    Returns:
        List[dict]: List of pod objects from the namespace. Returns an empty list if an error occurs.
    """
    cmd = ["kubectl", "get", "pods", "-n", namespace, "-o", "json"]
    data = run_kubectl(cmd)
    return data.get("items", [])

def get_pdbs(namespace):
    """
    Fetch all Pod Disruption Budgets (PDBs) in the specified namespace.

    Args:
        namespace (str): Kubernetes namespace name.

    Returns:
        List[dict]: List of PDB objects from the namespace. Returns an empty list if an error occurs.
    """
    cmd = ["kubectl", "get", "pdb", "-n", namespace, "-o", "json"]
    data = run_kubectl(cmd)
    return data.get("items", [])

def get_total_owners(pods_list):
    """
    Count the number of unique owners for a list of pods.

    Args:
        pods_list (List[dict]): List of pod objects.

    Returns:
        int: Number of unique owners.
    """
    
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

def get_font_path(font_filename: str) -> str:
    """
    Safely get the path to a bundled font file inside the kubecase/fonts/ directory.
    Works in editable installs and in packaged installs.
    """
    font_path = importlib.resources.files("kubecase").joinpath(f"fonts/{font_filename}")
    return str(font_path)

def get_asset_path(asset_filename: str) -> str:
    """
    Safely get the path to a bundled asset file inside the kubecase/assets/ directory.
    """
    asset_path = importlib.resources.files("kubecase").joinpath(f"assets/{asset_filename}")
    return str(asset_path)