from setuptools import setup
import pathlib

here = pathlib.Path(__file__).parent.resolve()
long_description = (here / 'README.md').read_text()

setup(
    name='terraware-devices',
    version='0.1.7',
    description='Device management for Terraformation hardware systems',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/terraware/terraware-devices',
    author='Terraformation',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
    ],
    install_requires=[
        'requests>=2.0',
        # bluepy is not actively maintained; see https://github.com/IanHarvey/bluepy/issues/403
        # It has a Linux-specific C extension, so skip install on other platforms.
        'bluepy~=1.3; platform_system=="Linux"',
        # gevent versions are date-based so tell us nothing about breaking changes
        'gevent>=20.9',
        # pymodbus bumps its minor version number for each release
        'pymodbus~=2.4',
        # rhizo-server API is under development, so minor versions might have breaking changes
        'rhizo-client~=0.1.3',
    ],
    license='MIT',
    packages=['terraware_devices'],
    python_requires='>=3.7, <4',
)
