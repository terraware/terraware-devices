from setuptools import setup
import pathlib

here = pathlib.Path(__file__).parent.resolve()
long_description = (here / 'README.md').read_text()

setup(
    name='terraware-devices',
    version='0.1.0',
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
        'rhizo-client~=0.1.0',
    ],
    license='MIT',
    packages=['terraware_devices'],
    python_requires='>=3.7, <4',
)
