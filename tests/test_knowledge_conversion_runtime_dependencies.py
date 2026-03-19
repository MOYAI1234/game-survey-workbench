import importlib.util

import pytest


@pytest.mark.parametrize(
    "module_name",
    ["mammoth", "lxml", "pdfplumber", "pdfminer", "pptx"],
)
def test_runtime_dependencies_for_knowledge_conversion_are_installed(module_name: str):
    assert importlib.util.find_spec(module_name) is not None
