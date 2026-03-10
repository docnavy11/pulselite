import csv


def extract_from_csv(file_path: str) -> str:
    rows = []
    with open(file_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        header_line = ", ".join(headers)
        for row in reader:
            row_text = ", ".join(f"{k}: {v}" for k, v in row.items() if v != "")
            if row_text:
                rows.append(row_text)
    if not rows:
        return ""
    return header_line + "\n" + "\n".join(rows)
