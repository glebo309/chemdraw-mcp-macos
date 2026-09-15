from pathlib import Path


def test_native_export_refuses_untitled_before_any_save():
    script=(Path(__file__).parents[1]/'chemdraw_macos/native.applescript').read_text()
    export=script.split('else if operation is "export" then',1)[1].split('else if operation is "clean"',1)[0]
    assert 'diskPath' in export
    assert 'Untitled document' in export
    assert export.index('Untitled document') < export.index('save targetDoc')
