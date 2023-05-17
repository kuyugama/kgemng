from setuptools import setup

setup(
    name='kgemng',
    version='0.0.1',
    packages=['kgemng'],
    url='',
    license='MIT',
    author='KuyuGama',
    author_email='mail.kuyugama@gmail.com',
    description='Asynchronous events managers. Part of KuyuGenesis',
    install_requires=["namedlocks", "relative-addons-system", "pyrogram", "magic-filter"]
)
