import yaml
from synapse.nt_client import NtClient
from wpilib import SmartDashboard
from synapse.pipline_handler import PipelineHandler
from synapse.pipeline import Pipeline


class Synapse:
    def __init__(self) -> None:
        with open(r"./internal_files/settings.yml") as file:
            settings = yaml.full_load(file)
            network_settings = settings["network"]

            self.nt_client = NtClient(
                network_settings["server_ip"],
                network_settings["name"],
                network_settings["server"],
            )

            SmartDashboard.init()
