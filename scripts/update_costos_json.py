import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MONTH_JSON = os.path.join(ROOT, "costos_septiembre.json")
COSTOS_JSON = os.path.join(ROOT, "costos", "src", "assets", "data", "costos.json")

GK_TO_SK = {
    "Desarrollo": "Desarrollo",
    "Ambiente QA": "QA",
    "Producción": "Producción",
}
ENV_TO_GK = {
    "Desarrollo": "Desarrollo",
    "QA": "Ambiente QA",
    "Producción": "Producción",
}

SUFFIXES = [" account", " workspace", " topic", " (v2)", " cache", " service"]


def normalize(name: str) -> str:
    n = name.strip().lower()
    for suf in SUFFIXES:
        if n.endswith(suf):
            n = n[: -len(suf)]
    n = re.sub(r"[^a-z0-9]+", "", n)
    return n


def main() -> None:
    with open(MONTH_JSON, encoding="utf-8") as f:
        month_data = json.load(f)

    with open(COSTOS_JSON, encoding="utf-8") as f:
        costos = json.load(f)

    idx = month_data["month_index"]
    year = "2026"

    costos["meta"]["lastData2026"] = idx
    costos["meta"]["status2026"][idx] = "full"

    for env_name, env_data in month_data["environments"].items():
        gk = ENV_TO_GK[env_name]
        sk = GK_TO_SK[gk]

        costos["general"][year][gk][idx] = env_data["total"]

        rows = costos["services"][sk][year]
        rows_by_norm = {normalize(r["name"]): r for r in rows}

        for service_name, cost in env_data["services"].items():
            norm = normalize(service_name)
            row = rows_by_norm.get(norm)
            if row is None:
                row = {
                    "name": service_name,
                    "values": [0.0] * 12,
                    "total": 0.0,
                }
                rows.append(row)
                rows_by_norm[norm] = row
            row["values"][idx] = cost
            row["total"] = round(sum(row["values"]), 2)

    with open(COSTOS_JSON, "w", encoding="utf-8") as f:
        json.dump(costos, f, ensure_ascii=False, separators=(",", ":"))

    print(f"Updated {COSTOS_JSON} with September ({idx}) data.")


if __name__ == "__main__":
    main()
