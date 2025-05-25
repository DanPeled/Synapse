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

## Project Structure
- `synapse-core`: Contains the core Python library for Synapse.
- `synapse-lib` Contains the vendordep library for the robot to communicate with the Synapse runtime.

## Getting Started
1. Clone the repository.
2. Install required dependencies.
3. Deploy code onto the coprocessor

## License
This project is licensed under the [MIT License](LICENSE).
