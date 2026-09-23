from contextlib import nullcontext
from pathlib import Path

import pytest

from test_api_drawing import EMPTY


@pytest.mark.parametrize('after_id', [42, 7, None])
def test_read_batches_post_read_identity_and_metadata_without_losing_target_guard(after_id):
    from chemdraw_macos.addin import read_document
    events = []

    class Bridge:
        lock = nullcontext()

        def _id(self, did):
            return did

        def _run(self, operation):
            events.append(operation)
            if operation == 'active_document':
                return 42
            assert operation == 'active_document_state'
            return [after_id, 'Test', '', True, 0] if after_id is not None else None

        def documents(self):
            pytest.fail('Separate document enumeration is unnecessary')

    class Channel:
        def request(self, operation):
            events.append('api_' + operation)
            return {'cdxml': EMPTY}

    if after_id == 42:
        result = read_document(Bridge(), Channel(), 42)
        assert result['document'] == {'document_id': 42, 'name': 'Test', 'file': '',
                                       'modified': True, 'molecule_count': 0}
    else:
        with pytest.raises(RuntimeError, match='Active document changed'):
            read_document(Bridge(), Channel(), 42)
    assert events == ['active_document', 'api_read', 'active_document_state']


def test_state_operation_checks_identity_after_gathering_metadata_without_activation():
    script = Path('chemdraw_macos/native.applescript').read_text()
    assert 'if operation is "active_document_state" then' in script
    branch = script.split('if operation is "active_document_state" then')[1].split('end if')[0]
    assert 'my documentRow(document 1)' in branch
    assert 'item 1 of stateRow' in branch
    assert 'activate' not in branch
