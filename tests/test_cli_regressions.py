from click.testing import CliRunner
from openpyxl import Workbook
from proofcheck.cli import cli, _parse_pages


def test_inspect_respects_sheet_and_header(tmp_path):
    wb=Workbook(); wb.active.title='Delegates'; wb.active.append(['Title']); wb.active.append(['Name'])
    wb.create_sheet('Other').append(['Ignore'])
    path=tmp_path/'book.xlsx'; wb.save(path)
    result=CliRunner().invoke(cli,['inspect',str(path),'--header-row','2','--sheet','Delegates'])
    assert result.exit_code == 0 and '[Delegates]: Name' in result.output and '[Other]' not in result.output


def test_range_parser_bounds_before_expanding():
    assert _parse_pages('1-999999999999999999,0,99',3) == [1,2,3]


def test_report_cannot_overwrite_inputs(excel_path,pdf_path):
    result=CliRunner().invoke(cli,['check',excel_path,pdf_path,'--column','Name','--xlsx',excel_path])
    assert result.exit_code == 2 and 'overwrite' in result.output
