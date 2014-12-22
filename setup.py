from setuptools import setup

setup(name='pylobby',
      version='0.1.0',
      description='Decentralized chat library',
      long_description=open('README.rst').read(),
      author='Marin Atanasov Nikolov',
      author_email='dnaeon@gmail.com',
      license='BSD',
      url='https://github.com/dnaeon/pylobby',
      download_url='https://github.com/dnaeon/pylobby/releases',
      packages=[
          'pylobby',
          'pylobby.client',
          'pylobby.server',
      ],
      install_requires=[
        'pyzmq >= 14.4.1',
      ]
)
