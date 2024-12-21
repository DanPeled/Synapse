from typing import Any
import yaml
from synapse.nt_client import NtClient
from synapse.pipeline_settings import GlobalSettings
from synapse.pipline_handler import PipelineHandler
from synapse.log import log


class Synapse:
    """
    handles the initialization and running of the Synapse runtime, including network setup and loading global settings.

        Attributes:
            pipeline_handler (PipelineHandler): The handler responsible for managing the pipelines' lifecycles.
            settings_dict (dict): A dictionary containing the configuration settings loaded from the `settings.yml` file.
            nt_client (NtClient): The instance of NtClient used to manage the NetworkTables connection.
    """

    def init(self, pipeline_handler: PipelineHandler) -> bool:
        """
        Initializes the Synapse pipeline by loading configuration settings and setting up NetworkTables and global settings.

        Args:
            pipeline_handler (PipelineHandler): The handler responsible for managing the pipeline's lifecycle.

        Returns:
            bool: True if initialization was successful, False otherwise.
        """
        log("Initializing Synapse...")
        self.pipeline_handler = pipeline_handler

        try:
            # Load the settings from the config file
            with open(r"./config/settings.yml") as file:
                settings = yaml.full_load(file)
                self.settings_dict = settings
                network_settings = settings["network"]

                # Initialize NetworkTables
                nt_good = self.__init_networktables(network_settings)
                if nt_good:
                    self.pipeline_handler.setup(settings)
                else:
                    log(
                        f"Error something went wrong while setting up networktables with params: {network_settings}"
                    )

                # Setup global settings
                global_settings = settings["global"]
                GlobalSettings.setup(global_settings)

        except Exception as e:
            log(f"Something went wrong while reading settings config file. {repr(e)}")
            return False

        log("Initialized Synapse successfully")
        return True

    def __init_networktables(self, settings: dict[str, Any]) -> bool:
        """
        Initializes the NetworkTables client with the provided settings.

        Args:
            settings (dict): A dictionary containing the NetworkTables settings such as `server_ip`, `name`, and `server` status.

        Returns:
            bool: True if NetworkTables was successfully initialized, False otherwise.
        """
        self.nt_client = NtClient()
        setup_good = self.nt_client.setup(
            settings["server_ip"], settings["name"], settings["server"]
        )
        return setup_good

    def run(self):
        """
        Starts the pipeline by loading the settings and executing the pipeline handler.

        This method is responsible for running the pipeline after it has been initialized.
        """
        self.pipeline_handler.loadSettings()
        self.pipeline_handler.run()
