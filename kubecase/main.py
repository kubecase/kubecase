# main.py
import typer
from kubecase import VERSION, generate_pdb_report, generate_probe_report, generate_resource_report

app = typer.Typer(
    help="KubeCase CLI - Live Kubernetes Troubleshooting and Reporting Assistant for Kubernetes Clusters",
    add_completion=False,
    context_settings={"help_option_names": ["-h", "--help"]}
)

get_app = typer.Typer(help="Generate reports for current cluster state")

@app.command()
def version():
    """
    Show current KubeCase CLI version.
    """
    typer.echo("🕵️‍♂️ KubeCase CLI")
    typer.echo(f"Version: {VERSION}")

# Add subcommands
app.add_typer(get_app, name="get")

@get_app.command("probe")
def get_probe(namespace: str = typer.Option(..., "-n", "--namespace", help="Target namespace")):
    """Generate a Probe Report"""
    generate_pdb_report.run(namespace)

@get_app.command("resource")
def get_resource(namespace: str = typer.Option(..., "-n", "--namespace", help="Target namespace")):
    """Generate a Resource Usage Report"""
    generate_resource_report.run(namespace)

@get_app.command("pdb")
def get_pdb(namespace: str = typer.Option(..., "-n", "--namespace", help="Target namespace")):
    """Generate a Pod Disruption Budget Report"""
    generate_pdb_report.run(namespace)


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
