from distutils.core import setup
import distutils.cmd
from distutils.ccompiler import new_compiler
import setuptools.command.build_py


# class BuildPyCommand(setuptools.command.build_py.build_py):
#     """Custom build command."""

#     def run(self):
#         print("Hello")
#         setuptools.command.build_py.build_py.run(self)

setup(
    #cmdclass={'build_py', BuildPyCommand},
    name='PySME',
    version='0.2',
    packages=['sme',],
    license='Lesser General Public License 3.0',
    long_description=open('README.md').read(),
    setup_requires=["cffi>=1.0.0"],
    cffi_modules=["sme/libsme_support_build.py:ffibuilder"],
    install_requires=["cffi>=1.0.0"]
)
