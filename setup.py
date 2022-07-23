from setuptools import setup
import pathlib

base_dir = pathlib.Path(__file__).parent

with open(base_dir / "README.md") as f:
    long_description = f.read()

setup(
  name = 'photosdup',
  packages = ['photosdup'],   
  version = '2.3',
  license='MIT',        
  description = 'Photos Duplicate finder - searches for duplicate or similar images in a Mac Photos library.', 
  long_description=long_description,
  long_description_content_type='text/markdown',
  author = 'Peter Schneider-Kamp',
  author_email = 'petersk@imada.sdu.dk', 
  url = 'https://github.com/peter-sk/photosdup', 
  keywords = ['mac', 'photos', 'duplicate', 'finder'],  
  install_requires=[
          'scipy',
          'numpy',
          'opencv-python',
          'photoscript',
          'scikit-image',
          'PySimpleGUI',
          'tqdm',
          'pyheif',
          'matplotlib'
      ],
  classifiers=[
    'Development Status :: 5 - Production/Stable',      # Chose either "3 - Alpha", "4 - Beta" or "5 - Production/Stable" as the current state of your package
    'Intended Audience :: Developers',      
    'Topic :: Software Development :: Build Tools',
    'License :: OSI Approved :: MIT License',    
    'Programming Language :: Python :: 3.9'
  ]
)
