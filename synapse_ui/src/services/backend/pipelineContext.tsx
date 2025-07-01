import { PipelineProto, PipelineTypeProto } from "@/proto/v1/pipeline";

export namespace PipelineManagement {
  export class PipelineContext {
    public constructor(
      public pipelines: Map<number, PipelineProto>,
      public pipelineTypes: Map<string, PipelineTypeProto>,
    ) { }
  }
}
