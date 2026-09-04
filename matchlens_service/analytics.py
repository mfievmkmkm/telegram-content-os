from __future__ import annotations

import math



def player_report(points: list[list[float]] | list[tuple[float, float, float]], duration: float) -> dict:
    if not points:
        return {}
    distances = []
    for left, right in zip(points, points[1:]):
        dt = max(.001, right[0] - left[0])
        distance = math.hypot(right[1] - left[1], right[2] - left[2])
        distances.append((distance / dt, right[0]))
    visible = max(.25, len(points) / 4)
    movement = sum(speed for speed, _ in distances)
    zones = {
        "left": sum(p[1] < 1 / 3 for p in points),
        "centre": sum(1 / 3 <= p[1] <= 2 / 3 for p in points),
        "right": sum(p[1] > 2 / 3 for p in points),
        "upper": sum(p[2] < 1 / 3 for p in points),
        "middle": sum(1 / 3 <= p[2] <= 2 / 3 for p in points),
        "lower": sum(p[2] > 2 / 3 for p in points),
    }
    bursts = sorted(distances, reverse=True)[:5]
    share = min(100.0, visible / max(.25, duration) * 100)
    confidence = "high" if share >= 45 and len(points) >= 80 else "medium" if share >= 20 else "low"
    return {
        "visible_seconds": round(visible, 1),
        "visibility_percent": round(share, 1),
        "movement_index": round(movement * 100, 1),
        "average_x": round(sum(p[1] for p in points) / len(points), 3),
        "average_y": round(sum(p[2] for p in points) / len(points), 3),
        "zones_percent": {key: round(value / len(points) * 100, 1) for key, value in zones.items()},
        "burst_timestamps": [round(timestamp, 1) for _, timestamp in bursts],
        "confidence": confidence,
    }


def coach_notes(report: dict) -> list[str]:
    if not report:
        return ["Недостаточно кадров для содержательного отчёта"]
    notes = []
    zones = report["zones_percent"]
    horizontal = max(("левом фланге", zones["left"]), ("центральном коридоре", zones["centre"]), ("правом фланге", zones["right"]), key=lambda item: item[1])
    notes.append(f"Чаще всего игрок появляется в {horizontal[0]} — {horizontal[1]}% видимых кадров")
    notes.append(f"Видимость игрока в записи: {report['visibility_percent']}%; уверенность отчёта — {report['confidence']}")
    if report["burst_timestamps"]:
        moments = ", ".join(f"{int(t // 60)}:{int(t % 60):02d}" for t in report["burst_timestamps"][:3])
        notes.append(f"Самые интенсивные перемещения: {moments}")
    notes.append("Movement index — относительная видеооценка, а не GPS-дистанция")
    return notes
