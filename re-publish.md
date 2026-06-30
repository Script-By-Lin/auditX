# 1. Install build tools (once)
pip install -e ".[dev]"
# 2. Clean old artifacts
rm -rf dist/ build/ *.egg-info
# 3. Build sdist + wheel
python -m build
# 4. Upload to PyPI
twine upload dist/*
When prompted for credentials, use:

Username: __token__
Password: your PyPI API token (starts with pypi-)
Or set them inline:

TWINE_USERNAME=__token__ TWINE_PASSWORD=pypi-YOUR_TOKEN_HERE twine upload dist/*
Important: PyPI will reject an upload if that version already exists. Current version in pyproject.toml is 0.1.7 — bump it first if that release is already on PyPI:

version = "0.1.6"
Optional sanity check before upload:


twine check dist/*