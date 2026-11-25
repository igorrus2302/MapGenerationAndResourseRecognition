"""Build empty current-schema CSV and XLSX templates for manual observations."""
from __future__ import annotations

import csv
import sys
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZIP_STORED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from geo_map.observations import TABLE_FIELDS

DESTINATION = ROOT / 'templates/observations/manual'
NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
REL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
PACKAGE = 'http://schemas.openxmlformats.org/package/2006/relationships'


def column_name(index: int) -> str:
    result = ''
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def sheet_xml(rows: list[list[str]]) -> str:
    xml_rows = []
    for i, row in enumerate(rows, 1):
        cells = ''.join(f'<c r="{column_name(j)}{i}" t="inlineStr"><is><t>{escape(v)}</t></is></c>'
                        for j, v in enumerate(row, 1))
        xml_rows.append(f'<row r="{i}">{cells}</row>')
    return f'<worksheet xmlns="{NS}"><sheetData>{"".join(xml_rows)}</sheetData></worksheet>'


def main() -> None:
    DESTINATION.mkdir(parents=True, exist_ok=True)
    for name, fields in TABLE_FIELDS.items():
        with (DESTINATION / f'{name}.csv').open('w', encoding='utf-8', newline='') as stream:
            csv.writer(stream).writerow(fields)
    sheets = [('Instructions', [
        ['Заполняйте только нужные листы, не изменяя заголовки.'],
        ['campaign_id должен совпадать с идентификатором текущей экспедиции.'],
        ['Числа и даты: десятичная точка, YYYY-MM-DD. Неизвестные необязательные значения — пустые клетки.'],
        ['Загрузите книгу в соответствующем разделе; для нескольких разделов выберите импорт полного пакета.'],
    ])] + [(name, [fields]) for name, fields in TABLE_FIELDS.items()]
    overrides = ''.join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                        for i in range(1, len(sheets) + 1))
    names = ''.join(f'<sheet name="{escape(name)}" sheetId="{i}" r:id="rId{i}"/>'
                    for i, (name, _) in enumerate(sheets, 1))
    relationships = ''.join(f'<Relationship Id="rId{i}" Type="{REL}/worksheet" Target="worksheets/sheet{i}.xml"/>'
                            for i in range(1, len(sheets) + 1))
    # Stored ZIP entries also work in browsers without deflate-raw support;
    # standard, compressed Excel exports are supported by the same importer.
    with ZipFile(DESTINATION / 'manual_observations.xlsx', 'w', ZIP_STORED) as book:
        book.writestr('[Content_Types].xml', '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                      '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                      '<Default Extension="xml" ContentType="application/xml"/>'
                      '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                      +overrides+'</Types>')
        book.writestr('_rels/.rels', f'<Relationships xmlns="{PACKAGE}"><Relationship Id="rId1" Type="{REL}/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        book.writestr('xl/workbook.xml', f'<workbook xmlns="{NS}" xmlns:r="{REL}"><sheets>{names}</sheets></workbook>')
        book.writestr('xl/_rels/workbook.xml.rels', f'<Relationships xmlns="{PACKAGE}">{relationships}</Relationships>')
        for i, (_, rows) in enumerate(sheets, 1):
            book.writestr(f'xl/worksheets/sheet{i}.xml', sheet_xml(rows))


if __name__ == '__main__':
    main()
