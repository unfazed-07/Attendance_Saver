from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from io import BytesIO


@dataclass(frozen=True)
class AttendanceRow:
    course_code: str
    course_name: str
    total_delivered: int
    total_attended: int
    duty_leave: int = 0
    first_week_bonus: int = 0
    reported_percentage: int = 0

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def parse_attendance_image(file_bytes: bytes, endpoint: str, key: str) -> list[AttendanceRow]:
    if not endpoint or not key:
        raise RuntimeError("Azure AI Document Intelligence is not configured. Set AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT and AZURE_DOCUMENT_INTELLIGENCE_KEY.")
    from azure.ai.documentintelligence import DocumentIntelligenceClient
    from azure.core.credentials import AzureKeyCredential

    client = DocumentIntelligenceClient(endpoint=endpoint, credential=AzureKeyCredential(key))
    poller = client.begin_analyze_document("prebuilt-layout", body=BytesIO(file_bytes))
    result = poller.result()
    rows: dict[int, dict[int, str]] = {}
    for table in result.tables or []:
        for cell in table.cells:
            rows.setdefault(cell.row_index, {})[cell.column_index] = str(cell.content or "").strip()

    return parse_document_rows(rows)


def parse_document_rows(rows: dict[int, dict[int, str]]) -> list[AttendanceRow]:
    parsed: list[AttendanceRow] = []
    for row_index in sorted(rows):
        cells = rows[row_index]
        if len(cells) < 6:
            continue
        course_cell = cells.get(0, "")
        if "aggregate attendance" in course_cell.lower() or "course" == course_cell.strip().lower():
            continue
        split = re.match(r"^\s*([A-Z]{3}\d{3})\s*:\s*(.*?)\s*$", course_cell, re.IGNORECASE)
        if not split:
            split = re.match(r"^\s*([A-Z]{3}\d{3})\s+(.*?)\s*$", course_cell, re.IGNORECASE)
        if not split:
            continue
        nums = []
        for index in range(1, 6):
            number = re.search(r"\d+", cells.get(index, "0"))
            nums.append(int(number.group(0)) if number else 0)
        parsed.append(AttendanceRow(split.group(1).upper(), split.group(2).strip(), *nums[:4], reported_percentage=nums[4]))
    if not parsed:
        raise ValueError("Document Intelligence did not find course rows in the expected six-column attendance table.")
    return parsed
