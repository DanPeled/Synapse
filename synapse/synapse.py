from typing import Any
import yaml
from synapse.nt_client import NtClient
from synapse.pipeline_settings import GlobalSettings
from synapse.pipline_handler import PipelineHandler
from synapse.log import log


class Synapse:
    def init(self, pipeline_handler: PipelineHandler) -> bool:
        log("Initializing Synapse...")
        self.pipeline_handler = pipeline_handler

        try:
            with open(r"./config/settings.yml") as file:
                settings = yaml.full_load(file)
                self.settings_dict = settings
                network_settings = settings["network"]
                nt_good = self.__init_networktables(network_settings)
                if nt_good:
                    self.pipeline_handler.setup()
                else:
                    log(
                        f"Error something went wrong while setting up networktables with params: {network_settings}"
                    )

                global_settings = settings["global"]
                GlobalSettings.setup(global_settings)

        except Exception:
            log("Something went wrong while reading settings config file.")
            return False

        log("Initialized Synapse successfuly")
        return True

    def __init_networktables(self, settings: dict[str, Any]) -> bool:
        self.nt_client = NtClient()
        setup_good = self.nt_client.setup(
            settings["server_ip"], settings["name"], settings["server"]
        )
        return setup_good

    def run(self):
        self.pipeline_handler.loadSettings()
        self.pipeline_handler.run()
