import argparse
from google.cloud import aiplatform

def create_index_endpoint(
    project_id: str,
    location: str,
    display_name: str,
):
    """Creates a Vertex AI IndexEndpoint (Matching Engine Index Endpoint).
    
    This endpoint is required to deploy a Vector Search Index for online querying.
    """
    
    # Initialize the Vertex AI SDK
    aiplatform.init(project=project_id, location=location)

    print(f"Creating Index Endpoint: {display_name} in {location}...")

    # Create the Index Endpoint
    index_endpoint = aiplatform.MatchingEngineIndexEndpoint.create(
        display_name=display_name,
        public_endpoint_enabled=True, # CCV uses public endpoints for easier API access
        description="Public endpoint for CCV Knowledge Base (Vector Search)"
    )

    print(f"Success! Index Endpoint Created.")
    print(f"Display Name: {index_endpoint.display_name}")
    print(f"Resource Name: {index_endpoint.resource_name}")
    print(f"Endpoint ID: {index_endpoint.name}")
    
    return index_endpoint

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create a Vertex AI Index Endpoint for CCV.")
    parser.add_argument("--project", required=True, help="Google Cloud Project ID")
    parser.add_argument("--region", default="us-central1", help="GCP Region (e.g., us-central1)")
    parser.add_argument("--name", default="ccv-kb-endpoint", help="Display name for the endpoint")

    args = parser.parse_args()

    try:
        create_index_endpoint(
            project_id=args.project,
            location=args.region,
            display_name=args.name
        )
    except Exception as e:
        print(f"Error creating Index Endpoint: {e}")
