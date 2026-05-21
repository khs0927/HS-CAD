from pathlib import Path
from unittest.mock import MagicMock
from src.adapters.lisp_adapter import LispAdapter

def test_lisp_adapter_path_normalization_on_windows():
    # Arrange
    mock_doc = MagicMock()
    mock_com_adapter = MagicMock()
    mock_com_adapter.get_active_document.return_value = mock_doc
    
    adapter = LispAdapter(mock_com_adapter)
    
    # Act
    # Pass a path with Windows backslashes
    adapter.load_lisp("C:\\cad\\sample\\my_lisp.lsp")
    
    # Assert
    mock_doc.SendCommand.assert_called_once_with('(load "C:/cad/sample/my_lisp.lsp")\n')

def test_lisp_adapter_path_normalization_with_path_object():
    # Arrange
    mock_doc = MagicMock()
    mock_com_adapter = MagicMock()
    mock_com_adapter.get_active_document.return_value = mock_doc
    
    adapter = LispAdapter(mock_com_adapter)
    
    # Act
    adapter.load_lisp(Path("C:/cad/another_sample/my_lisp.lsp"))
    
    # Assert
    mock_doc.SendCommand.assert_called_once_with('(load "C:/cad/another_sample/my_lisp.lsp")\n')
