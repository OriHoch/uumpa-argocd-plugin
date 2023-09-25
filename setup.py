from setuptools import setup, find_packages

setup(
    name='uumpa-argocd-plugin',
    packages=find_packages(exclude=['tests']),
    entry_points={
        'console_scripts': [
            'uumpa-argocd-plugin = uumpa_argocd_plugin.cli:main',
        ]
    },
)
