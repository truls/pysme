from distutils.core import setup
import distutils.cmd
from distutils.ccompiler import new_compiler
import setuptools.command.build_py


setup(
    name='PySME',
    version='0.2',
    packages=['sme',],
    license='Lesser General Public License 3.0',
    long_description=open('README.md').read(),
    setup_requires=["cffi>=1.0.0"],
    cffi_modules=["sme/libsme_support_build.py:ffibuilder"],
    install_requires=["cffi>=1.0.0"]
)
