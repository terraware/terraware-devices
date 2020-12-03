# Terraware device manager code

This code provides local on-site monitoring and control software for Terraformation hardware systems (seed banks, power generation, desalination, irrigation, etc.).

## Installation

To install the latest release: `pip install terraware-devices`

To install a local copy of this repo as a dependency in another project: `pip install -e /path/to/terraware-devices`

To install dependencies to work on the code locally: `pip install -e .`

## Packaging

Run `make package` to package the code for public distribution.

If you are a maintainer of the package on PyPI, run `make upload` to upload it (this will do `make package` automatically).

To upload to the test PyPI instance, run `make REPOSITORY=testpypi upload`.
