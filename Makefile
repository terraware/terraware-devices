# Run make REPOSITORY=testpypi to upload to the test pypi instance
REPOSITORY=pypi

package:
	if [ ! -d .venv ]; then python3 -m venv .venv; fi
	.venv/bin/pip install wheel
	.venv/bin/python setup.py sdist
	.venv/bin/python setup.py bdist_wheel

upload: package
	.venv/bin/pip install twine
	.venv/bin/twine upload --repository $(REPOSITORY) dist/*
