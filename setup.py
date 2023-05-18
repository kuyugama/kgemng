from setuptools import setup, find_packages

setup(
    name='kgemng',
    version='0.0.7',
    packages=find_packages(),
    url='',
    license='MIT',
    author='KuyuGama',
    author_email='mail.kuyugama@gmail.com',
    description='Asynchronous events managers. Part of KuyuGenesis',
    install_requires=["namedlocks", "relative-addons-system", "pyrogram", "magic-filter"]
)
