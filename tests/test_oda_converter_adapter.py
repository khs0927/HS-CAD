from pathlib import Path

from src.converters.oda_file_converter import ConversionResult, ODAFileConverter


def test_oda_converter_reports_unavailable_when_missing(tmp_path: Path):
    converter = ODAFileConverter(executable=tmp_path / 'missing.exe')
    ok, reason = converter.is_available()
    assert ok is False
    assert 'not found' in reason


def test_oda_converter_command_shape(tmp_path: Path):
    exe = tmp_path / 'ODAFileConverter.exe'
    exe.write_text('', encoding='utf-8')
    converter = ODAFileConverter(executable=exe)
    command = converter._build_command(Path('in'), Path('out'))
    assert command[0] == str(exe)
    assert 'ACAD2018' in command
    assert 'DXF' in command


def test_conversion_result_to_dict():
    result = ConversionResult(True, 'oda_file_converter', 'a.dwg', 'a.dxf', ['cmd'])
    payload = result.to_dict()
    assert payload['ok'] is True
    assert payload['engine'] == 'oda_file_converter'
