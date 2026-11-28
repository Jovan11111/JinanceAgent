import uuid
from datetime import datetime

from config import Config


class GraphTool:
    """Draw one chart with matplotlib and save it under db/images."""

    name = "create_chart"
    description = (
        "Create a line, bar, or pie chart and show it in the chat. "
        "labels and values must be the same length. "
        "Use this whenever the user wants a graph or a visual comparison."
    )

    def spec(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Chart title."},
                        "chart_type": {
                            "type": "string",
                            "enum": ["line", "bar", "pie"],
                            "description": "Chart type.",
                        },
                        "labels": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "X-axis labels, or slice labels for a pie chart.",
                        },
                        "values": {
                            "type": "array",
                            "items": {"type": "number"},
                            "description": "One number per label.",
                        },
                        "series_name": {"type": "string", "description": "Legend label."},
                        "x_label": {"type": "string"},
                        "y_label": {"type": "string"},
                    },
                    "required": ["title", "chart_type", "values"],
                },
            },
        }

    def run(
        self,
        title: str,
        chart_type: str,
        values: list,
        labels: list | None = None,
        series_name: str = "",
        x_label: str = "",
        y_label: str = "",
    ) -> dict:
        chart_type = (chart_type or "").strip().lower()
        if chart_type not in {"line", "bar", "pie"}:
            return _fail("chart_type must be line, bar, or pie.")
        numbers = _numbers(values)
        if numbers is None:
            return _fail("values must be a list of numbers.")
        if not numbers or len(numbers) > 500:
            return _fail("values must contain between 1 and 500 numbers.")
        names = [str(item) for item in labels] if labels else [str(i + 1) for i in range(len(numbers))]
        if len(names) != len(numbers):
            return _fail("labels and values must be the same length.")
        if chart_type == "pie" and any(number < 0 for number in numbers):
            return _fail("Pie charts need zero or positive values.")

        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        filename = f"chart_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.png"
        path = Config.IMAGES_DIR / filename
        figure, axes = plt.subplots(figsize=(8, 4.5), dpi=120)
        try:
            _style(figure, axes)
            color = "#3DDC84"
            if chart_type == "pie":
                colors = [_PIE_COLORS[i % len(_PIE_COLORS)] for i in range(len(numbers))]
                axes.pie(numbers, labels=names, colors=colors, textprops={"color": "#E7E8EA"})
            elif chart_type == "bar":
                axes.bar(names, numbers, color=color, label=series_name or None)
            else:
                axes.plot(names, numbers, color=color, linewidth=2, label=series_name or None)
            if chart_type != "pie":
                if x_label:
                    axes.set_xlabel(x_label)
                if y_label:
                    axes.set_ylabel(y_label)
                if len(names) > 6:
                    axes.tick_params(axis="x", labelrotation=35)
                    for tick in axes.get_xticklabels():
                        tick.set_ha("right")
                axes.grid(True, color="#2A2E35", linewidth=0.6)
                axes.set_axisbelow(True)
            if series_name and chart_type != "pie":
                legend = axes.legend(facecolor="#141618", edgecolor="#2A2E35", labelcolor="#E7E8EA")
                if legend is not None:
                    legend.get_frame().set_linewidth(0.6)
            axes.set_title(title or "Chart", color="#F2F2F2")
            figure.tight_layout()
            figure.savefig(path, bbox_inches="tight", facecolor=figure.get_facecolor())
        finally:
            plt.close(figure)

        return {
            "content": (
                f"Chart saved as {filename}. The user can see the image in the chat. "
                "Describe what it shows."
            ),
            "images": [filename],
            "files": [],
        }


_PIE_COLORS = ["#3DDC84", "#8FBF9F", "#D0D4DA", "#5C8F6E", "#C7E8D4", "#6E7681", "#245C3A", "#B7C4B8"]


def _numbers(values) -> list[float] | None:
    if not isinstance(values, list):
        return None
    numbers = []
    for value in values:
        try:
            numbers.append(float(value))
        except (TypeError, ValueError):
            return None
    return numbers


def _style(figure, axes):
    figure.patch.set_facecolor("#121417")
    axes.set_facecolor("#121417")
    axes.tick_params(colors="#D0D4DA")
    axes.xaxis.label.set_color("#D0D4DA")
    axes.yaxis.label.set_color("#D0D4DA")
    for spine in axes.spines.values():
        spine.set_color("#2A2E35")


def _fail(content: str) -> dict:
    return {"content": content, "images": [], "files": []}
