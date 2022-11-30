from setuptools import setup, find_packages
from dycode import __version__

with open("README.md", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="dycode",
    packages=find_packages(include=["dycode"]),
    version=__version__,
    license="MIT",
    description="A toolset for dynamic python code manipulations",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Vahid Zehtab",
    author_email="vahid@zehtab.me",
    url="https://github.com/vahidzee/dycode",
    keywords=["dynamic coding", "dynamic functions", "lazy evaluation"],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: End Users/Desktop",
        "Intended Audience :: Education",
        "Programming Language :: Python :: Implementation",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Software Development :: Libraries",
        "Topic :: Utilities",
    ],
    python_requires=">=3.8",
)
