# Synapse
A library for running custom vision code on an FRC coprocessor.

## Features
- **Pipeline System:** Organize and manage vision processing tasks efficiently.
- **Multiple Camera Support:** Handle multiple camera inputs simultaneously.
- **NetworkTables Integration:** Post vision results directly to NetworkTables for easy access in FRC dashboards.
- **Global Pipeline Configuration:** Easily configure global pipeline settings.
- **Fast Pipeline Development:** Streamlined workflow for creating and testing new pipelines.
- **Custom Python Pipelines:** Load and run custom Python-based vision pipelines.
- **Realtime Settings:** Adjust settings in real-time through NetworkTables.
- **Dynamic Pipeline Creation:** Create and modify pipelines dynamically.
- **Interactive UI:** A responsive, visual interface for:
  - Viewing live camera feeds
  - Managing and switching between pipelines
  - Tuning pipeline parameters in real-time
  - Monitoring output data and debugging visually
  Designed for intuitive interaction and minimal setup.
  
## Project Structure
- `synapse_core`: Contains the core Python library for Synapse.
- `synapse_net`: Contains the networking library for the runtime, including NetworkTables and socket communication, as well as Protocol Buffers message definitions.
- `synapse_lib` Contains the vendordep library for the robot to communicate with the Synapse runtime.
- `synapse_ui`: Contains the graphical user interface (UI) for interacting with the Synapse runtime.


## Getting Started
1. Clone the repository.
2. Install required dependencies.
3. Deploy code onto the coprocessor

## License
This project is licensed under the [MIT License](LICENSE).
