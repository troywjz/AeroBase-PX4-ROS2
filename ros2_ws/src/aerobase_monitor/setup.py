from setuptools import find_packages, setup

setup(
    name="aerobase_monitor",
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/aerobase_monitor"]),
        ("share/aerobase_monitor", ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="troywjz",
    maintainer_email="70458808+troywjz@users.noreply.github.com",
    description="Read-only PX4 telemetry monitoring for AeroBase",
    license="MIT",
    entry_points={"console_scripts": ["vehicle_monitor = aerobase_monitor.vehicle_monitor:main"]},
)
