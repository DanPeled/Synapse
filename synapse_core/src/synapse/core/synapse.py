import os
from pathlib import Path

from synapse.bcolors import bcolors
from synapse.core.config import Config, NetworkConfig
from synapse.log import err, log

from synapse_net import NtClient

from .pipeline import GlobalSettings
from .runtime_handler import RuntimeManager


class Synapse:
    """
    handles the initialization and running of the Synapse runtime, including network setup and loading global settings.

        Attributes:
            runtime_handler (RuntimeManager): The handler responsible for managing the pipelines' lifecycles.
            settings_dict (dict): A dictionary containing the configuration settings loaded from the `settings.yml` file.
            nt_client (NtClient): The instance of NtClient used to manage the NetworkTables connection.
    """

    def init(
        self,
        runtime_handler: RuntimeManager,
        config_path: Path,
    ) -> bool:
        """
        Initializes the Synapse pipeline by loading configuration settings and setting up NetworkTables and global settings.

        Args:
            runtime_handler (RuntimeManager): The handler responsible for managing the pipeline's lifecycle.
            config_path (str, optional): The path to the configuration file. Defaults to "./config/settings.yml".

        Returns:
            bool: True if initialization was successful, False otherwise.
        """

        log(
            bcolors.OKGREEN
            + bcolors.BOLD
            + "\n"
            + "=" * 20
            + " Synapse Initialize Starting... "
            + "=" * 20
            + bcolors.ENDC
        )

        self.runtime_handler = runtime_handler

        if config_path.exists():
            try:
                config = Config()
                config.load(filePath=config_path)

                # Load the settings from the config file
                settings = config.getConfigMap()
                self.settings_dict = settings

                global_settings = settings["global"]
                if not GlobalSettings.setup(global_settings):
                    raise Exception("Global settings setup failed")

                # Initialize NetworkTables
                self.__init_cmd_args()

                log(
                    f"Network Config:\n  Team Number: {config.network.teamNumber}\n  Name: {config.network.name}\n  Is Server: {self.__isServer}\n  Is Sim: {self.__isSim}"
                )

                nt_good = self.__init_networktables(config.network)
                if nt_good:
                    self.runtime_handler.setup(Path(os.getcwd()))
                else:
                    err(
                        f"Something went wrong while setting up networktables with params: {config.network}"
                    )
                    return False

                # Setup global settings
            except Exception as e:
                log(
                    f"Something went wrong while reading settings config file. {repr(e)}"
                )
                return False
        else:
            return False
        return True

    def __init_networktables(self, settings: NetworkConfig) -> bool:
        """
        Initializes the NetworkTables client with the provided settings.

        Args:
            settings (dict): A dictionary containing the NetworkTables settings such as `server_ip`, `name`, and `server` status.

        Returns:
            bool: True if NetworkTables was successfully initialized, False otherwise.
        """
        self.nt_client = NtClient()
        setup_good = self.nt_client.setup(
            teamNumber=settings.teamNumber,
            name=settings.name,
            isServer=self.__isServer,
            isSim=self.__isSim,
        )
        return setup_good

    def __init_cmd_args(self) -> None:
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("--server", action="store_true", help="Run in server mode")
        parser.add_argument("--sim", action="store_true", help="Run in sim mode")
        args = parser.parse_args()

        if args.server:
            self.__isServer = True
        else:
            self.__isServer = False
        if args.sim:
            self.__isSim = True
        else:
            self.__isSim = False

    def run(self) -> None:
        """
        Starts the pipeline by loading the settings and executing the pipeline handler.

        This method is responsible for running the pipeline after it has been initialized.
        """
        self.runtime_handler.run()

    @staticmethod
    def createAndRunRuntime(root: Path) -> None:
        handler = RuntimeManager(root)
        s = Synapse()
        if s.init(handler, root / "config" / "settings.yml"):
            s.run()
