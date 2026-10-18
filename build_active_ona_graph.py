"""
Active ONA: построение графов рабочих связей из CSV.

Рядом со скриптом должен лежать файл active_ona_edges_3cols.csv
с тремя столбцами: respondent_email, target_email, relationship_type.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd
from matplotlib.lines import Line2D


# Все файлы проекта находятся в папке со скриптом.
BASE_DIR = Path(__file__).resolve().parent
INPUT_FILE = BASE_DIR / "active_ona_edges_3cols.csv"
OUTPUT_DIR = BASE_DIR / "ona_graphs"

# Цвета типов связей на графике.
COLORS = {
    "Экспертный совет": "#2878B5",
    "Решение сложной проблемы": "#E07A2D",
    "Рабочее взаимодействие": "#2F8F5B",
    "Источник информации": "#9A63B5",
}

# Названия файлов для отдельных графиков.
FILE_NAMES = {
    "Экспертный совет": "ona_network_advice.png",
    "Решение сложной проблемы": "ona_network_problem_solving.png",
    "Рабочее взаимодействие": "ona_network_work.png",
    "Источник информации": "ona_network_information.png",
}


def load_data():
    """Читает CSV и проверяет, что в нём есть нужные столбцы и данные."""
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Не найден файл: {INPUT_FILE.name}. "
            "Положите CSV рядом со скриптом."
        )

    df = pd.read_csv(INPUT_FILE, encoding="utf-8-sig", dtype=str)
    required = ["respondent_email", "target_email", "relationship_type"]

    missing = set(required) - set(df.columns)
    if missing:
        raise ValueError(f"В CSV отсутствуют столбцы: {', '.join(sorted(missing))}")

    # Убираем пробелы, пустые строки и приводим email к одному регистру.
    df = df[required].fillna("")
    for column in required:
        df[column] = df[column].str.strip()

    df["respondent_email"] = df["respondent_email"].str.lower()
    df["target_email"] = df["target_email"].str.lower()
    df = df[(df[required] != "").all(axis=1)]

    # Самовыбор не имеет смысла для этой схемы.
    df = df[df["respondent_email"] != df["target_email"]]

    if df.empty:
        raise ValueError("В CSV не осталось строк для построения графа.")

    return df


def short_name(email):
    """Для читаемости показываем на графике часть email до @."""
    return email.split("@")[0].replace(".", "\n")


def draw_graph(graph, positions, title, output_file, edge_color=None, all_types=None):
    """Рисует граф и сохраняет его в PNG."""
    nodes = list(graph.nodes)
    incoming = dict(graph.in_degree())
    max_incoming = max(incoming.values(), default=1)

    # Чем больше входящих выборов, тем крупнее узел.
    sizes = [220 + 900 * incoming[node] / max_incoming for node in nodes]

    plt.figure(figsize=(14, 11))
    nx.draw_networkx_nodes(
        graph, positions,
        node_size=sizes,
        node_color="#DCE8F2",
        edgecolors="#38566F",
        linewidths=0.7,
    )

    if all_types is not None:
        # В общем графе цвет линии зависит от типа отношения.
        curve = {
            "Экспертный совет": -0.16,
            "Решение сложной проблемы": -0.05,
            "Рабочее взаимодействие": 0.05,
            "Источник информации": 0.16,
        }

        for rel_type, edges in all_types.items():
            nx.draw_networkx_edges(
                graph, positions,
                edgelist=edges,
                edge_color=COLORS.get(rel_type, "#777777"),
                width=0.8,
                alpha=0.6,
                arrows=True,
                arrowsize=8,
                connectionstyle=f"arc3,rad={curve.get(rel_type, 0)}",
            )

        legend = [
            Line2D([0], [0], color=COLORS.get(t, "#777777"), lw=2.5, label=t)
            for t in all_types
        ]
        plt.legend(handles=legend, loc="upper left", fontsize=8)
    else:
        # В графе одного типа все связи имеют один цвет.
        nx.draw_networkx_edges(
            graph, positions,
            edge_color=edge_color or "#2878B5",
            width=1.0,
            alpha=0.65,
            arrows=True,
            arrowsize=9,
        )

    labels = {node: short_name(node) for node in nodes}
    nx.draw_networkx_labels(graph, positions, labels=labels, font_size=6)

    plt.title(title)
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(output_file, dpi=180, bbox_inches="tight")
    plt.close()


def main():
    df = load_data()
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Общий граф объединяет все типы связей. Стрелка идёт от респондента
    # к выбранному им коллеге.
    graph = nx.from_pandas_edgelist(
        df,
        source="respondent_email",
        target="target_email",
        create_using=nx.DiGraph(),
    )

    # Единое расположение узлов помогает сравнивать разные типы связей.
    positions = nx.spring_layout(graph, seed=42, iterations=150)

    relationship_types = sorted(df["relationship_type"].unique())
    edges_by_type = {}

    for rel_type in relationship_types:
        rows = df[df["relationship_type"] == rel_type]
        edges_by_type[rel_type] = list(
            rows[["respondent_email", "target_email"]]
            .drop_duplicates()
            .itertuples(index=False, name=None)
        )

    # Сохраняем общую схему.
    draw_graph(
        graph,
        positions,
        f"Active ONA — общая сеть ({graph.number_of_nodes()} сотрудников)",
        OUTPUT_DIR / "ona_network_combined.png",
        all_types=edges_by_type,
    )

    # Сохраняем по отдельной схеме для каждого типа связи.
    for rel_type in relationship_types:
        layer = nx.DiGraph()
        layer.add_nodes_from(graph.nodes)
        layer.add_edges_from(edges_by_type[rel_type])

        output_name = FILE_NAMES.get(
            rel_type, f"ona_network_type_{relationship_types.index(rel_type) + 1}.png"
        )
        draw_graph(
            layer,
            positions,
            f"Active ONA — {rel_type}",
            OUTPUT_DIR / output_name,
            edge_color=COLORS.get(rel_type, "#777777"),
        )

    print(f"Обработано строк: {len(df)}")
    print(f"Сотрудников в сети: {graph.number_of_nodes()}")
    print(f"Типов связи: {len(relationship_types)}")
    print(f"Графики сохранены в папке: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
