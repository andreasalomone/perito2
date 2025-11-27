import io
import pytest
from services import docx_generator_salomone

def test_salomone_generator_execution():
    """
    Test that the Salomone generator can actually generate a DOCX file
    without crashing.
    """
    content = "Test report content.\nLine 2.\n"
    
    try:
        file_stream = docx_generator_salomone.create_styled_docx(content)
        assert isinstance(file_stream, io.BytesIO)
        assert file_stream.getbuffer().nbytes > 0
    except Exception as e:
        pytest.fail(f"Salomone generator failed with error: {e}")
