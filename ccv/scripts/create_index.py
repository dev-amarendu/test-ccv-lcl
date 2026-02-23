import argparse
from google.cloud import aiplatform

def create_vector_index(
    project_id: str,
    location: str,
    display_name: str,
    dimensions: int = 768,
    distance_measure: str = "DOT_PRODUCT"
):
    """Creates a Vertex AI Vector Search Index.
    
    This is where embedding-specific configurations (dimensions, distance metric) are defined.
    """
    
    # Initialize the Vertex AI SDK
    aiplatform.init(project=project_id, location=location)

    print(f"Creating Vector Search Index: {display_name}...")
    print(f"Config: {dimensions} dimensions, {distance_measure} distance metric")

    # Create the Index
    # Note: We are creating a 'streaming' index which allows for real-time updates
    # which is ideal for a Knowledge Base that changes frequently.
    index = aiplatform.MatchingEngineIndex.create_streaming(
        display_name=display_name,
        dimensions=dimensions,
        distance_measure_type=distance_measure,
        description="CCV Knowledge Base Index for RAG",
    )

    print(f"Success! Vector Search Index Created.")
    print(f"Display Name: {index.display_name}")
    print(f"Resource Name: {index.resource_name}")
    print(f"Index ID: {index.name}")
    
    return index

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create a Vertex AI Vector Search Index for CCV.")
    parser.add_argument("--project", required=True, help="Google Cloud Project ID")
    parser.add_argument("--region", default="us-central1", help="GCP Region")
    parser.add_argument("--name", default="ccv-kb-index", help="Display name for the index")
    parser.add_argument("--dims", type=int, default=768, help="Embedding dimensions (768 for Gemini)")
    parser.add_argument("--metric", default="DOT_PRODUCT", choices=["DOT_PRODUCT", "COSINE_DISTANCE", "SQUARED_L2_DISTANCE"], 
                        help="Distance measure type")

    args = parser.parse_args()

    try:
        create_vector_index(
            project_id=args.project,
            location=args.region,
            display_name=args.name,
            dimensions=args.dims,
            distance_measure=args.metric
        )
    except Exception as e:
        print(f"Error creating Vector Search Index: {e}")
