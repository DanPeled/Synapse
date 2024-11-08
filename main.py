from synapse.synapse import PipelineHandler, Synapse

if __name__ == "__main__":
    Synapse()
    handler = PipelineHandler("../")  # Relative directory to synapse dir
    handler.add_camera(0)
    handler.set_pipeline_for_camera_by_name(0, "ApriltagPipeline")
    handler.run()
