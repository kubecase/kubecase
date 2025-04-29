# main.py
import typer
from kubecase import VERSION, generate_pdb_report, generate_probe_report, generate_resource_report

app = typer.Typer(help="KubeCase - Kubernetes Troubleshooting Reports")
app = typer.Typer(
    help="KubeCase CLI - Live Kubernetes Troubleshooting and Reporting for Kubernetes Clusters",
    add_completion=False
)

@app.command()
def version():
    """
    Show current KubeCase CLI version.
    """
    typer.echo("🕵️‍♂️ KubeCase CLI")
    typer.echo(f"Version: {VERSION}")

@app.command()
def generate(
    namespace: str = typer.Option(..., "-n", "--namespace", help="Namespace to analyze"),
    report: str = typer.Option(..., "-r", "--report", help="Type of report: probe, resource, pdb"),
):
    """
    Generate a troubleshooting report.
    """
    if report == "pdb":
        typer.echo(f"📋 Generating KubeCase Pod Disruption Budget Report for namespace '{namespace}'...")
        generate_pdb_report.run(namespace)
    elif report == "probe":
        typer.echo(f"📋 Generating KubeCase Probe Report for namespace '{namespace}'...")
        generate_probe_report.run(namespace)
    elif report == "resource":
        typer.echo(f"📋 Generating KubeCase Resource Report for namespace '{namespace}'...")
        generate_resource_report.run(namespace)
    else:
        typer.secho(f"❌ Unknown report type: {report}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

@app.command()
def list_reports():
    """
    List all available report types.
    """
    typer.echo("🗂️  Available Reports:")
    typer.echo(" probe    ➔ Probe Report Coverage")
    typer.echo(" resource ➔ Resource Report Coverage")
    typer.echo(" pdb      ➔ Pod Disruption Budget Coverage")


if __name__ == "__main__":
    app()
