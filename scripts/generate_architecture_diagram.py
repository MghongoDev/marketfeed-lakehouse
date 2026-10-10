"""Generate the project architecture diagram with the Python Diagrams library."""

from pathlib import Path

from diagrams import Cluster, Diagram, Edge
from diagrams.generic.blank import Blank


OUTPUT = Path(__file__).resolve().parents[1] / "docs" / "img" / "architecture.svg"


def node(label: str, color: str) -> Blank:
    return Blank(
        label,
        shape="box",
        style="rounded,filled",
        fillcolor=color,
        color=color,
        fontcolor="#17212b",
        fontsize="12",
        margin="0.22,0.14",
    )


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    with Diagram(
        "MarketFeed Lakehouse",
        filename=str(OUTPUT.with_suffix("")),
        outformat="svg",
        show=False,
        direction="LR",
        graph_attr={
            "bgcolor": "transparent",
            "pad": "0.25",
            "nodesep": "0.55",
            "ranksep": "0.75",
            "splines": "spline",
            "fontname": "Arial",
            "fontsize": "20",
            "fontcolor": "#17212b",
        },
        node_attr={"fontname": "Arial"},
        edge_attr={
            "fontname": "Arial",
            "fontsize": "10",
            "color": "#64748b",
            "fontcolor": "#475569",
            "penwidth": "1.6",
        },
    ):
        with Cluster(
            "External Sources",
            graph_attr={"bgcolor": "#f8fafc", "color": "#cbd5e1", "style": "rounded"},
        ):
            alpha_vantage = node("Alpha Vantage\nEquity prices", "#dbeafe")
            fred = node("FRED\nMacro indicators", "#dbeafe")

        with Cluster(
            "Bronze Ingestion DAG",
            graph_attr={"bgcolor": "#fff7ed", "color": "#fdba74", "style": "rounded"},
        ):
            ingestion = node("Python ingestion\nrequests + pandas", "#ffedd5")
            bronze = node("Bronze\nRaw Parquet\nby ingest date", "#fed7aa")
            quality = node("Freshness gate\nGreat Expectations", "#fef3c7")
            ingestion >> bronze
            bronze >> Edge(label="validate freshness") >> quality

        with Cluster(
            "Transformation DAG",
            graph_attr={"bgcolor": "#f0fdf4", "color": "#86efac", "style": "rounded"},
        ):
            dbt = node("dbt Core\nSnapshots + models\nSilver → Gold", "#dcfce7")
            warehouse = node("DuckDB\nSilver + Gold tables", "#bbf7d0")
            dbt >> warehouse

        consumer = node("SQL consumers\nAnalysts / BI", "#ede9fe")

        alpha_vantage >> ingestion
        fred >> ingestion
        bronze >> Edge(label="Parquet sources") >> dbt
        warehouse >> consumer

        airflow = node("Apache Airflow\nScheduled DAGs", "#e0e7ff")
        airflow >> Edge(
            label="schedules",
            style="dashed",
            color="#6366f1",
            fontcolor="#4f46e5",
            constraint="false",
        ) >> ingestion
        airflow >> Edge(
            style="dashed",
            color="#6366f1",
            constraint="false",
        ) >> quality
        airflow >> Edge(
            style="dashed",
            color="#6366f1",
            constraint="false",
        ) >> dbt


if __name__ == "__main__":
    main()
