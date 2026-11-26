"""
SITL (Software In The Loop) & Virtual Simulation Module.
Enables defense tech researchers to validate C2 Cognitive Saturation and CRA
mitigation against virtual drone swarms without requiring physical UAV hardware or weapon systems.
"""

from .sitl_adapter import SitlAdapter, VirtualSwarmScenario

__all__ = ["SitlAdapter", "VirtualSwarmScenario"]
