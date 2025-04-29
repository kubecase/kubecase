# main.py

import typer
from kubecase import generate_pdb_report

app = typer.Typer(help="KubeCase - Kubernetes Troubleshooting Reports")

@app.command()
def generate(
    namespace: str = typer.Option(..., "-n", "--namespace", help="Namespace to analyze"),
    report: str = typer.Option(..., "-r", "--report", help="Type of report: probe, resource, pdb"),
):
    """
    Generate a troubleshooting report.
    """
    
    if report == "pdb":
        typer.echo(f"📋 Generating Pod Disruption Budget Report for namespace '{namespace}'...")
        generate_pdb_report.run(namespace)
    else:
        typer.secho(f"❌ Unknown report type: {report}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

if __name__ == "__main__":
    app()
